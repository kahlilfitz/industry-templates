"""Re-derive a demo scenario's structured inputs from its raw pack (hardening item G4b).

``derive(scenario_dir)`` reads only ``scenario_dir/raw/*`` and returns
``{"roles": ..., "bench": ..., "constraints": ...}`` built with the ingest rules documented in
``tests/README.md`` ("Ingest rules"). Standard library only. Every constant below is one of those
documented rules; no scenario value is hard-coded here.
"""
import copy
import csv
import io
import re
from pathlib import Path

RAW_FILES = (
    "sow-role-extract.md",
    "staffing-request-email.txt",
    "bench-roster.csv",
    "conflicts-register-extract.csv",
)

# Rule: fixed contract version and connector/skill source labels.
CONTRACT_VERSION = "ps.engagement-staffing-bench-match.v1"
ROLE_SOURCE = "skill:role-intake"
BENCH_SOURCE = "connector:resource-management-system"
CONFLICTS_SOURCE = "connector:conflicts-register"

# Rule: provenance carries the demo-pack build stamp and the scenario folder name.
DEMO_PACK_GENERATED_AT = "2026-09-23T21:20:34Z"

# Rule: role and engagement confidence = how far the staffing request corroborates the SOW.
CORROBORATION_CONFIDENCE = {"full": 0.96, "partial": 0.95, "none": 0.94}

# Rule: bench-query evidence ladder (SKILL.md step 5) read from the roster's evidence columns.
BENCH_LADDER = {"no_enrichment": 0.95, "secondary_source": 0.97, "verified": 0.98, "standard": 0.96}
EVIDENCE_COLUMNS = ("profile_enrichment", "availability_verified", "secondary_source", "citation")

# Rule: one evidence tier for the whole conflicts-register extract.
CONFLICTS_CONFIDENCE = 0.97

# Rule: citation templates.
ENGAGEMENT_CITATION = "SOW extract {sow_id}, header and staffing request email"
ROLE_CITATION = "SOW {sow_id} section {section} role {index}"
LEAVE_CITATION = "leave calendar request {}"
SOFT_BOOKING_CITATION = "pursuit soft-book {}"
EXTRACT_CITATION = "conflicts extract {}"

# Rule: escalation wording.
PREFERENCE_ESCALATION = (
    "{role_id}: staffing request names {name} as a preferred candidate; recorded as context only "
    "and excluded from scoring and eligibility (role-intake step 4)"
)
MISSING_CODE_ESCALATION = (
    "engagement: SOW header gives no internal engagement code; carried SOW ID {sow_id} "
    "(role-intake step 1)"
)

CANONICAL_SENIORITY = {
    "associate", "consultant", "senior consultant", "manager", "senior manager", "director", "partner",
}
REGISTER_OPTIONAL = ("material", "role_type", "process", "end_date", "resolved_date")
REGISTER_REQUIRED = ("candidate_id", "type", "client_name", "status")

HEADER_SEPARATOR = "\u00b7"
PREFERENCE_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?) is the (?:obvious |preferred |right |best )?(?:pick|choice)\b"
)
LANGUAGE_IN_TITLE = re.compile(r"\b([A-Z][a-z]+)-speaking\b")
BOOKING_PATTERN = re.compile(r"^(\S+) (\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2}) (\d+)%$")
REGISTER_ID_PATTERN = re.compile(r"\b(CF-[A-Z]+-\d+)\b")


def _split_list(cell):
    cell = (cell or "").strip()
    if cell.casefold() in ("", "none"):
        return []
    return [item.strip() for item in cell.split(";") if item.strip()]


def _int(text, pattern, label):
    match = re.fullmatch(pattern, text.strip())
    if not match:
        raise ValueError(f"unrecognised {label}: {text!r}")
    return int(match.group(1))


def _seniority(text):
    value = text.strip().casefold()
    if value not in CANONICAL_SENIORITY:
        raise ValueError(f"non-canonical seniority: {text!r}")
    return value


def _parse_sow(text):
    lines = text.split("\n")
    title = re.fullmatch(r"# SOW (\S+) - Staffing excerpt", lines[0].strip())
    if not title:
        raise ValueError("SOW title line not recognised")
    header, section, table = {}, None, []
    for line in lines[1:]:
        stripped = line.strip()
        heading = re.fullmatch(r"## (\d+(?:\.\d+)*) Roles", stripped)
        if heading:
            section = heading.group(1)
        elif section is None and ":" in stripped:
            for part in stripped.split(HEADER_SEPARATOR):
                key, _, value = part.partition(":")
                header[key.strip()] = value.strip()
        elif section is not None and stripped.startswith("|"):
            table.append([cell.strip() for cell in stripped.strip("|").split("|")])
    if section is None or len(table) < 2:
        raise ValueError("SOW roles table not found")
    columns = table[0]
    rows = [dict(zip(columns, row)) for row in table[2:]]
    return title.group(1), header, section, rows


def _location(cell):
    remote = re.fullmatch(r"(.+?) or remote", cell.strip())
    if remote:
        return remote.group(1), True
    onsite = re.fullmatch(r"(.+?) only", cell.strip())
    if onsite:
        return onsite.group(1), False
    raise ValueError(f"unrecognised location: {cell!r}")


def _rate_band(cell):
    match = re.fullmatch(r"([A-Z]{3}) (\d+)-(\d+)/hr", cell.strip())
    if not match:
        raise ValueError(f"unrecognised rate band: {cell!r}")
    return {"currency": match.group(1), "min": int(match.group(2)), "max": int(match.group(3))}


def _request_blocks(text):
    _, _, body = text.replace("\r\n", "\n").partition("\n\n")
    blocks = []
    for paragraph in re.split(r"\n\s*\n", body):
        prose = []
        for line in paragraph.split("\n"):
            if re.match(r"\s*\d+\.\s", line):
                blocks.append(line.strip())
            elif line.strip():
                prose.append(line.strip())
        if prose:
            blocks.append(" ".join(prose))
    return blocks


def _corroboration(role, blocks):
    title = role["title"].casefold()
    named = [block.casefold().replace(title, " ") for block in blocks if title in block.casefold()]
    terms = [
        f"{role['allocation_pct']}%",
        role["start_date"],
        f"{role['duration_weeks']} weeks",
        role["location"],
        *role["required_skills"],
        *role["preferred_skills"],
        *role["required_certifications"],
    ]
    text = " ".join(named)
    found = sum(1 for term in terms if term.casefold() in text)
    if named and found == len(terms):
        return CORROBORATION_CONFIDENCE["full"]
    if found:
        return CORROBORATION_CONFIDENCE["partial"]
    return CORROBORATION_CONFIDENCE["none"]


def _derive_roles(scenario_name, sow_text, request_text):
    sow_id, header, section, rows = _parse_sow(sow_text)
    blocks = _request_blocks(request_text)
    client = header["Synthetic client"]
    code = header.get("Internal engagement code", "")
    escalations = [] if code else [MISSING_CODE_ESCALATION.format(sow_id=sow_id)]
    engagement = {
        "engagement_id": code or sow_id,
        "client_name": client,
        "affiliates": _split_list(header.get("Known client affiliate", "")),
        "practice": header["Practice"],
        "stage": header["Lifecycle stage"],
        "source": ROLE_SOURCE,
        "confidence": CORROBORATION_CONFIDENCE[
            "full" if client.casefold() in request_text.casefold() else "none"
        ],
        "citation": ENGAGEMENT_CITATION.format(sow_id=sow_id),
    }
    working_language = header["Working language"]
    roles = []
    for index, row in enumerate(rows, start=1):
        location, remote_ok = _location(row["Location"])
        languages = [working_language]
        for language in LANGUAGE_IN_TITLE.findall(row["Role"]):
            if language not in languages:
                languages.append(language)
        role = {
            "role_id": row["Role ID"],
            "title": row["Role"],
            "seniority": _seniority(row["Seniority"]),
            "start_date": row["Start"],
            "duration_weeks": _int(row["Duration"], r"(\d+) weeks?", "duration"),
            "allocation_pct": _int(row["Allocation"], r"(\d+)%", "allocation"),
            "location": location,
            "remote_ok": remote_ok,
            "required_languages": languages,
            "required_skills": _split_list(row["Required skills"]),
            "preferred_skills": _split_list(row["Preferred skills"]),
            "required_certifications": _split_list(row["Certifications"]),
            "industry_context": header["Client industry"],
            "rate_band": _rate_band(row["Rate band"]),
            "source": ROLE_SOURCE,
        }
        role["confidence"] = _corroboration(role, blocks)
        role["citation"] = ROLE_CITATION.format(sow_id=sow_id, section=section, index=index)
        roles.append(role)
    for block in blocks:
        for name in PREFERENCE_PATTERN.findall(block):
            named_roles = [role for role in roles if role["title"].casefold() in block.casefold()]
            role_id = named_roles[0]["role_id"] if named_roles else "engagement"
            escalations.append(PREFERENCE_ESCALATION.format(role_id=role_id, name=name))
    return {
        "contract_version": CONTRACT_VERSION,
        "engagement": engagement,
        "roles": roles,
        "escalations": escalations,
        "provenance": {"generated_at": DEMO_PACK_GENERATED_AT, "demo_scenario": scenario_name},
    }


def _bookings(cell, template):
    records = []
    for entry in _split_list(cell):
        match = BOOKING_PATTERN.fullmatch(entry)
        if not match:
            raise ValueError(f"unrecognised availability record: {entry!r}")
        record_id, start, end, pct = match.groups()
        records.append({"start": start, "end": end, "allocation_pct": int(pct),
                        "citation": template.format(record_id)})
    return records


def _bench_confidence(row):
    enrichment = row["profile_enrichment"].strip().casefold()
    verified = row["availability_verified"].strip().casefold()
    if enrichment not in ("standard", "none") or verified not in ("yes", "no"):
        raise ValueError(f"unrecognised evidence columns for {row['candidate_id']!r}")
    if enrichment == "none":
        return BENCH_LADDER["no_enrichment"]
    if row["secondary_source"].strip():
        return BENCH_LADDER["secondary_source"]
    if verified == "yes":
        return BENCH_LADDER["verified"]
    return BENCH_LADDER["standard"]


def _read_csv(text):
    return list(csv.DictReader(io.StringIO(text), skipinitialspace=True))


def _derive_bench(roles_payload, roster_text):
    candidates = []
    for row in _read_csv(roster_text):
        candidates.append({
            "candidate_id": row["candidate_id"].strip(),
            "name": row["name"].strip(),
            "seniority": _seniority(row["seniority"]),
            "skills": _split_list(row["skills"]),
            "certifications": _split_list(row["certifications"]),
            "industry_experience": _split_list(row["industry_experience"]),
            "location": row["location"].strip(),
            "languages": _split_list(row["languages"]),
            "rate": int(row["rate"]),
            "current_allocation_pct": int(row["current_allocation_pct"]),
            "target_utilization_pct": int(row["target_utilization_pct"]),
            "approved_leave": _bookings(row["approved_leave"], LEAVE_CITATION),
            "soft_bookings": _bookings(row["soft_bookings"], SOFT_BOOKING_CITATION),
            "source": BENCH_SOURCE,
            "confidence": _bench_confidence(row),
            "citation": row["citation"],
        })
    return {
        "contract_version": CONTRACT_VERSION,
        "engagement": copy.deepcopy(roles_payload["engagement"]),
        "roles": [],
        "bench_candidates": candidates,
        "escalations": [],
        "provenance": copy.deepcopy(roles_payload["provenance"]),
    }


def _material(value):
    lowered = value.casefold()
    if lowered in ("true", "false"):
        return lowered == "true"
    return value


def _derive_constraints(roles_payload, register_text):
    rows, register_ids = [], set()
    for row in _read_csv(register_text):
        record = {key: row[key].strip() for key in REGISTER_REQUIRED}
        for key in REGISTER_OPTIONAL:
            value = (row.get(key) or "").strip()
            if value:
                record[key] = _material(value) if key == "material" else value
        record["source"] = CONFLICTS_SOURCE
        record["confidence"] = CONFLICTS_CONFIDENCE
        record["citation"] = row["citation"]
        register_ids.update(REGISTER_ID_PATTERN.findall(row["citation"]))
        rows.append(record)
    if len(register_ids) != 1:
        raise ValueError(f"expected one conflicts-register ID, found {sorted(register_ids)}")
    return {
        "contract_version": CONTRACT_VERSION,
        "engagement": copy.deepcopy(roles_payload["engagement"]),
        "roles": copy.deepcopy(roles_payload["roles"]),
        "constraints": rows,
        "source": CONFLICTS_SOURCE,
        "confidence": CONFLICTS_CONFIDENCE,
        "citation": EXTRACT_CITATION.format(register_ids.pop()),
    }


def derive_from_sources(scenario_name, sources):
    """Derive the structured inputs from raw file texts keyed by the names in ``RAW_FILES``."""
    roles = _derive_roles(scenario_name, sources["sow-role-extract.md"],
                          sources["staffing-request-email.txt"])
    return {
        "roles": roles,
        "bench": _derive_bench(roles, sources["bench-roster.csv"]),
        "constraints": _derive_constraints(roles, sources["conflicts-register-extract.csv"]),
    }


def read_raw(scenario_dir):
    raw = Path(scenario_dir) / "raw"
    return {name: (raw / name).read_text(encoding="utf-8") for name in RAW_FILES}


def derive(scenario_dir: Path) -> dict:
    scenario_dir = Path(scenario_dir)
    return derive_from_sources(scenario_dir.name, read_raw(scenario_dir))
