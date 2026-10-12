"""Fail-closed input handling shared by the staffing engines (byte-identical in every scripts/ folder).

Clean one-line input errors that never echo a value or a supplied path, strict JSON loading
(duplicate keys, non-finite numbers and deep nesting refused), typed field access, one canonical
form for every name and ID comparison, reserved display labels, and atomic LF output writes.
"""
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from datetime import date, datetime

MAX_JSON_DEPTH = 64
MAX_INPUT_BYTES = 20 * 1024 * 1024
MARKER_PREFIX = "[FLAGGED:"


class InputError(Exception):
    """A malformed input; the message names a field path or a label, never a value or a file path."""


def need(condition, message):
    if not condition:
        raise InputError(message)


def run(main):
    """Run an engine main(); any input error or unexpected failure is one clean line and exit 2."""
    try:
        return main()
    except InputError as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 2
    except RecursionError:
        print("error: input nested too deeply; fail closed", file=sys.stderr, flush=True)
        return 2
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - fail closed without a traceback or an echoed value
        print(f"error: unexpected {type(error).__name__} while processing input; fail closed",
              file=sys.stderr, flush=True)
        return 2


_JSON_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"?|[\[\]{}]')


def _depth_ok(text):
    depth = 0
    for token in _JSON_TOKEN.finditer(text):
        char = token.group(0)
        if char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                return False
        elif char in "]}":
            depth -= 1
    return True


def _unique_object(label):
    def hook(pairs):
        seen = set()
        for key, _value in pairs:
            folded = canonical(key)
            need(folded not in seen,
                 f"{label}: an object repeats a member name (not repeated); the file is ambiguous")
            seen.add(folded)
        return dict(pairs)
    return hook


def _no_constant(_name):
    raise InputError("non-finite number (NaN or Infinity) is not valid JSON")


def load_json(path, label):
    """Load one JSON input; every failure is an InputError naming only ``label``."""
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_INPUT_BYTES + 1)
    except OSError:
        raise InputError(f"{label}: file missing or unreadable") from None
    need(len(raw) <= MAX_INPUT_BYTES, f"{label}: file larger than {MAX_INPUT_BYTES} bytes")
    need(raw.strip(), f"{label}: file is empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InputError(f"{label}: not UTF-8 text") from None
    need(_depth_ok(text), f"{label}: JSON nested deeper than {MAX_JSON_DEPTH} levels")
    try:
        document = json.loads(
            text, object_pairs_hook=_unique_object(label), parse_constant=_no_constant
        )
    except json.JSONDecodeError as error:
        raise InputError(f"{label}: not valid JSON (line {error.lineno})") from None
    need(isinstance(document, dict), f"{label}: top level must be a JSON object")
    return document


def write_json(path, payload):
    """Write ``json.dumps(payload, indent=2)`` with LF line endings, atomically (temp file + replace)."""
    data = json.dumps(payload, indent=2).encode("utf-8")
    folder = os.path.dirname(os.path.abspath(path))
    try:
        handle, temp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=folder)
    except OSError:
        raise InputError("output folder missing or not writable") from None
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(temp_path, path)
    except OSError:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise InputError("output file could not be written") from None


# One canonical form for every name, ID and header comparison (output keeps the original value).
def canonical(value):
    text = unicodedata.normalize("NFKC", str(value))
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    return " ".join(text.casefold().split())


def id_key(value):
    """Canonical ID: canonical() with '-', '_', '.' and whitespace folded. Blank IDs return None."""
    if value is None or isinstance(value, bool) or not isinstance(value, str):
        return None
    folded = re.sub(r"[\s\-_.\u2010-\u2015\u2212]+", "-", canonical(value)).strip("-")
    return folded or None


RESERVED_WORDS = {
    "unknown", "unknown candidate", "unknown role", "none", "null", "n/a", "na", "tbd", "redacted",
    "withheld", "flagged", "anonymous", "candidate", "role", "bench record", "role record",
    "citation unknown",
}


def has_marker(value):
    return isinstance(value, str) and MARKER_PREFIX.casefold() in canonical(value)


def is_reserved_label(value):
    """True for display fallbacks and marker forms the engines emit; such values are never data."""
    if not isinstance(value, str):
        return False
    folded = canonical(value)
    if has_marker(value) or folded in RESERVED_WORDS:
        return True
    return bool(re.fullmatch(r"[<\[(].*[>\])]", folded))


# Typed field access; ``where`` is a field path such as roles[0].role_id.
_KINDS = {
    "obj": (dict, "an object"),
    "list": (list, "an array"),
    "str": (str, "a string"),
    "bool": (bool, "true or false"),
}


def kind_of(value, kind):
    if kind == "num":
        return is_num(value)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _KINDS[kind][0])


def _kind_name(kind):
    return {"num": "a number", "int": "an integer"}.get(kind) or _KINDS[kind][1]


def is_num(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def field(obj, key, kind, where, required=True, nullable=False):
    """Return obj[key] checked against ``kind``; absent/None only when allowed. Never coerces."""
    need(isinstance(obj, dict), f"{where} must be an object")
    path = f"{where}.{key}" if where else key
    if key not in obj:
        need(not required, f"{path} is required")
        return None
    value = obj[key]
    if value is None:
        need(nullable or not required, f"{path} must not be null")
        return None
    need(kind_of(value, kind), f"{path} must be {_kind_name(kind)}")
    return value


def text_list(obj, key, where, required=True):
    """A list of non-reserved strings (absent only when not required; never null)."""
    path = f"{where}.{key}" if where else key
    values = field(obj, key, "list", where, required=required)
    if values is None:
        return None
    for index, item in enumerate(values):
        need(isinstance(item, str), f"{path}[{index}] must be a string")
    return values


def check_id(value, path):
    need(isinstance(value, str), f"{path} must be a string identifier")
    need(id_key(value) is not None, f"{path} must not be blank")
    need(not is_reserved_label(value), f"{path} uses a reserved label form")
    return value


def check_name(value, path):
    need(isinstance(value, str) and value.strip(), f"{path} must be a non-blank string")
    need(not is_reserved_label(value), f"{path} uses a reserved label form")
    return value


def check_pct(value, path):
    need(is_num(value), f"{path} must be a number")
    need(0 <= value <= 100, f"{path} must be between 0 and 100")
    return value


def check_confidence(value, path):
    need(is_num(value), f"{path} must be a number")
    need(0 <= value <= 1, f"{path} must be between 0 and 1")
    return value


def check_date(value, path):
    need(isinstance(value, str), f"{path} must be a YYYY-MM-DD date")
    try:
        need(len(value) == 10, f"{path} must be a YYYY-MM-DD date")
        return date.fromisoformat(value)
    except ValueError:
        raise InputError(f"{path} must be a YYYY-MM-DD date") from None


_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")


def check_timestamp(value, path):
    need(isinstance(value, str) and _TIMESTAMP_RE.fullmatch(value),
         f"{path} must be an ISO 8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    try:
        datetime.fromisoformat(value[:-1])
    except ValueError:
        raise InputError(f"{path} must be an ISO 8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)") from None
    return value


def duplicate_keys(values):
    """Canonical ID keys that occur more than once (blank keys are never equal to each other)."""
    seen, repeated = set(), []
    for value in values:
        key = id_key(value)
        if key is None:
            continue
        if key in seen and key not in repeated:
            repeated.append(key)
        seen.add(key)
    return repeated
