#!/usr/bin/env python3
"""contract_check - validate a packet against the shipped contract JSON (python3 stdlib only).

Every engine validates every input packet at entry against contracts/ps.time-expense-narrative-compliance.v1.json
(the copy shipped in its own skill folder) before it reads anything (signal_policy.validate_packet). A
violation is a ContractError: the engine writes no output. The walker supports the schema keywords the
contract uses - $ref (local #/definitions), type, enum, const, required, properties, additionalProperties,
propertyNames, items, pattern, minLength, minimum, maximum - and refuses to load a contract that uses any
other validation keyword, so a keyword it cannot enforce is never silently ignored (fail closed).

Rules: "number" is a finite int or float and never a boolean; "integer" is an int and never a boolean;
"pattern" is a regular-expression search, as in JSON Schema. Error messages name the field path, the rule
and the JSON type of the value - never the value itself, which is untrusted text.

This file ships as identical copies next to each engine (skills are self-contained);
tests/check_shared_copies.py fails when the copies drift.
"""
import functools
import json
import math
import os
import re

CONTRACT_FILE = "ps.time-expense-narrative-compliance.v1.json"
ANNOTATIONS = {"$schema", "$id", "title", "description", "definitions"}
KEYWORDS = {"$ref", "type", "enum", "const", "required", "properties", "additionalProperties", "propertyNames",
            "items", "pattern", "minLength", "minimum", "maximum"}
JSON_TYPES = {bool: "boolean", str: "string", int: "integer", float: "number", dict: "object", list: "array",
              type(None): "null"}


class ContractError(ValueError):
    """The packet violates the contract, or the contract itself cannot be used (fail closed)."""


def contract_path(script_dir):
    """The contract shipped with the skill (skills/<skill>/contracts/), else the plugin-level copy."""
    current = os.path.abspath(script_dir)
    for _ in range(4):
        candidate = os.path.join(current, "contracts", CONTRACT_FILE)
        if os.path.isfile(candidate):
            return candidate
        current = os.path.dirname(current)
    raise ContractError(f"contract {CONTRACT_FILE} not found next to the engine; reinstall the skill")


def _check_keywords(schema, where):
    if isinstance(schema, dict):
        unknown = set(schema) - KEYWORDS - ANNOTATIONS
        if unknown:
            raise ContractError(f"contract uses unsupported keyword(s) {', '.join(sorted(unknown))} at {where}")
        for key, value in schema.items():
            if key in ("properties", "definitions"):
                for name, sub in value.items():
                    _check_keywords(sub, f"{where}/{key}/{name}")
            elif key in ("items", "additionalProperties", "propertyNames") and isinstance(value, dict):
                _check_keywords(value, f"{where}/{key}")


@functools.lru_cache(maxsize=8)
def load_contract(path):
    try:
        with open(path, encoding="utf-8") as fh:
            schema = json.load(fh)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read contract {os.path.basename(path)}: {exc}") from exc
    if not isinstance(schema, dict):
        raise ContractError(f"contract {os.path.basename(path)} is not a JSON object")
    _check_keywords(schema, "#")
    return schema


def json_type(value):
    return JSON_TYPES.get(type(value), type(value).__name__)


def _is(value, kind):
    if kind == "number":
        return type(value) in (int, float) and math.isfinite(value)
    if kind == "integer":
        return type(value) is int
    return json_type(value) == kind


def _resolve(schema, root):
    seen = 0
    while "$ref" in schema:
        ref = schema["$ref"]
        if not (isinstance(ref, str) and ref.startswith("#/definitions/")) or seen > 16:
            raise ContractError(f"contract reference {ref!r} cannot be resolved")
        schema = (root.get("definitions") or {}).get(ref[len("#/definitions/"):])
        if not isinstance(schema, dict):
            raise ContractError(f"contract reference {ref!r} cannot be resolved")
        seen += 1
    return schema


def _fail(where, rule, value):
    raise ContractError(f"invalid input: {where} must be {rule}, got {json_type(value)} "
                        "(the contract is enforced in full; nothing is coerced)")


def validate(value, schema, root, where="packet"):
    """Raise ContractError at the first violation of schema (resolved against root) by value."""
    schema = _resolve(schema, root)
    if set(schema) - KEYWORDS - ANNOTATIONS:
        raise ContractError(f"contract uses an unsupported keyword at {where}; the walker cannot enforce it (fail closed)")
    kinds = schema.get("type")
    if kinds is not None:
        kinds = [kinds] if isinstance(kinds, str) else list(kinds)
        if not any(_is(value, k) for k in kinds):
            _fail(where, " or ".join(kinds), value)
    if "const" in schema and (value != schema["const"] or type(value) is not type(schema["const"])):
        raise ContractError(f"invalid input: {where} must be the contract constant (fail closed)")
    if "enum" in schema and not any(value == v and type(value) is type(v) for v in schema["enum"]):
        raise ContractError(f"invalid input: {where} must be one of {', '.join(map(str, schema['enum']))}; an "
                            f"unrecognised {json_type(value)} value is rejected (fail closed)")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            _fail(where, f"a string of at least {schema['minLength']} character(s)", value)
        if "pattern" in schema and not re.search(schema["pattern"], value):
            _fail(where, f"a string matching the contract pattern {schema['pattern']}", value)
    if _is(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            _fail(where, f"a number >= {schema['minimum']}", value)
        if "maximum" in schema and value > schema["maximum"]:
            _fail(where, f"a number <= {schema['maximum']}", value)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ContractError(f"invalid input: {where} is missing required field '{key}'")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        names = schema.get("propertyNames")
        for key, item in value.items():
            if names is not None:
                validate(key, names, root, f"{where} key")
            if key in properties:
                validate(item, properties[key], root, f"{where}.{key}")
            elif extra is False:
                raise ContractError(f"invalid input: {where} has a field the contract does not allow")
            elif isinstance(extra, dict):
                validate(item, extra, root, f"{where}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], root, f"{where}[{i}]")


def validate_packet(packet, script_dir):
    """Validate a whole packet against the contract shipped with the engine in script_dir."""
    root = load_contract(contract_path(script_dir))
    validate(packet, root, root)
    return packet


def string_paths(schema, root, where="packet"):
    """Every field path whose value may be a string: [(path, leaf schema)]. Array items are written "[]"."""
    schema = _resolve(schema, root)
    out = []
    kinds = schema.get("type")
    kinds = [kinds] if isinstance(kinds, str) else list(kinds or [])
    if "string" in kinds or (not kinds and ("enum" in schema or "const" in schema or "pattern" in schema)):
        out.append((where, schema))
    for key, sub in schema.get("properties", {}).items():
        out += string_paths(sub, root, f"{where}.{key}")
    if isinstance(schema.get("items"), dict):
        out += string_paths(schema["items"], root, f"{where}[]")
    if isinstance(schema.get("additionalProperties"), dict):
        out += string_paths(schema["additionalProperties"], root, f"{where}.*")
    return out
