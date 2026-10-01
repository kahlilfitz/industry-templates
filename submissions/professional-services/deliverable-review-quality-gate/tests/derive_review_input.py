#!/usr/bin/env python3
"""Re-derive a demo scenario's review-input.json from its raw pack (stdlib only).

  python tests/derive_review_input.py [demo-data/<scenario> ...]

Every value in a scenario's structured input must appear in, or follow by a documented
deliverable-ingest / criteria-retrieve rule from, that scenario's raw pack:

  raw/draft-deliverable.md         cover (title, client, engagement, document ID, version, type,
                                   confidentiality marking, distribution list), [Page N] markers,
                                   numbered paragraphs, disclaimer clause titles
  raw/supporting-evidence-index.md evidence ID, title, type, source and confidence
  raw/prior-review-findings.md     tracker status, document check, location and confidence
  raw/release-registers.md         client-data handling, brand checks, licensed-content register
  raw/qrm-gate-criteria-extract.md criteria set ID

Source fields are rebuilt and compared exactly. Assertions are traced instead: the text must be
quoted from the located paragraph under the stated section and page, sample and population sizes
must appear in that paragraph or in a linked evidence entry, and every evidence ID must be indexed.
Classification fields (class, label, hedging_present, limitation_present, stated_basis,
scope_aligned), prior-finding detail and extraction confidence are ingest judgements: they are
listed in JUDGEMENT_KEYS and type-checked, not re-derived. Any other field is reported, so a new
fixture value cannot be added without a raw source or a documented rule.

Paragraph rule (deliverable-ingest step 3): a paragraph is a block of body text separated by a
blank line; headings, [Page N] markers and blank lines are not paragraphs. Paragraphs are counted
from 1 on each page. A source with no [Page N] markers is unpaginated: every block is page 1 and
paragraphs are counted from 1 from the top of the document.
Exit code 0 = every scenario derives cleanly.
"""
import json
import os
import re
import sys

CONTRACT_VERSION = "ps.deliverable-review-quality-gate.v1"
CRITERIA_FLOOR = ["quality-gate-criteria.md #1-#8", "severity-rules.md #1-#4"]
PAGE_MARKER = re.compile(r"^\[Page (\d+)\]$")
SECTION_NUMBER = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
LOCATION = re.compile(r"^(?P<section>.+?), page (?P<page>\d+), paragraph (?P<paragraph>\d+), (?P<label>.+)$")
EVIDENCE = re.compile(r"^- (?P<id>EV-[\w-]+): (?P<title>.+?)\. (?P<desc>.*?) ?Type: (?P<type>\w+)\. Source: (?P<source>[\w ]+)\. Confidence: (?P<conf>[\d.]+)\.$")
PRIOR = re.compile(r"^- (?P<id>PR-[\w-]+): (?P<request>.+?) Tracker status: (?P<status>closed|open)[^.]*\. Document check: fix (?P<fix>present|absent)[^.]*\. Location: (?P<loc>.+?)\. Confidence: (?P<conf>[\d.]+)\.$")
BRAND = re.compile(r"^- (?P<id>[\w-]+): (?P<status>\w+)\. (?P<title>.+?)\. (?P<detail>.+?) Legal or release control: (?P<legal>yes|no)\. Location: (?P<loc>.+?)\. Confidence: (?P<conf>[\d.]+)\. Criteria: (?P<crit>.+?)\.$")
LICENSED = re.compile(r"^- (?P<id>[\w-]+): (?P<detail>.+?) Attribution present: (?P<attr>yes|no)\. License status: (?P<status>[\w ]+)\. Location: (?P<loc>.+?)\. Confidence: (?P<conf>[\d.]+)\. Register: (?P<register>.+?)\. Criteria: (?P<crit>.+?)\.$")
NO_ASSURANCE = re.compile(r"\bnot (?:provide |be treated as |an? )?assurance\b", re.IGNORECASE)
RELIANCE = re.compile(r"\bmay not be relied (?:up)?on\b|\breliance\b", re.IGNORECASE)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
MISSING = object()

JUDGEMENT_KEYS = {
    "deliverable": {"confidence"},
    "criteria": {"confidence"},
    "assertion": {"assertion_id", "class", "location", "hedging_present", "limitation_present", "stated_basis", "scope_aligned", "confidence"},
    "prior_finding": {"detail"},
}
ORDER_FREE = {"present_disclaimer_types", "required_language", "present_language"}
REGISTER_IDS = {"brand_checks": "check_id", "licensed_content": "content_id"}


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section_name(heading):
    return SECTION_NUMBER.sub("", heading.strip())


def parse_draft(text):
    """Return (title, cover fields, blocks keyed by (page, paragraph), disclaimer clause titles)."""
    lines = text.splitlines()
    paginated = any(PAGE_MARKER.match(line.strip()) for line in lines)
    page, paragraph, section, title = 1, 0, None, None
    blocks, current, disclaimers = {}, [], []

    def flush():
        nonlocal paragraph
        if current:
            paragraph += 1
            blocks[(page, paragraph)] = {"section": section, "text": " ".join(current), "lines": list(current)}
            current.clear()

    for raw in lines:
        line = raw.strip()
        marker = PAGE_MARKER.match(line)
        if marker:
            flush()
            page, paragraph = int(marker.group(1)), 0
        elif line.startswith("# "):
            flush()
            title, section = line[2:].strip(), "Cover"
        elif line.startswith("#"):
            flush()
            section = section_name(line.lstrip("#"))
            clause = re.match(r"^Disclaimer - (.+)$", section)
            if clause:
                disclaimers.append(clause.group(1).strip().lower().replace(" ", "_"))
        elif not line:
            flush()
        else:
            current.append(line)
    flush()
    if not paginated and any(key[0] != 1 for key in blocks):
        raise ValueError("unpaginated draft produced a page other than 1")
    cover = {}
    first = next((block for key, block in sorted(blocks.items()) if block["section"] == "Cover"), None)
    for line in first["lines"] if first else []:
        for part in line.split(" | "):
            key, sep, value = part.partition(": ")
            if sep:
                cover[key.strip()] = value.strip()
    return title, cover, blocks, disclaimers


def parse_location(text):
    match = LOCATION.match(text.strip())
    if not match:
        raise ValueError(f"unparseable location: {text!r}")
    return {"section": match["section"], "page": int(match["page"]), "paragraph": int(match["paragraph"]), "label": match["label"]}


def register_sections(text):
    sections, name = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            sections[name] = []
        elif name and line.strip():
            sections[name].append(line.strip())
    return sections


def parse_registers(path):
    """Return client_data_handling, brand_checks and licensed_content; a missing register is unknown/None."""
    sections = register_sections(read_text(path)) if os.path.exists(path) else {}
    handling = "unknown"
    for line in sections.get("Client-data handling register", []):
        match = re.match(r"^Handling status: (\w+)$", line)
        if match:
            handling = match.group(1)
    brand = None
    if "Brand and formatting checks" in sections:
        brand = []
        for line in sections["Brand and formatting checks"]:
            match = BRAND.match(line)
            if match:
                brand.append({"check_id": match["id"], "status": match["status"], "legal_or_release_control": match["legal"] == "yes",
                              "title": match["title"], "detail": match["detail"], "location": parse_location(match["loc"]),
                              "confidence": float(match["conf"]), "citation": match["crit"]})
    licensed = None
    if "Licensed and third-party content register" in sections:
        licensed = []
        for line in sections["Licensed and third-party content register"]:
            match = LICENSED.match(line)
            if match:
                licensed.append({"content_id": match["id"], "attribution_present": match["attr"] == "yes", "license_status": match["status"],
                                 "detail": match["detail"], "location": parse_location(match["loc"]), "confidence": float(match["conf"]),
                                 "citation": f"{match['register']}; {match['crit']}"})
    return handling, brand, licensed


def parse_evidence(text):
    items, lines = [], {}
    for line in text.splitlines():
        match = EVIDENCE.match(line.strip())
        if match:
            items.append({"evidence_id": match["id"], "type": match["type"], "title": match["title"], "confidence": float(match["conf"]),
                          "source": "connector:" + match["source"].strip().lower().replace(" ", "-"),
                          "citation": f"supporting-evidence-index.md {match['id']}"})
            lines[match["id"]] = line
    return items, lines


def parse_prior(text):
    items = []
    for line in text.splitlines():
        match = PRIOR.match(line.strip())
        if match:
            closed, fixed = match["status"] == "closed", match["fix"] == "present"
            citation = f"prior-review-findings.md {match['id']}"
            if closed and not fixed:
                citation += "; quality-gate-criteria.md #7.1-#7.2"
            items.append({"finding_id": match["id"], "claimed_closed": closed, "document_fix_present": fixed,
                          "location": parse_location(match["loc"]), "confidence": float(match["conf"]),
                          "source": "skill:criteria-retrieve", "citation": citation})
    return items


def derive(scenario_dir):
    """Rebuild every source-derived field of review-input.json from scenario_dir/raw."""
    scenario = os.path.basename(os.path.normpath(scenario_dir))
    raw = os.path.join(scenario_dir, "raw")
    title, cover, blocks, disclaimers = parse_draft(read_text(os.path.join(raw, "draft-deliverable.md")))
    client = cover.get("Client")
    recipients = [item.strip() for item in cover["Distribution"].split(";")] if cover.get("Distribution") else None
    third_party = any(client is None or client.lower() not in item.lower() for item in recipients or [])
    handling, brand, licensed = parse_registers(os.path.join(raw, "release-registers.md"))
    body = " ".join(block["text"] for block in blocks.values())
    headings = " ".join(block["section"] or "" for block in blocks.values())
    present_language = []
    if re.search(r"limitation", headings + " " + body, re.IGNORECASE):
        present_language.append("limitations")
    if NO_ASSURANCE.search(body):
        present_language.append("no_assurance")
    if "reliance_restriction" in disclaimers or RELIANCE.search(" ".join(b["text"] for b in blocks.values() if (b["section"] or "").startswith("Disclaimer"))):
        present_language.append("reliance_restriction")
    deliverable = {
        "deliverable_id": cover.get("Document ID", MISSING), "client_name": client or MISSING, "title": title or MISSING,
        "version": cover.get("Version", MISSING), "type": cover.get("Document type", MISSING),
        "intended_recipients": recipients if recipients is not None else MISSING,
        "third_party_recipient_named": third_party, "confidentiality_marking": cover.get("Confidentiality marking", MISSING),
        "client_data_handling": handling,
        "required_disclaimer_type": "reliance_restriction" if third_party else "general_advice",
        "present_disclaimer_types": disclaimers,
        "required_language": (["reliance_restriction"] if third_party else []) + ["limitations", "no_assurance"],
        "present_language": present_language,
        "brand_checks": brand, "licensed_content": licensed,
        "source": "skill:deliverable-ingest", "citation": f"demo-data/{scenario}/raw/draft-deliverable.md",
    }
    if cover.get("Client aliases"):
        deliverable["client_aliases"] = [item.strip() for item in cover["Client aliases"].split(";")]
    extract = read_text(os.path.join(raw, "qrm-gate-criteria-extract.md"))
    set_id = re.search(r"^Criteria set ID: (.+)$", extract, re.MULTILINE)
    evidence, evidence_lines = parse_evidence(read_text(os.path.join(raw, "supporting-evidence-index.md")))
    return {
        "contract_version": CONTRACT_VERSION, "engagement_id": cover.get("Engagement", MISSING), "scenario_id": scenario,
        "deliverable": deliverable,
        "criteria": {"criteria_set_id": set_id.group(1).strip() if set_id else MISSING, "criteria_sections": CRITERIA_FLOOR,
                     "source": "skill:criteria-retrieve", "citation": f"demo-data/{scenario}/raw/qrm-gate-criteria-extract.md"},
        "evidence_set": evidence,
        "prior_findings": parse_prior(read_text(os.path.join(raw, "prior-review-findings.md"))),
        "findings": [], "escalations": [],
        "provenance": {"engines": [], "demo_scenario": scenario},
        "_blocks": blocks, "_evidence_lines": evidence_lines,
    }


def numbers_in(text):
    return {float(token.replace(",", "")) for token in NUMBER.findall(text)}


def location_problems(label, location, blocks):
    block = blocks.get((location.get("page"), location.get("paragraph")))
    if block is None:
        return [f"{label}: draft has no paragraph {location.get('paragraph')} on page {location.get('page')}"]
    if not (block["section"] or "").startswith(location.get("section") or "\0"):
        return [f"{label}: page {location['page']} paragraph {location['paragraph']} is under {block['section']!r}, not {location.get('section')!r}"]
    return []


def compare_value(path, expected, actual, problems):
    if expected is MISSING:
        problems.append(f"{path}: value {actual!r} has no raw source")
    elif path.rsplit(".", 1)[-1] in ORDER_FREE and isinstance(expected, list) and isinstance(actual, list):
        if sorted(expected) != sorted(actual):
            problems.append(f"{path}: raw pack gives {sorted(expected)!r}, review input has {sorted(actual)!r}")
    elif expected != actual:
        problems.append(f"{path}: raw pack gives {expected!r}, review input has {actual!r}")


def compare_object(path, expected, actual, judgement, problems):
    if not isinstance(actual, dict):
        problems.append(f"{path}: expected an object")
        return
    for key in sorted(set(expected) | set(actual)):
        if key in judgement:
            continue
        if key not in actual:
            problems.append(f"{path}.{key}: raw pack gives {expected[key]!r} but the review input omits it")
        elif key not in expected:
            problems.append(f"{path}.{key}: value {actual[key]!r} is neither derived from the raw pack nor a declared ingest judgement")
        elif key in REGISTER_IDS and isinstance(expected[key], list) and isinstance(actual[key], list):
            compare_list(f"{path}.{key}", expected[key], actual[key], REGISTER_IDS[key], set(), problems)
        else:
            compare_value(f"{path}.{key}", expected[key], actual[key], problems)


def compare_list(path, expected, actual, key, judgement, problems):
    if not isinstance(actual, list):
        problems.append(f"{path}: raw pack gives a list of {len(expected)}, review input has {actual!r}")
        return
    want, have = [item[key] for item in expected], [item.get(key) for item in actual if isinstance(item, dict)]
    if want != have:
        problems.append(f"{path}: raw pack gives {want!r}, review input has {have!r}")
        return
    for index, (exp, act) in enumerate(zip(expected, actual)):
        compare_object(f"{path}[{index}]", exp, act, judgement, problems)


def assertion_problems(index, assertion, blocks, evidence_lines):
    label = f"assertions[{index}] {assertion.get('assertion_id')}"
    location = assertion.get("location") or {}
    problems = location_problems(label, location, blocks)
    block = blocks.get((location.get("page"), location.get("paragraph")))
    allowed = JUDGEMENT_KEYS["assertion"] | {"text", "evidence_ids", "sample_size", "population_size", "source", "citation"}
    problems += [f"{label}.{key}: value is neither derived from the raw pack nor a declared ingest judgement" for key in sorted(set(assertion) - allowed)]
    if block and assertion.get("text", "").rstrip(".") not in block["text"]:
        problems.append(f"{label}: text is not quoted from page {location['page']} paragraph {location['paragraph']}")
    if assertion.get("citation") != f"draft-deliverable.md p{location.get('page')} para{location.get('paragraph')}":
        problems.append(f"{label}: citation {assertion.get('citation')!r} does not match its location")
    if assertion.get("source") != "skill:deliverable-ingest":
        problems.append(f"{label}: source must be skill:deliverable-ingest")
    unknown = [eid for eid in assertion.get("evidence_ids") or [] if eid not in evidence_lines]
    if unknown:
        problems.append(f"{label}: evidence IDs {unknown} are not in the evidence index")
    context = (block["text"] if block else "") + " " + " ".join(evidence_lines.get(eid, "") for eid in assertion.get("evidence_ids") or [])
    for key in ("sample_size", "population_size"):
        value = assertion.get(key)
        if value is not None and float(value) not in numbers_in(context):
            problems.append(f"{label}.{key}: {value} appears in neither the located paragraph nor a linked evidence entry")
    for key in ("hedging_present", "limitation_present", "stated_basis", "scope_aligned"):
        if key in assertion and not isinstance(assertion[key], bool):
            problems.append(f"{label}.{key}: ingest judgement must be true/false")
    return problems


def compare(scenario_dir, payload):
    """Return a list of human-readable differences between the raw pack and a review-input payload."""
    derived = derive(scenario_dir)
    blocks, evidence_lines = derived.pop("_blocks"), derived.pop("_evidence_lines")
    problems = []
    for key in ("contract_version", "engagement_id", "scenario_id", "findings", "escalations"):
        compare_value(key, derived[key], payload.get(key), problems)
    compare_object("deliverable", derived["deliverable"], payload.get("deliverable"), JUDGEMENT_KEYS["deliverable"], problems)
    compare_object("criteria", derived["criteria"], payload.get("criteria"), JUDGEMENT_KEYS["criteria"], problems)
    compare_list("evidence_set", derived["evidence_set"], payload.get("evidence_set"), "evidence_id", set(), problems)
    compare_list("prior_findings", derived["prior_findings"], payload.get("prior_findings"), "finding_id", JUDGEMENT_KEYS["prior_finding"], problems)
    compare_object("provenance", derived["provenance"], payload.get("provenance"), {"generated_at"}, problems)
    deliverable = derived["deliverable"]
    for name in ("brand_checks", "licensed_content"):
        for index, item in enumerate(deliverable[name] or []):
            problems += location_problems(f"deliverable.{name}[{index}]", item["location"], blocks)
    for index, item in enumerate(derived["prior_findings"]):
        problems += location_problems(f"prior_findings[{index}]", item["location"], blocks)
    for index, assertion in enumerate(payload.get("assertions") or []):
        problems += assertion_problems(index, assertion, blocks, evidence_lines)
    return problems


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scenarios = argv or [os.path.join(root, "demo-data", name) for name in sorted(os.listdir(os.path.join(root, "demo-data")))]
    failed = False
    for scenario_dir in scenarios:
        with open(os.path.join(scenario_dir, "review-input.json"), encoding="utf-8") as fh:
            problems = compare(scenario_dir, json.load(fh))
        print(f"{os.path.basename(os.path.normpath(scenario_dir))}: {'derives from its raw pack' if not problems else f'{len(problems)} difference(s)'}")
        for problem in problems:
            print("  - " + problem)
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
