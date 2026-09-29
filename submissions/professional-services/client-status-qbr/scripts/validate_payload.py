#!/usr/bin/env python3
"""Validate a ps.client-status-qbr.v1 payload against the shipped contract.

Standard library only - no jsonschema, no PyYAML, nothing to install. Supports the
subset of JSON Schema the contract actually uses: $ref, definitions, type (single or
list), required, properties, additionalProperties, items, enum, oneOf, minimum,
maximum and pattern.

Usage:
    python "$SKILL_DIR/scripts/validate_payload.py" --input "$RUN_DIR/status-input.json"
    python "$SKILL_DIR/scripts/validate_payload.py" --input "$RUN_DIR/variance.json" --hop variance-calc

Exit codes:
    0  payload is valid for the requested hop
    1  payload is invalid - every problem is printed, one per line
    2  the payload or the contract could not be read

Every error line names the JSON path, what was expected and which skill is
responsible for populating it, so the fix is unambiguous.
"""

import argparse
import datetime
import json
import math
import os
import re
import sys

CONTRACT_NAME = "ps.client-status-qbr.v1"
DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Which skill populates which top-level block. Used to make errors actionable.
OWNER = {
    "contract_version": "plan-retrieve",
    "engagement": "plan-retrieve",
    "reporting_period": "plan-retrieve",
    "plan": "plan-retrieve",
    "prior_status": "plan-retrieve",
    "risks": "plan-retrieve",
    "decisions": "plan-retrieve",
    "actions": "plan-retrieve",
    "budget": "burn-pull",
    "variance_summary": "variance-calc",
    "aged_items": "risk-summarize",
    "draft": "status-draft",
    "settings": "the skill the user asked (variance-calc or risk-summarize)",
    "escalations": "any skill",
    "provenance": "any skill",
}

# Published threshold defaults (status-reporting-rules.md #2-#5). Each pair must keep
# amber below red once a user override is merged over these (#8.1).
THRESHOLD_DEFAULTS = {
    "schedule_amber_days": 5,
    "schedule_red_days": 10,
    "budget_amber_pct": 5.0,
    "budget_red_pct": 10.0,
    "scope_amber_open_items": 1,
    "scope_red_open_items": 3,
    "risk_stale_days": 45,
    "risk_critical_days": 90,
    "decision_overdue_days": 7,
    "action_overdue_days": 7,
}
THRESHOLD_PAIRS = [
    ("schedule_amber_days", "schedule_red_days"),
    ("budget_amber_pct", "budget_red_pct"),
    ("scope_amber_open_items", "scope_red_open_items"),
    ("risk_stale_days", "risk_critical_days"),
]
# Rules that can never be set from conversation (#8.2). Named here so a user request
# for one gets a plain refusal rather than a generic "not declared" line.
FIXED_RULES = {
    "confidence_floor": "#1.3",
    "include_unbilled_wip": "#3.3",
    "rebaseline_check": "#2.3",
    "rebaseline_check_required": "#2.3",
    "client_blocker_reclassifies": "#5.5",
    "draft_only": "#7",
}


def check_settings(payload, errors):
    settings = payload.get("settings")
    if not isinstance(settings, dict):
        return
    thresholds = settings.get("thresholds")
    if not isinstance(thresholds, dict):
        return
    for key in thresholds:
        if key.lower() in FIXED_RULES:
            errors.append(
                f"$.settings.thresholds.{key}: {key} is a fixed rule "
                f"(status-reporting-rules.md {FIXED_RULES[key.lower()]}) and cannot be changed "
                "in conversation (#8.2) - remove it and tell the user it is fixed"
            )
    merged = dict(THRESHOLD_DEFAULTS)
    merged.update(
        {k: v for k, v in thresholds.items() if k in THRESHOLD_DEFAULTS and TYPE_CHECKS["number"](v)}
    )
    for amber, red in THRESHOLD_PAIRS:
        if merged[amber] >= merged[red]:
            errors.append(
                f"$.settings.thresholds: {amber} ({merged[amber]}) must be below {red} "
                f"({merged[red]}) once the published defaults are filled in (#8.1) - ask the "
                "user for a consistent pair"
            )

# The blocks each hop must have present once it has done its own work. Each entry
# lists what the hop needs from upstream plus the block it is itself responsible
# for producing, so a hand-off can be checked in one call.
HOPS = {
    "plan-retrieve": [
        "contract_version",
        "engagement",
        "reporting_period",
        "plan",
        "risks",
        "decisions",
        "actions",
    ],
    "burn-pull": ["contract_version", "engagement", "reporting_period", "budget"],
    "variance-calc": ["contract_version", "plan", "budget", "variance_summary"],
    # Ageing a RAID register needs the register and a date to measure against, not
    # the finance export. Requiring variance_summary here stopped a user who had not
    # yet received the burn export from ageing risks at all.
    "raid-ready": [
        "contract_version",
        "reporting_period",
        "risks",
        "decisions",
        "actions",
    ],
    "risk-summarize": ["contract_version", "reporting_period", "aged_items"],
    # The advertised variance-only draft genuinely has no RAID section, so it must
    # not be asked for aged_items.
    "variance-only-draft": ["contract_version", "variance_summary"],
    "status-draft": ["contract_version", "variance_summary", "aged_items"],
}

# Hops at or after variance-calc run the engines, so by then every escalation a
# skill wrote must have been turned into a record.
RECORDED_ESCALATION_HOPS = ("variance-calc", "risk-summarize", "status-draft")


def check_escalations(payload, hop, errors):
    """Guard the escalation lifecycle across a hand-off.

    Two failures this catches, both of which were silent before: an engine dropping
    a structured escalation on the floor, and a blocker marked resolved without a
    named person or a recorded outcome.
    """
    records = payload.get("escalation_records", [])
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not record.get("resolved_at"):
            continue
        if not (record.get("resolved_by") and record.get("resolution")):
            errors.append(
                f"$.escalation_records[{index}]: resolved_at is set without resolved_by "
                "and resolution - a blocker is cleared only by a named person and a "
                "recorded outcome (status-reporting-rules.md #6.4)"
            )

    # Upstream hops (burn-pull, plan-retrieve) raise object-form escalations before any
    # engine has produced escalation_records[], so they are exempt. Everything else is
    # checked - including runs with no --hop at all, because gating the guard purely on a
    # label meant forgetting the flag silently disarmed the one check that catches a
    # dropped escalation.
    if hop not in RECORDED_ESCALATION_HOPS and "escalation_records" not in payload:
        return
    recorded = {
        record.get("message")
        for record in records
        if isinstance(record, dict)
    }
    for index, entry in enumerate(payload.get("escalations", [])):
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        if isinstance(message, str) and message not in recorded:
            errors.append(
                f"$.escalations[{index}]: the structured escalation {message[:60]!r} has no "
                "matching entry in escalation_records[] - an engine dropped it during the "
                "hand-off; every escalation raised upstream must survive to the internal "
                "review (status-reporting-rules.md #6.2, #6.3)"
            )


def find_contract(explicit=None):
    """Resolve the contract next to this script, so it works from any cwd."""
    if explicit:
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "contracts", f"{CONTRACT_NAME}.json"),
        os.path.join(here, "contracts", f"{CONTRACT_NAME}.json"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return os.path.normpath(candidate)
    return None


def resolve(schema, root):
    seen = 0
    while "$ref" in schema:
        seen += 1
        if seen > 20:
            raise ValueError("contract contains a circular $ref")
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"contract uses an unsupported $ref {ref!r}")
        node = root
        for part in ref[2:].split("/"):
            node = node[part]
        schema = node
    return schema


def reject_non_finite(token):
    """json.load accepts the bare tokens NaN, Infinity and -Infinity by default.
    They are not valid JSON and no downstream consumer handles them, so refuse
    the file rather than letting a non-finite value into a RAG comparison."""
    raise ValueError(
        f"{token} is not valid JSON. A budget or schedule figure came through as a "
        "non-finite number - usually an empty or text cell in the source export. Fix "
        "the source value and re-run."
    )


def is_finite_number(value):
    """NaN and Infinity are floats, so a bare isinstance check lets them through.
    NaN then compares False against every threshold and reads as GREEN - an empty
    WIP cell written by pandas is enough to turn a red budget green. Reject both
    here so a non-finite amount can never reach a RAG comparison."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": is_finite_number,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def type_name(value):
    for name in ("null", "boolean", "integer", "number", "string", "array", "object"):
        if TYPE_CHECKS[name](value):
            return name
    return type(value).__name__


def check_format(value, schema, path, errors):
    """Enforce the one format the contract relies on: ISO dates.

    A blank string is rejected as well as a malformed one. Blank is the shape that
    silently ages an item as "no date recorded" further down the chain, so it has to
    be stopped at the hand-off rather than interpreted later.
    """
    if schema.get("format") != "date" or not isinstance(value, str):
        return
    # date.fromisoformat() alone is too permissive on Python >= 3.11: it accepts
    # "20260920" and "2026-W38-7", neither of which is what the contract promises.
    # Check the literal shape first so the message and the contract agree.
    if not DATE_SHAPE.match(value):
        errors.append(
            f"{path}: {value!r} is not an ISO date (YYYY-MM-DD) - use null if it is unknown, "
            "never a blank string and never a guess"
        )
        return
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        errors.append(
            f"{path}: {value!r} is not a real calendar date (YYYY-MM-DD) - use null if it is "
            "unknown, never a blank string and never a guess"
        )


def validate(value, schema, root, path, errors):
    try:
        schema = resolve(schema, root)
    except (ValueError, KeyError) as exc:
        errors.append(f"{path}: contract could not be resolved ({exc})")
        return

    if "oneOf" in schema:
        for option in schema["oneOf"]:
            trial = []
            validate(value, option, root, path, trial)
            if not trial:
                break
        else:
            allowed = " or ".join(
                str(resolve(o, root).get("type", "value")) for o in schema["oneOf"]
            )
            errors.append(f"{path}: expected {allowed}, found {type_name(value)}")
            return

    expected = schema.get("type")
    if expected is not None:
        allowed = [expected] if isinstance(expected, str) else list(expected)
        if not any(TYPE_CHECKS.get(name, lambda _v: True)(value) for name in allowed):
            errors.append(
                f"{path}: expected {' or '.join(allowed)}, found {type_name(value)}"
            )
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(
            f"{path}: {value!r} is not one of {', '.join(repr(o) for o in schema['enum'])}"
        )

    if isinstance(value, str) and "pattern" in schema:
        if not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {schema['pattern']}")

    check_format(value, schema, path, errors)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below the minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above the maximum {schema['maximum']}")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                top = path.split(".")[1].split("[")[0] if path != "$" else key
                owner = OWNER.get(top)
                hint = f" - populated by {owner}" if owner else ""
                errors.append(f"{path}.{key}: required field is missing{hint}")
        extra = schema.get("additionalProperties")
        for key, child in value.items():
            if key in properties:
                validate(child, properties[key], root, f"{path}.{key}", errors)
            elif isinstance(extra, dict):
                validate(child, extra, root, f"{path}.{key}", errors)
            elif extra is False:
                errors.append(f"{path}.{key}: field is not declared in the contract")

    if isinstance(value, list) and "items" in schema:
        for index, child in enumerate(value):
            validate(child, schema["items"], root, f"{path}[{index}]", errors)


def internal_field_paths(contract):
    """Field names the contract marks x_internal, e.g. engagement.manager.

    Read out of the contract rather than hard-coded here so that marking a new field
    internal is a one-line change in one file.
    """
    found = []

    def walk(node, path):
        if not isinstance(node, dict):
            return
        for name, spec in (node.get("properties") or {}).items():
            here = path + [name]
            if isinstance(spec, dict):
                if spec.get("x_internal"):
                    found.append(".".join(here))
                walk(spec, here)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, path + ["[]"])

    walk(contract, [])
    return found


# Rule #7.2. Each entry is (label, compiled pattern). Kept deliberately narrow: these must
# fire on real personal data and stay quiet on ordinary status prose, because a lint that
# cries wolf gets switched off and then protects nothing.
PERSONAL_DATA_PATTERNS = (
    ("an email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    (
        "a phone number",
        re.compile(r"(?<![\d-])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?![\d-])"),
    ),
    ("an IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    (
        "a bank or card number",
        re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    ),
)

# Text that is meaningful internally but must never appear in a client document.
INTERNAL_TEXT_PATTERNS = (
    (r"\bconfidence\b", "a confidence score"),
    (r"status-reporting-rules\.md|#\d\.\d", "a rules citation"),
    (
        r"\b(?:margin|internal cost|cost rate|day rate|charge rate|utili[sz]ation)\b",
        "internal cost or margin language",
    ),
)

# Name parts that are also ordinary words in a status pack. Matching these on a word
# boundary would fail every pack that mentions a dev environment or a design lead,
# and a lint that cries wolf gets switched off. Surnames are the real signal, so
# nothing here may be a surname - "Bell" and "Moreno" must still be caught.
NAME_PART_STOPWORDS = frozenset(
    {
        "and",
        "dev",
        "lead",
        "the",
        "van",
        "von",
    }
)

# Keys that carry per-person money or judgement. Aggregate equivalents are fine, which is
# why this matches the key rather than the value.
SENSITIVE_KEY = re.compile(
    r"(?:^|_)(?:salary|salaries|pay|payrate|day_rate|daily_rate|cost_rate|charge_rate|"
    r"bill_rate|hourly_rate|rate_card|bonus|compensation|iban|bank_account|account_number|"
    r"sort_code|routing_number|card_number|home_address|personal_email|personal_phone|"
    r"performance_rating|performance_comment)(?:$|_)",
    re.IGNORECASE,
)


def lint_personal_data(payload, errors):
    """Refuse a payload carrying individual-level personal or financial data (#7.2)."""

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                here = f"{path}.{key}"
                if SENSITIVE_KEY.search(key):
                    errors.append(
                        f"{here}: field name reads as individual pay, rate or personal "
                        "identifier data, which must never enter the payload "
                        "(status-reporting-rules.md #7.2). Report at engagement, team or "
                        "role level instead, or leave it out and escalate"
                    )
                walk(value, here)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, str):
            for label, pattern in PERSONAL_DATA_PATTERNS:
                if pattern.search(node):
                    errors.append(
                        f"{path}: value contains what looks like {label}, which is "
                        "personal data and must not be carried in the payload or the pack "
                        "(status-reporting-rules.md #7.2). Remove it at source; do not "
                        "mask it and carry on"
                    )
                    break

    walk(payload, "$")


def lint_client_pack(text, payload, contract, errors, internal_sources=()):
    """Check a drafted client-facing document for material that must not leave the firm.

    The engines cannot stop a model typing a manager's name into a narrative, but this can
    catch it before the document is shared, which is where rule #7.2 actually bites.
    """
    lowered = text.casefold()

    for path in internal_field_paths(contract):
        value = payload
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if not isinstance(value, str) or not value.strip():
            continue
        # A whole-value match is trivially evaded by writing "Mr Bell" or "Jon", so
        # test each name part on its own word boundary.
        for part in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", value):
            if part.casefold() in NAME_PART_STOPWORDS:
                continue
            if re.search(rf"\b{re.escape(part)}\b", text, re.IGNORECASE):
                errors.append(
                    f"client pack: contains {part!r}, part of the internal-only field "
                    f"{path}. Refer to this person by role instead "
                    "(status-reporting-rules.md #7.2)"
                )

    for label, pattern in PERSONAL_DATA_PATTERNS:
        match = pattern.search(text)
        if match:
            errors.append(
                f"client pack: contains what looks like {label} "
                f"({match.group(0)[:40]!r}) - remove it (#7.2)"
            )

    if re.search(r"\bengine:[A-Za-z_]+", text):
        errors.append(
            "client pack: cites an engine (engine:variance_calc / engine:item_age). Engine "
            "attributions belong in the internal review sheet, not the client document"
        )

    if "draft" not in lowered:
        errors.append(
            "client pack: no DRAFT label. Every pack this skill produces is a draft for human "
            "review and must say so before it is shared (status-reporting-rules.md #7.1)"
        )

    for pattern, label in INTERNAL_TEXT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            errors.append(
                f"client pack: contains {label} ({match.group(0)[:40]!r}) - internal only "
                "(status-reporting-rules.md #3.6, #7.2)"
            )

    # Escalations are written for the internal reviewer and routinely quote the very
    # material the client must not see, so reproducing one verbatim defeats the split.
    for record in payload.get("escalation_records", []):
        message = (record or {}).get("message", "") if isinstance(record, dict) else ""
        if len(message) > 40 and message[:60].casefold() in lowered:
            errors.append(
                f"client pack: reproduces escalation text verbatim ({message[:40]!r}). "
                "Escalations belong in internal-review.md"
            )
            break

    blocking = [
        record
        for record in payload.get("escalation_records", [])
        if isinstance(record, dict)
        and record.get("type") == "blocking"
        and not record.get("resolved_at")
    ]
    if blocking:
        stated = re.search(r"not for issue\W+(\d+)\s+blocking", lowered)
        if not stated or int(stated.group(1)) != len(blocking):
            errors.append(
                f"client pack: {len(blocking)} blocking escalation(s) are unresolved, so the "
                "pack must carry a NOT FOR ISSUE banner naming that exact count "
                f"(found {stated.group(1) if stated else 'no count'}) until they are "
                "resolved on the record (status-reporting-rules.md #6.4, #7.1)"
            )

    for source_path in internal_sources or ():
        overlap = shared_phrase(source_path, text, allowed=payload_vocabulary(payload))
        if overlap:
            errors.append(
                f"client pack: reproduces {overlap!r} verbatim from the internal source "
                f"{source_path}. Internal commentary must be restated, not quoted "
                "(status-reporting-rules.md #7.2, #7.3)"
            )


def payload_vocabulary(payload):
    """Text the client pack is *supposed* to reuse word for word.

    Milestone names, item titles and the engagement name appear in the internal source
    and in the pack because they are the shared nouns of the engagement, not because a
    model pasted the PM's commentary through. Without this the phrase check fires on
    "claims rules design sign-off" and the whole flag gets ignored.
    """
    collected = []

    def walk(node, internal):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, internal or key in INTERNAL_VOCABULARY_KEYS)
        elif isinstance(node, list):
            for value in node:
                walk(value, internal)
        elif isinstance(node, str) and not internal:
            collected.append(node)

    walk(payload, False)
    return " \n ".join(collected)


# Payload keys whose text is internal commentary, so it must never be treated as
# vocabulary the client pack is entitled to reuse.
INTERNAL_VOCABULARY_KEYS = frozenset(
    {"escalations", "escalation_records", "message", "resolution", "notes"}
)


def shared_phrase(source_path, text, length=5, allowed=""):
    """The first run of `length` words the client pack shares with an internal source.

    Catches a PM's own words being pasted through - "keep it green if possible" - which
    no keyword list can anticipate. Five words rather than six: the distinctive part of
    such a phrase is short, and a six-word window misses it as soon as the surrounding
    sentence is reworded, which is exactly what a model does when it paraphrases badly.
    """
    try:
        with open(source_path, "r", encoding="utf-8") as handle:
            source = handle.read()
    except OSError:
        return None

    def grams(raw):
        words = re.findall(r"[a-z0-9']+", raw.casefold())
        return {
            " ".join(words[i : i + length]): i
            for i in range(len(words) - length + 1)
        }

    source_grams = grams(source)
    if not source_grams:
        return None
    allowed_grams = grams(allowed) if allowed else {}
    for gram in grams(text):
        if gram in source_grams and gram not in allowed_grams:
            return gram
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Validate a ps.client-status-qbr.v1 payload against the shipped contract."
    )
    parser.add_argument("--input", required=True, help="payload JSON to validate")
    parser.add_argument(
        "--hop",
        choices=sorted(HOPS),
        help="also assert the blocks this hop needs are present",
    )
    parser.add_argument("--contract", help="override the contract path")
    parser.add_argument(
        "--client-pack",
        metavar="FILE",
        help=(
            "also lint a drafted client-facing document against the personal-data and "
            "internal-material boundary (status-reporting-rules.md #7.2)"
        ),
    )
    parser.add_argument(
        "--internal-source",
        metavar="FILE",
        action="append",
        default=[],
        help=(
            "an internal source file (e.g. raw/pm-email.txt). Fails if the client pack "
            "reproduces six or more consecutive words from it. Repeatable."
        ),
    )
    args = parser.parse_args()

    contract_path = find_contract(args.contract)
    if not contract_path or not os.path.exists(contract_path):
        print(
            "validate_payload: could not find the contract. Expected it at "
            f"../contracts/{CONTRACT_NAME}.json relative to this script. Pass --contract "
            "to point at it explicitly.",
            file=sys.stderr,
        )
        return 2

    try:
        with open(args.input, encoding="utf-8") as handle:
            payload = json.load(handle, parse_constant=reject_non_finite)
    except FileNotFoundError:
        print(f"validate_payload: no such file {args.input}", file=sys.stderr)
        return 2
    except ValueError as exc:
        # JSONDecodeError subclasses ValueError, so this catches both a malformed
        # file and a non-finite token surfaced by reject_non_finite.
        if isinstance(exc, json.JSONDecodeError):
            print(
                f"validate_payload: {args.input} is not valid JSON - {exc}. The previous "
                "skill most likely wrote prose into the file instead of a JSON object.",
                file=sys.stderr,
            )
        else:
            print(f"validate_payload: {args.input} - {exc}", file=sys.stderr)
        return 2

    with open(contract_path, encoding="utf-8") as handle:
        contract = json.load(handle)

    if not isinstance(payload, dict):
        print(
            f"validate_payload: {args.input} must be a JSON object, found "
            f"{type_name(payload)}. The previous skill wrote a bare value or a list "
            "instead of a contract payload - re-run it.",
            file=sys.stderr,
        )
        return 2

    errors = []
    found = payload.get("contract_version")
    if found != CONTRACT_NAME:
        errors.append(
            f"$.contract_version: expected {CONTRACT_NAME!r} but found {found!r} - "
            "run plan-retrieve first to build a valid payload"
        )

    # The contract identifier stays v1 while the schema only gains optional fields, so
    # it cannot catch a newer payload meeting an older plugin copy. The revision can:
    # a payload built by 1.6.0 checked against a 1.5.x contract is a stale install, not
    # a bad payload, and saying so is the difference between a fixable message and a
    # confusing list of unknown-field errors.
    contract_revision = contract.get("revision")
    payload_revision = payload.get("contract_revision")
    if (
        isinstance(contract_revision, int)
        and isinstance(payload_revision, int)
        and payload_revision > contract_revision
    ):
        errors.append(
            f"$.contract_revision: the payload was built against revision {payload_revision} "
            f"of {CONTRACT_NAME} but this plugin copy ships revision {contract_revision} - "
            "this copy of client-status-qbr is out of date; ask the user for the current "
            "plugin folder rather than editing the payload"
        )

    validate(payload, contract, contract, "$", errors)
    check_settings(payload, errors)
    check_escalations(payload, args.hop, errors)
    lint_personal_data(payload, errors)

    if args.client_pack:
        try:
            with open(args.client_pack, encoding="utf-8") as handle:
                lint_client_pack(
                    handle.read(), payload, contract, errors, args.internal_source
                )
        except FileNotFoundError:
            errors.append(
                f"--client-pack: no such file {args.client_pack} - draft the pack before "
                "linting it"
            )

    for block in HOPS.get(args.hop, []):
        if block not in payload:
            errors.append(
                f"$.{block}: required before/by the {args.hop} hop but absent - "
                f"populated by {OWNER.get(block, 'an earlier skill')}"
            )

    if errors:
        print(
            f"validate_payload: {len(errors)} problem(s) in {args.input}:", file=sys.stderr
        )
        for error in sorted(set(errors)):
            print(f"  - {error}", file=sys.stderr)
        print(
            "Do not continue the chain. Fix the payload at source or escalate the missing "
            "values to a human - never invent them.",
            file=sys.stderr,
        )
        return 1

    scope = f" for hop {args.hop}" if args.hop else ""
    print(f"validate_payload: {args.input} is valid against {CONTRACT_NAME}{scope}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
