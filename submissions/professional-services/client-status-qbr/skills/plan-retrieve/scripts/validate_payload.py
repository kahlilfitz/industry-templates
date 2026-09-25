#!/usr/bin/env python3
"""Validate a ps.client-status-qbr.v1 payload against the shipped contract.

Standard library only - no jsonschema, no PyYAML, nothing to install. Supports the
subset of JSON Schema the contract actually uses: $ref, definitions, type (single or
list), required, properties, additionalProperties, items, enum, oneOf, minimum,
maximum and pattern.

Usage:
    python "$SKILL_DIR/scripts/validate_payload.py" --input ./status-run/status-input.json
    python "$SKILL_DIR/scripts/validate_payload.py" --input ./status-run/variance.json --hop variance-calc

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
    "escalations": "any skill",
    "provenance": "any skill",
}

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
    "risk-summarize": ["contract_version", "variance_summary", "aged_items"],
    "status-draft": ["contract_version", "variance_summary", "aged_items"],
}


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


TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
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
            payload = json.load(handle)
    except FileNotFoundError:
        print(f"validate_payload: no such file {args.input}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(
            f"validate_payload: {args.input} is not valid JSON - {exc}. The previous skill "
            "most likely wrote prose into the file instead of a JSON object.",
            file=sys.stderr,
        )
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

    validate(payload, contract, contract, "$", errors)

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
