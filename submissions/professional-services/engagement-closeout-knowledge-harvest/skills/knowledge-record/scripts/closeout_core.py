#!/usr/bin/env python3
"""closeout_core - shared rules for the engagement-closeout-knowledge-harvest engines.

One byte-identical copy ships in the scripts/ folder of asset-identify, lesson-cluster,
sanitize-check and knowledge-record. It holds the strict loader, the input contract validator, the
embedded-instruction screen (through the vendored shared steering_guard.py), the three deterministic
stages, the knowledge-record skeleton and the whole-document replay every later stage runs.
Section numbers cite references/reuse-asset-rubric.md, lesson-taxonomy.md and
confidentiality-sanitisation-rules.md. No network, no model calls, no side effects beyond --out.
"""
import functools
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import steering_guard as sg  # noqa: E402  vendored byte for byte from shared/steering-guard

SCREENING_LABEL = f"steering_guard {sg.__version__} (shared, vendored) with the closeout hook profile"

CONTRACT = "ps.engagement-closeout-knowledge-harvest.v1"
ENGINE_VERSIONS = {
    "asset_identify": "asset_identify/1.0.3",
    "lesson_cluster": "lesson_cluster/1.0.3",
    "sanitize_check": "sanitize_check/1.0.3",
}

WITHHELD = "[withheld: embedded instruction held for review - see screening_holds]"
DRAFT_LABEL = "DRAFT - HUMAN REVIEW REQUIRED"
MAX_INPUT_BYTES = 5_000_000
MAX_DEPTH = 64

# Plugin vocabulary passes to the shared detector only through its documented hooks
# (confidentiality-sanitisation-rules.md #8.1). Closeout text never legitimately carries an e-mail
# address or URL, so any contact detail is treated as steering.
GUARD_HOOKS = {
    "extra_verdict_words": (
        "release candidate", "release ready", "cleared for reuse", "approved for reuse",
        "approved for external use", "sanitised", "sanitized", "publishable", "no redaction needed",
        "client approved", "internal reuse candidate", "satisfied", "met", "external use", "safe to publish",
        "safe to reuse", "publication ready", "cleared", "already reviewed",
        # QA round 2 closeout vocabulary (#8.1): "redaction complete" closes detector gap line 2;
        # "published" closes "mark/treat this record as published".
        "published", "redaction complete", "confidentiality cleared", "cleared for external use",
        "approved for publication",
    ),
    "extra_rule_nouns": (
        "confidentiality terms", "confidentiality rules", "sanitisation rules", "sanitization rules",
        "aggregation rule", "aggregation review", "redaction", "practice review", "client terms",
        "govern step", "sanitisation gate", "sanitisation check", "sanitization check", "confidentiality check",
        "redaction check", "client approval", "written approval",
        "knowledge base", "external use", "client consent", "consent requirement", "publication rule",
    ),
    "contact_is_steering": True,
}

# reuse-asset-rubric.md
GENERALISABILITY_WEIGHT = 0.35   # #1.1
EFFORT_WEIGHT = 0.25             # #2.1
SHELF_LIFE_WEIGHT = 0.20         # #3.1
DEPENDENCY_WEIGHT = 0.20         # #4.1
SHORTLIST_SCORE = 70             # #5.1
RETAIN_SCORE = 50                # #5.2
SCORING_CONFIDENCE_FLOOR = 0.70  # #5.1

# lesson-taxonomy.md
CLUSTER_KEYWORDS = {
    "delivery-governance": ["governance", "sign-off", "signoff", "decision", "escalation", "scope", "steerco", "owner"],
    "adoption-change": ["training", "adoption", "champion", "communications", "readiness", "change"],
    "data-integration": ["data", "migration", "integration", "environment", "api", "cutover", "defect"],
    "commercial-staffing": ["staffing", "budget", "contract", "margin", "partner", "resourcing"],
}
CATEGORY_CITATIONS = {
    "delivery-governance": "lesson-taxonomy.md #1.1",
    "adoption-change": "lesson-taxonomy.md #1.2",
    "data-integration": "lesson-taxonomy.md #1.3",
    "commercial-staffing": "lesson-taxonomy.md #1.4",
    "unclassified": "lesson-taxonomy.md #1.5",
}
HIGH_IMPACT_TERMS = ["blocker", "critical", "delayed", "rework", "executive", "go-live", "golive"]  # #2.1
MIN_CLUSTER_CONFIDENCE = 0.70  # #3.1

# confidentiality-sanitisation-rules.md
DIRECT_IDENTIFIER_MARKERS = {"client_name", "client_logo", "client_domain", "site_name", "project_codename"}  # #1.1
CLIENT_SPECIFIC_MARKERS = {"client_specific_configuration"}  # #1.3
NAMED_PERSON_MARKERS = {"named_individual", "named_person_blame"}  # #2.1, #2.2
COMMERCIAL_MARKERS = {"pricing", "contract_value", "revenue", "margin", "precise_headcount", "implementation_date"}  # #3.1
LICENSED_MARKERS = {"licensed_third_party_content", "vendor_screenshot", "benchmark_excerpt"}  # #4.1
PRODUCT_AGGREGATION_MARKERS = {"third_party_product", "named_vendor"}  # #4.2
AGGREGATION_TOKENS = {
    "sector", "region", "client_headcount", "go_live_date", "third_party_product", "named_vendor",
    "unique_architecture", "rare_operating_model", "distinctive_metric",
    "generic_operating_model", "generic_training_pattern",
}  # #5.3
KNOWN_MARKERS = (DIRECT_IDENTIFIER_MARKERS | CLIENT_SPECIFIC_MARKERS | NAMED_PERSON_MARKERS
                 | COMMERCIAL_MARKERS | LICENSED_MARKERS | PRODUCT_AGGREGATION_MARKERS)
AGGREGATION_MIN_TOKENS = 4  # #5.1
SANITISATION_CONFIDENCE_FLOOR = 0.80  # #6.1
DEFAULT_REVIEW_REQUIRED = True  # #6.2
BLAME_PATTERN = re.compile(r"\b(?:failed|fault|blamed|missed|caused)\b", re.IGNORECASE)  # #2.2
PERSON_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\s+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\b")

RELEASE = "RELEASE_CANDIDATE_SANITISED"
# Clearance-state precedence, most restrictive first (#7.3). An asset takes the first state that applies.
PRECEDENCE = (
    "HOLD_EMBEDDED_INSTRUCTION",
    "HOLD_IDENTITY_UNSCREENABLE",
    "HOLD_TERMS_UNAVAILABLE",
    "HOLD_UNRECOGNISED_MARKER",
    "HOLD_PERSONAL_DATA_REWRITE",
    "HOLD_RIGHTS_UNKNOWN",
    "HOLD_REDACTION_REQUIRED",
    "HOLD_AGGREGATION_RISK",
    "HOLD_LOW_CONFIDENCE",
    "HOLD_NOT_SHORTLISTED",
    RELEASE,
)

# ---------------------------------------------------------------------------------------------
# Errors, canonical forms and the strict loader
# ---------------------------------------------------------------------------------------------


class InputError(Exception):
    """A clean input error. The message names a field path and the expected shape; it never
    repeats a supplied value, file name or unknown member name (D17)."""


def strip_cf(text):
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def canon(text):
    """One canonical form for every comparison (A13): NFKC, no Cf characters, casefold, single spaces."""
    return " ".join(strip_cf(unicodedata.normalize("NFKC", strip_cf(text))).casefold().split())


def canon_id(text):
    """canon() with '-', '_', '.' and spaces folded away, for identifier comparisons (A13)."""
    return re.sub(r"[-_.\s]+", "", canon(text))


def words(text):
    return re.findall(r"[a-z0-9]+", canon(text))


ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
TOKEN_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
SOURCE_RE = re.compile(r"(skill|connector):[a-z0-9][a-z0-9_.-]{0,63}")
TS_RE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
DATE_RE = re.compile(r"\d{4}-\d\d-\d\d")
STATUSES = ("complete", "draft", "missing", "superseded")

# Label forms the engines emit or that downstream Mobilization reserves (D25): cluster and hold
# IDs, the knowledge-record ID suffix, hold IDs, file paths and positions, and display fallbacks.
_RESERVED_RE = re.compile(
    r"(?:lc|sh)[-_. ]?\d+"
    r"|.*[-_. ]kr[-_. ]draft"
    r"|hold(?:-[a-z0-9]+){2,}"
    r"|(?:raw|upstream|expected|demo-data)/.*|rendered order of .*"
    r"|[\w.-]+\.(?:csv|md|json|txt)\b.*"
    r"|(?:rows?|lines?|clauses?) \d+(?:(?: ?[-,] ?| and )\d+)*(?:\.\w+)?"
    r"|[\w.]*\[\d+\][\w.\[\]]*(?: .*)?"
    r"|\(blank [\w ]+\)|this client or matter|released knowledge asset .+|lesson: .*|<member>"
)


def reserved_label(value):
    text = canon(value)
    return bool(text) and bool(_RESERVED_RE.fullmatch(text))


def _no_duplicate_members(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise InputError("a JSON object repeats a member name (name not repeated); duplicate members are malformed")
        seen.add(key)
    return dict(pairs)


def _refuse_constant(_):
    raise InputError("a JSON number is NaN or Infinity; only finite numbers are accepted")


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise InputError("a JSON number is out of range; only finite numbers are accepted")
    return value


_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)


def _depth_ok(text):
    depth = 0
    for match in re.finditer(r"[\[\]{}]", _STRING_RE.sub('""', text)):
        if match.group() in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                return False
        else:
            depth -= 1
    return True


def load_json(path, label="input"):
    """Strict JSON load (A7, A11, A14): UTF-8, size cap, depth cap, no duplicate members, finite numbers."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_INPUT_BYTES + 1)
    except OSError:
        raise InputError(f"{label} file could not be read") from None
    if len(data) > MAX_INPUT_BYTES:
        raise InputError(f"{label} is larger than {MAX_INPUT_BYTES} bytes")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InputError(f"{label} is not UTF-8 text") from None
    if not _depth_ok(text):
        raise InputError(f"{label} nests JSON deeper than {MAX_DEPTH} levels")
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_members,
                          parse_constant=_refuse_constant, parse_float=_finite_float)
    except InputError:
        raise
    except (ValueError, RecursionError):
        raise InputError(f"{label} is not valid JSON") from None


def read_text(path, label, limit=1_000_000):
    try:
        with open(path, "rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        raise InputError(f"{label} file could not be read") from None
    if len(data) > limit:
        raise InputError(f"{label} is larger than {limit} bytes")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InputError(f"{label} is not UTF-8 text") from None


def write_text(path, text):
    """Atomic LF write: the target appears only when the whole output is ready (G3)."""
    directory = os.path.dirname(os.path.abspath(path))
    handle, temp = tempfile.mkstemp(dir=directory, prefix=".closeout-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as output:
            output.write(text)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.remove(temp)
        raise


def dump(doc):
    return json.dumps(doc, indent=2)


# ---------------------------------------------------------------------------------------------
# Field paths and value validators (D17: only contract vocabulary is ever named)
# ---------------------------------------------------------------------------------------------

CONTRACT_VOCAB = frozenset({
    "contract_version", "run_metadata", "generated_at", "demo_scenario", "engagement", "engagement_id",
    "title", "client_name", "client_descriptor", "sector", "region", "client_headcount", "go_live_date",
    "third_party_products", "confidence", "source", "citation", "artifacts", "artifact_id", "artifact_type",
    "required", "status", "owner", "candidate_assets", "asset_id", "asset_type", "description",
    "generalisability", "effort_to_recreate", "shelf_life_months", "client_dependency",
    "confidentiality_markers", "aggregation_tokens", "decision_log", "decision_id", "summary", "impact",
    "retrospective_inputs", "input_id", "text", "speaker_role", "named_people", "confidentiality_terms",
    "term_id", "escalations", "deliverable_index", "completeness_gap", "reusable_asset_shortlist",
    "reuse_score", "recommendation", "reuse_rationale", "clearance_state", "lesson_clusters", "cluster_id",
    "category", "priority_score", "review_candidate", "evidence_ids", "evidence_citations", "summary_seed",
    "sensitivity_signals", "evidence_id", "signal", "sanitisation_report", "overall_disposition", "findings",
    "target_type", "target_id", "disposition", "reason", "governance_note", "released_assets",
    "review_required", "held_assets", "lessons_for_draft", "rewrite_required", "drafting_guidance",
    "knowledge_record", "record_id", "engagement_context_guidance", "reusable_assets",
    "held_assets_summary", "lessons", "sanitisation_summary", "downstream_handoff", "consumer_template",
    "contract_fields", "handoff_note", "draft_label", "provenance", "engines", "input_escalations",
    "policies", "screening", "screening_holds", "hold_id", "path", "location", "family",
})


def seg(key):
    return key if key in CONTRACT_VOCAB else "<member>"


def _type_name(value):
    if isinstance(value, bool):
        return "true or false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, list):
        return "an array"
    return "an object"


def need_object(value, path):
    if type(value) is not dict:
        raise InputError(f"{path} must be a JSON object, got {_type_name(value)} (value not repeated)")
    return value


def need_list(value, path):
    if type(value) is not list:
        raise InputError(f"{path} must be a JSON array, got {_type_name(value)} (value not repeated)")
    return value


def check_members(obj, path, required, optional=()):
    allowed = set(required) | set(optional)
    for key in obj:
        if key not in allowed:
            raise InputError(f"{path}.{seg(key)} is not a member the contract allows here (name not repeated)")
    for key in required:
        if key not in obj:
            raise InputError(f"{path}.{key} is required (an absent member is not an empty one)")


def timestamp_ok(value):
    if type(value) is not str or not TS_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def date_ok(value):
    if type(value) is not str or not DATE_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _check_text(value, path, ctx, name=False):
    if type(value) is not str:
        raise InputError(f"{path} must be a string, got {_type_name(value)} (value not repeated)")
    if value == WITHHELD and ctx["replay"]:
        if path not in ctx["prior"]:
            raise InputError(f"{path} carries the withheld placeholder without a screening hold for that path (confidentiality-sanitisation-rules.md #8.4)")
        ctx["bound"].add(path)
        return
    if not value.strip():
        raise InputError(f"{path} must not be blank")
    if name and reserved_label(value):
        raise InputError(f"{path} is in a label form the engines reserve (value not repeated)")


def _check_ident(value, path):
    if type(value) is not str:
        raise InputError(f"{path} must be an identifier string, got {_type_name(value)} (value not repeated)")
    if not ID_RE.fullmatch(value):
        raise InputError(f"{path} must be 1-64 ASCII letters, digits, '.', '_' or '-' starting with a letter or digit (value not repeated)")
    if reserved_label(value):
        raise InputError(f"{path} is in a label form the engines reserve (value not repeated)")
    if id_hits(value):
        raise InputError(f"{path} reads as an instruction to the reviewer or tool (value not repeated)")
    if not id_shape_ok(value):
        raise InputError(f"{path} reads as a phrase, not an identifier (value not repeated)")


def _check_token(value, path):
    if type(value) is not str or not TOKEN_RE.fullmatch(value):
        raise InputError(f"{path} must be a lowercase marker token (letters, digits, '_'; value not repeated)")
    if id_hits(value):
        raise InputError(f"{path} reads as an instruction to the reviewer or tool (value not repeated)")


def _check_value(kind, value, path, ctx):
    if kind == "text":
        _check_text(value, path, ctx)
    elif kind == "name":
        _check_text(value, path, ctx, name=True)
    elif kind == "id":
        _check_ident(value, path)
    elif kind == "bool":
        if type(value) is not bool:
            raise InputError(f"{path} must be true or false, got {_type_name(value)} (value not repeated)")
    elif kind == "score5":
        if type(value) is not int or not 0 <= value <= 5:
            raise InputError(f"{path} must be a whole number from 0 to 5 (value not repeated)")
    elif kind == "months":
        if type(value) is not int or not 0 <= value <= 600:
            raise InputError(f"{path} must be a whole number of months from 0 to 600 (value not repeated)")
    elif kind == "headcount":
        if value is not None and (type(value) is not int or value < 0):
            raise InputError(f"{path} must be a non-negative whole number or null (value not repeated)")
    elif kind == "num01":
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise InputError(f"{path} must be a number from 0 to 1 (value not repeated)")
    elif kind == "source":
        if type(value) is not str or not SOURCE_RE.fullmatch(value):
            raise InputError(f"{path} must be skill:<name> or connector:<name>; engine: sources are reserved for the engines (value not repeated)")
        if id_hits(value):
            raise InputError(f"{path} reads as an instruction to the reviewer or tool (value not repeated)")
    elif kind == "status":
        if type(value) is not str or value not in STATUSES:
            raise InputError(f"{path} must be one of complete, draft, missing or superseded (value not repeated)")
    elif kind == "date":
        if not date_ok(value):
            raise InputError(f"{path} must be a calendar date YYYY-MM-DD (value not repeated)")
    elif kind in ("names", "texts", "tokens"):
        need_list(value, path)
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            if kind == "tokens":
                _check_token(item, item_path)
            else:
                _check_text(item, item_path, ctx, name=(kind == "names"))
    else:  # pragma: no cover - programming error
        raise AssertionError(kind)


# The input contract the first stage enforces (A1, A2, A5a, A15). (member, kind, required)
RECORD_SPECS = {
    "engagement": (
        ("engagement_id", "id", True), ("title", "name", True), ("client_name", "name", True),
        ("client_descriptor", "text", True), ("sector", "text", False), ("region", "text", False),
        ("client_headcount", "headcount", False), ("go_live_date", "date", False),
        ("third_party_products", "texts", False), ("confidence", "num01", True),
        ("source", "source", True), ("citation", "text", True),
    ),
    "artifacts": (
        ("artifact_id", "id", True), ("title", "name", True), ("artifact_type", "text", True),
        ("required", "bool", True), ("status", "status", True), ("owner", "name", True),
        ("confidence", "num01", True), ("source", "source", True), ("citation", "text", True),
    ),
    "candidate_assets": (
        ("asset_id", "id", True), ("title", "name", True), ("asset_type", "text", True),
        ("description", "text", True), ("generalisability", "score5", True),
        ("effort_to_recreate", "score5", True), ("shelf_life_months", "months", True),
        ("client_dependency", "score5", True), ("confidentiality_markers", "tokens", True),
        ("aggregation_tokens", "tokens", True), ("confidence", "num01", True),
        ("source", "source", True), ("citation", "text", True),
    ),
    "decision_log": (
        ("decision_id", "id", True), ("summary", "text", True), ("impact", "text", True),
        ("confidence", "num01", True), ("source", "source", True), ("citation", "text", True),
    ),
    "retrospective_inputs": (
        ("input_id", "id", True), ("speaker_role", "name", True), ("text", "text", True),
        ("named_people", "names", True), ("confidence", "num01", True), ("source", "source", True),
        ("citation", "text", True),
    ),
    "confidentiality_terms": (
        ("term_id", "id", True), ("summary", "text", True), ("confidence", "num01", True),
        ("source", "source", True), ("citation", "text", True),
    ),
}
ID_FIELDS = {
    "engagement": "engagement_id", "artifacts": "artifact_id", "candidate_assets": "asset_id",
    "decision_log": "decision_id", "retrospective_inputs": "input_id", "confidentiality_terms": "term_id",
}
RAW_ARRAYS = ("artifacts", "candidate_assets", "decision_log", "retrospective_inputs", "confidentiality_terms")
RAW_REQUIRED = ("contract_version", "engagement") + RAW_ARRAYS
RAW_OPTIONAL = ("run_metadata", "escalations")
ENGINE_SECTIONS = (
    "deliverable_index", "reusable_asset_shortlist", "lesson_clusters", "sanitisation_report",
    "released_assets", "held_assets", "lessons_for_draft", "knowledge_record", "provenance", "screening_holds",
)
STAGE_KEYS = {
    1: set(RAW_REQUIRED) | {"run_metadata", "escalations", "deliverable_index", "reusable_asset_shortlist",
                            "provenance", "screening_holds"},
}
STAGE_KEYS[2] = STAGE_KEYS[1] | {"lesson_clusters"}
STAGE_KEYS[3] = STAGE_KEYS[2] | {"sanitisation_report", "released_assets", "held_assets", "lessons_for_draft",
                                 "knowledge_record"}
STAGE_NAMES = {1: "asset_identify", 2: "lesson_cluster", 3: "sanitize_check"}


def _check_contract_version(doc):
    need_object(doc, "input")
    if "contract_version" not in doc:
        raise InputError("contract_version is required")
    if doc["contract_version"] != CONTRACT:
        raise InputError(f"wrong contract version (expected {CONTRACT}; value not repeated)")


def validate_input(doc, generated_at=None, prior=None):
    """Validate the engagement input (or the raw sections an intermediate carries) and return
    (input, timestamp). prior maps a carried placeholder's path to its screening hold (replay)."""
    _check_contract_version(doc)
    for key in doc:
        if key in ENGINE_SECTIONS:
            raise InputError(f"{key} is engine-owned and may not be supplied in the engagement input")
    check_members(doc, "input", (), RAW_REQUIRED + RAW_OPTIONAL)
    ctx = {"replay": prior is not None, "prior": prior or {}, "bound": set()}
    for name in RAW_ARRAYS:
        if name not in doc or type(doc[name]) is not list:
            raise InputError(f"missing or invalid required array: {name} (absent, null or another type is not an empty list)")
    if "engagement" not in doc or type(doc["engagement"]) is not dict:
        raise InputError("missing or invalid required object: engagement")

    timestamp = generated_at
    if generated_at is not None and not timestamp_ok(generated_at):
        raise InputError("--generated-at must be an ISO-8601 UTC timestamp YYYY-MM-DDTHH:MM:SSZ")
    run_metadata = {}
    if "run_metadata" in doc:
        run_metadata = need_object(doc["run_metadata"], "run_metadata")
        check_members(run_metadata, "run_metadata", (), ("generated_at", "demo_scenario"))
        if "generated_at" in run_metadata:
            if not timestamp_ok(run_metadata["generated_at"]):
                raise InputError("run_metadata.generated_at must be an ISO-8601 UTC timestamp YYYY-MM-DDTHH:MM:SSZ (value not repeated)")
            if timestamp is not None and timestamp != run_metadata["generated_at"]:
                raise InputError("--generated-at and run_metadata.generated_at disagree")
            timestamp = run_metadata["generated_at"]
        if "demo_scenario" in run_metadata:
            value = run_metadata["demo_scenario"]
            if type(value) is not str or not SLUG_RE.fullmatch(value) or id_hits(value):
                raise InputError("run_metadata.demo_scenario must be a lowercase slug (value not repeated)")
    if timestamp is None:
        raise InputError("run_metadata.generated_at is required (or pass --generated-at)")

    escalations = []
    if "escalations" in doc:
        need_list(doc["escalations"], "escalations")
        for index, item in enumerate(doc["escalations"]):
            _check_text(item, f"escalations[{index}]", ctx)
            if item == WITHHELD or item not in escalations:  # identical upstream escalations merge once (A8)
                escalations.append(item)

    def check_record(record, path, spec):
        need_object(record, path)
        check_members(record, path, [m for m, _, req in spec if req], [m for m, _, req in spec if not req])
        for member, kind, _ in spec:
            if member in record:
                _check_value(kind, record[member], f"{path}.{member}", ctx)

    check_record(doc["engagement"], "engagement", RECORD_SPECS["engagement"])
    evidence_ids = {}
    for name in RAW_ARRAYS:
        seen = {}
        for index, record in enumerate(doc[name]):
            path = f"{name}[{index}]"
            check_record(record, path, RECORD_SPECS[name])
            key = canon_id(record[ID_FIELDS[name]])
            if key in seen:
                raise InputError(f"{path}.{ID_FIELDS[name]} duplicates {name}[{seen[key]}] in canonical form (A12)")
            seen[key] = index
            if name in ("decision_log", "retrospective_inputs"):
                if key in evidence_ids:
                    raise InputError(f"{path}.{ID_FIELDS[name]} duplicates an evidence ID used in {evidence_ids[key]}")
                evidence_ids[key] = path
    if ctx["replay"] and set(ctx["prior"]) - ctx["bound"]:
        pass  # holds whose path is not a placeholder are refused by the whole-document comparison
    clean = {
        "contract_version": CONTRACT,
        "run_metadata": {"generated_at": timestamp},
        "engagement": json.loads(json.dumps(doc["engagement"])),
    }
    if "demo_scenario" in run_metadata:
        clean["run_metadata"]["demo_scenario"] = run_metadata["demo_scenario"]
    for name in RAW_ARRAYS:
        clean[name] = json.loads(json.dumps(doc[name]))
    clean["escalations"] = escalations
    return clean, timestamp


# ---------------------------------------------------------------------------------------------
# Embedded-instruction screen (D1-D3, D5, D11, D13, D15, D16, D18, D20-D22)
# ---------------------------------------------------------------------------------------------

_MARKER_RE = re.compile(r"[\[\u27e6\u3010\u3014][^\[\]\u27e6\u27e7\u3010\u3011\u3014\u3015]{0,60}?\bwithheld\b")
FAMILIES = tuple(sg.FAMILIES) + ("supplied_marker", "client_identity", "render_shape")
LOCATION_RE = re.compile(r"field|record|run|rendered|line \d+|lines \d+-\d+")
HOLD_REASONS = {
    "oversize": "field too long to screen; withheld for review (text not repeated)",
    "supplied_marker": "field carries a withheld-marker form the engines did not emit; withheld for review (text not repeated)",
    "client_identity": "field repeats the engagement client name, which is itself withheld; withheld for review (text not repeated)",
    "instruction": "embedded instruction or steering text; the field is withheld for review (text not repeated)",
    "render_shape": "value is not in a render-safe shape (a title is a short noun phrase; a citation is a source "
                    "path or document ID with an optional locator); withheld for review (text not repeated)",
}

# ---------------------------------------------------------------------------------------------
# Render policy (confidentiality-sanitisation-rules.md #8.6). A supplied title or citation reaches
# the governed record and the skeleton only in a positive allow-shape, so text the detector misses
# cannot render: anything else is withheld with a render_shape hold.
# ---------------------------------------------------------------------------------------------

TITLE_MAX_CHARS = 80
TITLE_MAX_WORDS = 10
CITATION_MAX_CHARS = 160
_TITLE_PUNCT = set(" -&/(),+'\u2019")
# Words that make a clause rather than a noun phrase: auxiliaries, modals, negation, pronouns,
# demonstratives, politeness and steering adverbs.
_TITLE_CLAUSE_WORDS = frozenset((
    "is am are was were be been being do does did has have had can could will would shall should must might "
    "not no never nothing nobody please kindly this these that those it its they them we us you your i me "
    "he she him said says say tell told so already now just straight again exactly anyone everyone someone"
).split())
# Imperative or verdict verbs that never head a reusable-asset noun phrase.
_TITLE_VERBS = frozenset((
    "approve approved approves publish published publishes waive waived waives bypass bypassed ignore ignored "
    "ignores disregard disregarded overlook overlooked skip skipped skips vouch vouched vetted cleared "
    "authorise authorised authorize authorized escalate reopen examine delete consider"
).split())
# Verbs that are also nouns ("Release plan", "Review checklist"): refused only as the first word
# followed by a determiner, pronoun or 'as/for/to/without' ("Release the asset", "Share as is").
_TITLE_LEAD_VERBS = frozenset((
    "release share send mark keep leave flag treat look go move use take make put let check review close file "
    "list accept allow forward grant permit sign remove drop add set give push post upload distribute circulate "
    "copy label rate classify record"
).split())
_TITLE_LEAD_FOLLOWERS = frozenset("the a an all every any each our their my his her as for to without".split())
_TITLE_PHRASES = ("fine to", "ok to", "okay to", "safe to", "good to go", "as is", "cleared for", "approved for",
                  "for external use", "no need")
_CITE_LOCATOR = (r"(?:rows?|lines?|clauses?|sections?|pages?|pp?\.|slides?|paras?|paragraphs?|items?|tabs?|sheets?|"
                 r"cells?|tables?|figures?|fig\.|appendix|annex|schedule|\u00a7)")
_CITE_TOKEN = r"(?:\d[A-Za-z0-9.]{0,15}|[A-Za-z]{1,2}(?:[\d.][A-Za-z0-9.]{0,13})?)"
_CITE_VALUE = _CITE_TOKEN + r"(?:\s?[-\u2013]\s?" + _CITE_TOKEN + r")?"
_CITE_NAMED = r"(?:sheet|tab)\s[A-Za-z][A-Za-z0-9_]{0,31}"
_CITE_PART = (r"[A-Za-z0-9][A-Za-z0-9_./\\-]{0,119}(?:#[A-Za-z0-9][A-Za-z0-9_.-]{0,63})?"
              r"(?:,?\s(?:" + _CITE_NAMED + r"|" + _CITE_LOCATOR + r"\s?" + _CITE_VALUE
              + r"(?:,\s?" + _CITE_VALUE + r")*))*")
CITATION_RE = re.compile(_CITE_PART + r"(?:;\s?" + _CITE_PART + r")*")
_CITE_SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./\\-]*")
_CITE_WORDS = re.compile(r"#([A-Za-z0-9][A-Za-z0-9_.-]*)|\b(?:sheet|tab)\s([A-Za-z][A-Za-z0-9_]*)")
_TITLE_PATH = re.compile(r"(?:engagement|artifacts\[\d+\]|candidate_assets\[\d+\])\.title")
_CITATION_PATH = re.compile(r"(?:engagement|[a-z_]+\[\d+\])\.citation")


def title_shape_ok(value):
    """A short noun phrase: letters, digits and light punctuation only, no clause word, no imperative
    or verdict verb, no verdict phrase (#8.6)."""
    text = unicodedata.normalize("NFKC", strip_cf(value)).strip()
    if not text or len(text) > TITLE_MAX_CHARS or not any(c.isalpha() for c in text):
        return False
    for index, char in enumerate(text):
        if char.isalnum() or char in _TITLE_PUNCT:
            continue
        if char == "." and 0 < index < len(text) - 1 and text[index - 1].isdigit() and text[index + 1].isdigit():
            continue
        return False
    tokens = text.split()
    if len(tokens) > TITLE_MAX_WORDS:
        return False
    lowered = []
    for token in tokens:
        bare = token.strip("(),'\u2019")
        low = bare.casefold().replace("\u2019", "'")
        acronym = len(bare) >= 2 and bare.isupper()
        if low.endswith("n't") or (not acronym and low in _TITLE_CLAUSE_WORDS) or low in _TITLE_VERBS:
            return False
        lowered.append(low)
    if lowered[0] in _TITLE_LEAD_VERBS and len(lowered) > 1 and lowered[1] in _TITLE_LEAD_FOLLOWERS:
        return False
    joined = f" {' '.join(words(text))} "
    return not any(f" {phrase} " in joined for phrase in _TITLE_PHRASES)


def citation_shape_ok(value):
    """A source path or document ID (no spaces; it carries a '.', '/', '\\' or a digit) with an optional
    #anchor and row, line, clause, section, page or named-sheet locators, ';'-separated. No path
    segment, anchor or sheet name may spell a clause word or verb, as an identifier may not (#8.6)."""
    text = value.strip()
    if not text or len(text) > CITATION_MAX_CHARS or not CITATION_RE.fullmatch(text):
        return False
    for part in text.split(";"):
        source = _CITE_SOURCE.match(part.strip())
        if not source or not any(c in "./\\" or c.isdigit() for c in source.group(0)):
            return False
        if not id_shape_ok(re.sub(r"[/\\]", ".", source.group(0))):
            return False
    return all(id_shape_ok(anchor or sheet) for anchor, sheet in _CITE_WORDS.findall(text))


def id_shape_ok(value):
    """An identifier renders as itself, so it may not spell a clause: no '-', '_' or '.' separated
    segment is a clause word or an imperative or verdict verb (#8.6). Upper-case acronyms pass."""
    for segment in re.split(r"[-_.]+", value):
        low = segment.casefold()
        acronym = len(segment) >= 2 and segment.isupper()
        if (not acronym and low in _TITLE_CLAUSE_WORDS) or low in _TITLE_VERBS:
            return False
    return True


def shape_hits(path, value):
    """The render-policy screen for one supplied value: ("render_shape",) or ()."""
    if _TITLE_PATH.fullmatch(path):
        return () if title_shape_ok(value) else ("render_shape",)
    if _CITATION_PATH.fullmatch(path):
        return () if citation_shape_ok(value) else ("render_shape",)
    return ()


def marker_shaped(text):
    return bool(_MARKER_RE.search(canon(text)))


def _families(hits):
    found = []
    for hit in hits:
        if hit.family not in found:
            found.append(hit.family)
    return found


@functools.lru_cache(maxsize=65536)
def text_hits(text):
    """The single detector call site for one line of supplied text: a tuple of hit families."""
    if len(text) > sg.MAX_TOTAL_CHARS:
        return ("oversize",)
    found = ["supplied_marker"] if marker_shaped(text) else []
    for family in _families(sg.scan(text, **GUARD_HOOKS)):
        if family not in found:
            found.append(family)
    return tuple(found)


@functools.lru_cache(maxsize=65536)
def fields_hits(values):
    """Bounded join of related values (D13, D18, D22): a tuple of hit families."""
    if sum(len(value) for value in values) > sg.MAX_TOTAL_CHARS:
        return ("oversize",)
    return tuple(_families(sg.scan_fields({str(i): v for i, v in enumerate(values)}, **GUARD_HOOKS)))


def id_hits(value):
    """IDs, tokens and sources are scanned with '-', '_', '.' and ':' read as spaces, then each
    ':'-separated segment on its own so a 'scheme:' prefix cannot shield an instruction (D13)."""
    found = text_hits(re.sub(r"[-_.:]+", " ", value))
    segments = value.split(":")
    for segment in segments if not found and len(segments) > 1 else ():
        found = text_hits(re.sub(r"[-_.]+", " ", segment).strip())
        if found:
            break
    return found


_LINE_SPLIT = re.compile(r"\r\n|[\n\r\u2028\u2029\x85\x0b\x0c]")


def field_hits(text):
    """Screen one field line by line, then adjacent line pairs (D11). Returns (families, location)."""
    if len(text) > sg.MAX_TOTAL_CHARS:
        return ("oversize",), "field"
    lines = _LINE_SPLIT.split(text)
    single = len([line for line in lines if line.strip()]) <= 1
    for number, line in enumerate(lines, start=1):
        found = text_hits(line)
        if found:
            return found, "field" if single else f"line {number}"
    for number in range(1, len(lines)):
        pair = (lines[number - 1], lines[number])
        if pair[0].strip() and pair[1].strip():
            found = fields_hits(pair)
            if found:
                return found, f"lines {number}-{number + 1}"
    return (), ""


def strip_placeholders(text):
    return text.replace(WITHHELD, " ")


_STOP_TOKENS = {"the", "client", "group", "company", "services", "service", "global", "national",
                "international", "holdings", "limited", "ltd", "inc", "corp", "corporation", "and", "of"}


def identity_terms(client_name):
    """The canonical client name and its distinctive first word (>= 4 letters, not a generic word)."""
    if client_name == WITHHELD:
        return ()
    terms = [canon(client_name)]
    first = words(client_name)[:1]
    if first and len(first[0]) >= 4 and first[0] not in _STOP_TOKENS:
        terms.append(first[0])
    return tuple(t for t in terms if t)


def contains_identity(text, terms):
    body = canon(strip_placeholders(text))
    tokens = set(words(body))
    for term in terms:
        if " " in term or not term.isalnum():
            if term in body:
                return True
        elif term in tokens:
            return True
    return False


def _layout(doc):
    """Every screened free-text slot in a fixed order, the records whose fields render together and
    the runs of adjacent values. A slot is (path, container, key)."""
    slots, records, runs = [], [], []

    def record_slots(record, path, spec):
        members = []
        for member, kind, _ in spec:
            if member not in record:
                continue
            if kind in ("text", "name"):
                members.append((f"{path}.{member}", record, member))
            elif kind in ("texts", "names"):
                items = [(f"{path}.{member}[{i}]", record[member], i) for i in range(len(record[member]))]
                members.extend(items)
                if len(items) > 1:
                    runs.append(items)
        slots.extend(members)
        records.append(members)
        return members

    record_slots(doc["engagement"], "engagement", RECORD_SPECS["engagement"])
    for name in RAW_ARRAYS:
        previous = None
        for index, record in enumerate(doc[name]):
            members = record_slots(record, f"{name}[{index}]", RECORD_SPECS[name])
            if previous is not None:
                runs.append(("pair", previous, members))
            previous = members
    escalation_slots = [(f"escalations[{i}]", doc["escalations"], i) for i in range(len(doc["escalations"]))]
    slots.extend(escalation_slots)
    if len(escalation_slots) > 1:
        runs.append(escalation_slots)
    return slots, records, runs


def screen(doc, prior=None, forced=None):
    """Screen every supplied free-text value of a validated input. Returns (screened copy, holds).
    prior: carried holds keyed by path (a carried placeholder keeps its hold); forced: paths the
    rendered-document screen withholds (#8.2)."""
    prior = prior or {}
    forced = forced or {}
    doc = json.loads(json.dumps(doc))
    slots, records, runs = _layout(doc)
    order = {path: index for index, (path, _, _) in enumerate(slots)}
    held = {}
    for path, box, key in slots:
        value = box[key]
        if path in forced:
            held[path] = forced[path]
        elif path in prior and value == WITHHELD:
            held[path] = prior[path]
        else:
            found, location = field_hits(value)
            if not found:
                found, location = shape_hits(path, value), "field"
            if found:
                held[path] = (found, location)
    terms = identity_terms(doc["engagement"]["client_name"])  # harvested before any redaction (A16)

    def live(members):
        return [m for m in members if m[0] not in held]

    def withhold(members, found, location):
        for path, _, _ in members:
            if path not in held:
                held[path] = (found, location)

    while True:
        before = len(held)
        for members in records:
            current = live(members)
            if len(current) > 1:
                found = fields_hits(tuple(box[key] for _, box, key in current))
                if found:
                    withhold(current, found, "record")
                    continue
                # Fields of one record can render next to each other in any layout (a title beside
                # its description), so every pair of live fields is also screened as a join (D22).
                for i in range(len(current)):
                    for j in range(i + 1, len(current)):
                        pair = (current[i], current[j])
                        if all(m[0] not in held for m in pair):
                            found = fields_hits(tuple(box[key] for _, box, key in pair))
                            if found:
                                withhold(pair, found, "record")
        for run in runs:
            if run and run[0] == "pair":
                current = live(run[1]) + live(run[2])
                if live(run[1]) and live(run[2]):
                    found = fields_hits(tuple(box[key] for _, box, key in current))
                    if found:
                        withhold(current, found, "run")
                        continue
                    # Any field of one entry can render next to any field of the next (D18).
                    for first in run[1]:
                        for second in run[2]:
                            if first[0] not in held and second[0] not in held:
                                found = fields_hits((first[1][first[2]], second[1][second[2]]))
                                if found:
                                    withhold((first, second), found, "run")
                continue
            current = live(run)
            windows = [current] + [current[i:i + size] for size in (2, 3) for i in range(len(current) - size + 1)]
            for window in windows:
                if len(window) > 1 and all(m[0] not in held for m in window):
                    found = fields_hits(tuple(box[key] for _, box, key in window))
                    if found:
                        withhold(window, found, "run")
        if "engagement.client_name" in held and terms:
            for member in slots:
                if member[0] not in held and contains_identity(member[1][member[2]], terms):
                    held[member[0]] = (("client_identity",), "field")
        if len(held) == before:
            break
    for path, box, key in slots:
        if path in held:
            box[key] = WITHHELD
    holds = []
    for number, path in enumerate(sorted(held, key=order.__getitem__), start=1):
        found, location = held[path]
        holds.append(make_hold(number, path, found, location))
    return doc, holds


def make_hold(number, path, found, location):
    found = tuple(found)
    if "oversize" in found:
        reason, citation = HOLD_REASONS["oversize"], "confidentiality-sanitisation-rules.md #8.1"
    elif "supplied_marker" in found:
        reason, citation = HOLD_REASONS["supplied_marker"], "confidentiality-sanitisation-rules.md #8.4"
    elif "client_identity" in found:
        reason, citation = HOLD_REASONS["client_identity"], "confidentiality-sanitisation-rules.md #8.3"
    elif found == ("render_shape",):
        reason, citation = HOLD_REASONS["render_shape"], "confidentiality-sanitisation-rules.md #8.6"
    else:
        reason, citation = HOLD_REASONS["instruction"], "confidentiality-sanitisation-rules.md #8.1"
    if location == "rendered":
        citation = "confidentiality-sanitisation-rules.md #8.2"
    return {
        "hold_id": f"SH-{number:03d}",
        "path": path,
        "location": location,
        "family": "+".join(sorted(found)),
        "reason": reason,
        "source": "engine:sanitize_check" if location == "rendered" else "engine:asset_identify",
        "citation": citation,
    }


def parse_holds(value):
    """Carried screening holds keyed by path. Only the family and location of a withheld value are
    carried (its text is gone); everything else is re-derived and compared."""
    need_list(value, "screening_holds")
    prior = {}
    for index, hold in enumerate(value):
        path = f"screening_holds[{index}]"
        need_object(hold, path)
        check_members(hold, path, ("hold_id", "path", "location", "family", "reason", "source", "citation"))
        for member in ("hold_id", "path", "location", "family", "reason", "source", "citation"):
            if type(hold[member]) is not str:
                raise InputError(f"{path}.{member} must be a string (value not repeated)")
        if not LOCATION_RE.fullmatch(hold["location"]):
            raise InputError(f"{path}.location is not a screening location (value not repeated)")
        families = tuple(hold["family"].split("+"))
        if not all(f in FAMILIES for f in families):
            raise InputError(f"{path}.family is not a detector family (value not repeated)")
        if hold["path"] in prior:
            raise InputError(f"{path}.path repeats another hold's path")
        prior[hold["path"]] = (families, hold["location"])
    return prior


# ---------------------------------------------------------------------------------------------
# Stage 1 - asset_identify (reuse-asset-rubric.md)
# ---------------------------------------------------------------------------------------------


def shelf_score(months):
    if months >= 18:
        return 100
    if months >= 12:
        return 80
    if months >= 6:
        return 50
    return 20


def asset_score(asset):
    general = asset["generalisability"] / 5 * 100
    effort = asset["effort_to_recreate"] / 5 * 100
    shelf = shelf_score(asset["shelf_life_months"])
    dependency = (5 - asset["client_dependency"]) / 5 * 100
    return round(general * GENERALISABILITY_WEIGHT + effort * EFFORT_WEIGHT
                 + shelf * SHELF_LIFE_WEIGHT + dependency * DEPENDENCY_WEIGHT, 1)


def recommendation(score, confidence):
    if score >= SHORTLIST_SCORE and confidence >= SCORING_CONFIDENCE_FLOOR:
        return "shortlist"
    if score >= RETAIN_SCORE:
        return "retain_for_internal_reference"
    return "archive_with_engagement"


def _merge(items, extra):
    out = list(items)
    for item in extra:
        if item == WITHHELD or item not in out:
            out.append(item)
    return out


def _composed(text, fallback):
    """Text composed from several supplied values is screened as composed (D22)."""
    if WITHHELD in text or text_hits(text):
        return fallback
    return text


def stage_asset_identify(s, holds, timestamp):
    deliverable_index, gaps = [], []
    for artifact in s["artifacts"]:
        complete = artifact["status"] == "complete"
        gap = artifact["required"] is True and not complete
        if gap:
            rule = " - closeout gap (reuse-asset-rubric.md #6.1)"
            gaps.append(_composed(
                f"{artifact['artifact_id']}: required deliverable '{artifact['title']}' is {artifact['status']}{rule}",
                f"{artifact['artifact_id']}: required deliverable is {artifact['status']}{rule}",
            ))
        deliverable_index.append({
            "artifact_id": artifact["artifact_id"],
            "title": artifact["title"],
            "artifact_type": artifact["artifact_type"],
            "required": artifact["required"],
            "status": artifact["status"],
            "completeness_gap": gap,
            "owner": artifact["owner"],
            "confidence": min(float(artifact["confidence"]), 0.99),
            "source": "engine:asset_identify",
            "citation": f"{artifact['citation']}; reuse-asset-rubric.md #6.1",
        })
    shortlist = []
    for asset in s["candidate_assets"]:
        score = asset_score(asset)
        confidence = min(float(asset["confidence"]), 0.94)
        shortlist.append({
            "asset_id": asset["asset_id"],
            "title": asset["title"],
            "asset_type": asset["asset_type"],
            "description": asset["description"],
            "reuse_score": score,
            "recommendation": recommendation(score, confidence),
            "reuse_rationale": (
                f"generalisability {asset['generalisability']}/5; "
                f"effort_to_recreate {asset['effort_to_recreate']}/5; "
                f"shelf_life {asset['shelf_life_months']} months; "
                f"client_dependency {asset['client_dependency']}/5"
            ),
            "confidentiality_markers": list(asset["confidentiality_markers"]),
            "aggregation_tokens": list(asset["aggregation_tokens"]),
            "confidence": confidence,
            "source": "engine:asset_identify",
            "citation": f"{asset['citation']}; reuse-asset-rubric.md #1.1,#2.1,#3.1,#4.1,#5.1",
        })
    screening = []
    if holds:
        screening.append(
            f"screening: {len(holds)} field(s) withheld for embedded-instruction review - see screening_holds "
            "(confidentiality-sanitisation-rules.md #8.1)"
        )
    doc = {key: s[key] for key in ("contract_version", "run_metadata", "engagement") + RAW_ARRAYS}
    doc["escalations"] = _merge(s["escalations"], gaps + screening)
    doc["deliverable_index"] = deliverable_index
    doc["reusable_asset_shortlist"] = shortlist
    doc["provenance"] = {
        "engines": [ENGINE_VERSIONS["asset_identify"]],
        "generated_at": timestamp,
        "demo_scenario": s["run_metadata"].get("demo_scenario", ""),
        "input_escalations": list(s["escalations"]),
        "policies": ["reuse-asset-rubric.md #1-#6", "confidentiality-sanitisation-rules.md #8.1"],
        "screening": SCREENING_LABEL,
    }
    doc["screening_holds"] = holds
    return doc


# ---------------------------------------------------------------------------------------------
# Stage 2 - lesson_cluster (lesson-taxonomy.md)
# ---------------------------------------------------------------------------------------------


def category_for(text):
    """(category, keyword hits). No match, or a tie between categories, stays unclassified (#1.5, A4)."""
    low = text.lower()
    counts = {category: sum(1 for word in kw if word in low) for category, kw in CLUSTER_KEYWORDS.items()}
    best = max(counts.values())
    if best == 0 or list(counts.values()).count(best) > 1:
        return ("unclassified", 0)
    return (next(c for c, n in counts.items() if n == best), best)


def decision_withheld(item):
    return WITHHELD in (item["summary"], item["impact"], item["citation"])


def retro_withheld(item):
    return WITHHELD in (item["text"], item["speaker_role"], item["citation"])


def evidence_items(doc):
    """Decision and retrospective evidence; withheld text is marked and never read (D19)."""
    items = []
    for item in doc["decision_log"]:
        withheld = decision_withheld(item)
        items.append({
            "id": item["decision_id"], "kind": "decision",
            "text": "" if withheld else item["summary"] + " " + item["impact"],
            "withheld": withheld, "confidence": item["confidence"], "citation": item["citation"],
            "named_people": [],
        })
    for item in doc["retrospective_inputs"]:
        withheld = retro_withheld(item)
        items.append({
            "id": item["input_id"], "kind": "retrospective",
            "text": "" if withheld else item["text"],
            "withheld": withheld, "confidence": item["confidence"], "citation": item["citation"],
            "named_people": list(item["named_people"]),
        })
    return items


def stage_lesson_cluster(doc):
    grouped = {}
    for ev in evidence_items(doc):
        category, hits = ("unclassified", 0) if ev["withheld"] else category_for(ev["text"])
        grouped.setdefault(category, []).append((ev, hits))
    clusters = []
    for category in sorted(grouped):
        members = [m[0] for m in grouped[category]]
        blob = " ".join(m["text"] for m in members).lower()
        impact_hits = sum(1 for term in HIGH_IMPACT_TERMS if term in blob)
        priority = min(100, 45 + 10 * impact_hits + 5 * len(members))
        keyword_hits = sum(h for _, h in grouped[category])
        confidence = round(min(0.95, 0.62 + 0.06 * keyword_hits + 0.03 * len(members)), 2)
        signals = []
        for ev in members:
            if ev["withheld"]:
                signals.append({"evidence_id": ev["id"], "signal": "embedded_instruction",
                                "citation": "confidentiality-sanitisation-rules.md #8.1"})
            if ev["named_people"]:
                signals.append({"evidence_id": ev["id"], "signal": "named_person",
                                "citation": "confidentiality-sanitisation-rules.md #2.1"})
            if ev["named_people"] and BLAME_PATTERN.search(ev["text"]):
                signals.append({"evidence_id": ev["id"], "signal": "named_person_blame",
                                "citation": "confidentiality-sanitisation-rules.md #2.2"})
        first = members[0]
        seed = (f"Evidence {first['id']}: source text withheld for embedded-instruction review."
                if first["withheld"] else _composed(first["text"][:220], f"Evidence {first['id']}: seed not repeated."))
        clusters.append({
            "category": category,
            "priority_score": priority,
            "review_candidate": confidence < MIN_CLUSTER_CONFIDENCE,
            "evidence_ids": [ev["id"] for ev in members],
            "evidence_citations": list(dict.fromkeys(ev["citation"] for ev in members)),
            "summary_seed": seed,
            "sensitivity_signals": signals,
            "confidence": confidence,
            "source": "engine:lesson_cluster",
            "citation": f"{CATEGORY_CITATIONS[category]}; lesson-taxonomy.md #2.1,#2.2,#3.1",
        })
    clusters.sort(key=lambda c: (-c["priority_score"], c["category"]))
    for index, cluster in enumerate(clusters, start=1):
        cluster["cluster_id"] = f"LC-{index:03d}"
    out = {key: value for key, value in doc.items() if key != "screening_holds"}
    out["provenance"] = dict(doc["provenance"])
    out["provenance"]["engines"] = doc["provenance"]["engines"] + [ENGINE_VERSIONS["lesson_cluster"]]
    out["provenance"]["policies"] = doc["provenance"]["policies"] + ["lesson-taxonomy.md #1-#4"]
    out["lesson_clusters"] = clusters
    out["screening_holds"] = doc["screening_holds"]
    return out


# ---------------------------------------------------------------------------------------------
# Stage 3 - sanitize_check (confidentiality-sanitisation-rules.md)
# ---------------------------------------------------------------------------------------------

LESSON_HELD_REASON = "lesson evidence must be rewritten at role and process level before reuse (source text not repeated)"
CONTEXT_GUIDANCE = (
    "Draft a generalized engagement context only from approved release-candidate "
    "metadata. Do not copy client names, client descriptors, sector-and-region "
    "combinations, precise scale, dates, products or other raw engagement fields."
)
HANDOFF_NOTE = (
    "Credential & Case Study Assembly may consume only release-candidate fields and inherits no "
    "permission to publish, identify the client, use logos or waive client terms."
)
HANDOFF_FIELDS = [
    "knowledge_record.reusable_assets",
    "knowledge_record.held_assets_summary",
    "knowledge_record.lessons",
    "sanitisation_report.findings",
    "released_assets[].clearance_state",
]


def finding(target_type, target_id, disposition, state, reason, citation, confidence):
    return {
        "target_type": target_type, "target_id": target_id, "disposition": disposition,
        "clearance_state": state, "reason": reason, "confidence": confidence,
        "source": "engine:sanitize_check", "citation": citation,
    }


def _asset_withheld(raw_asset):
    return any(raw_asset[m] == WITHHELD for m in ("title", "asset_type", "description", "citation"))


def stage_sanitize_check(doc):
    engagement = doc["engagement"]
    terms = identity_terms(engagement["client_name"])
    identity_unscreenable = engagement["client_name"] == WITHHELD
    terms_unavailable = not doc["confidentiality_terms"]
    raw_assets = {a["asset_id"]: a for a in doc["candidate_assets"]}
    findings, released, held, candidates = [], [], [], []
    escalations = list(doc["escalations"])
    own_finding = {}

    for asset in doc["reusable_asset_shortlist"]:
        raw_asset = raw_assets[asset["asset_id"]]
        markers = set(asset["confidentiality_markers"]) | set(asset["aggregation_tokens"])
        confidence = min(float(asset["confidence"]), 0.93)
        states, reasons, citations = [], [], []

        def hold(state, reason, citation):
            states.append(state)
            reasons.append(reason)
            citations.append(citation)

        if asset["recommendation"] != "shortlist":
            hold("HOLD_NOT_SHORTLISTED", "reuse score did not reach shortlist band",
                 "confidentiality-sanitisation-rules.md #6.2; reuse-asset-rubric.md #5.2,#5.3")
        else:
            candidates.append(asset)
            citations.append("confidentiality-sanitisation-rules.md #6.2,#7.1")
        if confidence < SANITISATION_CONFIDENCE_FLOOR:
            hold("HOLD_LOW_CONFIDENCE", f"confidence {confidence} below {SANITISATION_CONFIDENCE_FLOOR}",
                 "confidentiality-sanitisation-rules.md #6.1")
        if markers & DIRECT_IDENTIFIER_MARKERS:
            hold("HOLD_REDACTION_REQUIRED",
                 "direct client-identifying material present: " + ", ".join(sorted(markers & DIRECT_IDENTIFIER_MARKERS)),
                 "confidentiality-sanitisation-rules.md #1.1")
        if markers & CLIENT_SPECIFIC_MARKERS:
            hold("HOLD_REDACTION_REQUIRED",
                 "client-specific configuration requires removal before reuse: " + ", ".join(sorted(markers & CLIENT_SPECIFIC_MARKERS)),
                 "confidentiality-sanitisation-rules.md #1.3")
        asset_text = " ".join(raw_asset[m] for m in ("title", "asset_type", "description", "citation"))
        if terms and contains_identity(asset_text, terms):
            hold("HOLD_REDACTION_REQUIRED", "asset text contains the engagement client name (name not repeated)",
                 "confidentiality-sanitisation-rules.md #1.1")
        if markers & NAMED_PERSON_MARKERS:
            hold("HOLD_PERSONAL_DATA_REWRITE",
                 "named-person material requires removal and role-level rewrite: " + ", ".join(sorted(markers & NAMED_PERSON_MARKERS)),
                 "confidentiality-sanitisation-rules.md #2.1,#2.2")
        if markers & LICENSED_MARKERS:
            hold("HOLD_RIGHTS_UNKNOWN",
                 "third-party or licensed material requires rights evidence: " + ", ".join(sorted(markers & LICENSED_MARKERS)),
                 "confidentiality-sanitisation-rules.md #4.1")
        if markers & COMMERCIAL_MARKERS:
            hold("HOLD_REDACTION_REQUIRED",
                 "commercial figures require verified removal or banding before review: " + ", ".join(sorted(markers & COMMERCIAL_MARKERS)),
                 "confidentiality-sanitisation-rules.md #3.1")
        if markers & PRODUCT_AGGREGATION_MARKERS and not states:
            reasons.append("named product/vendor contributes to aggregation review")
            citations.append("confidentiality-sanitisation-rules.md #4.2")
        unknown = markers - KNOWN_MARKERS - AGGREGATION_TOKENS
        if unknown:
            hold("HOLD_UNRECOGNISED_MARKER",
                 f"{len(unknown)} unrecognised confidentiality marker(s) or aggregation token(s) (names not repeated)",
                 "confidentiality-sanitisation-rules.md #7.4")
            escalations.append(f"{asset['asset_id']}: unrecognised confidentiality marker or aggregation token - asset held "
                               "(confidentiality-sanitisation-rules.md #7.4)")
        if terms_unavailable:
            hold("HOLD_TERMS_UNAVAILABLE", "no confidentiality terms supplied; client terms cannot be checked",
                 "confidentiality-sanitisation-rules.md #7.5")
        if identity_unscreenable:
            hold("HOLD_IDENTITY_UNSCREENABLE", "engagement client name withheld; client identity cannot be screened",
                 "confidentiality-sanitisation-rules.md #8.3")
        if _asset_withheld(raw_asset):
            hold("HOLD_EMBEDDED_INSTRUCTION", "asset text withheld for embedded-instruction review (text not repeated)",
                 "confidentiality-sanitisation-rules.md #8.1")
        state = next(s for s in PRECEDENCE if s in states or s == RELEASE)
        disposition = "release_candidate" if state == RELEASE else "hold"
        if not reasons and disposition == "release_candidate":
            reasons.append("no individual hold marker detected; candidate still requires human review")
        rec = {
            "asset_id": asset["asset_id"],
            "title": asset["title"],
            "title_withheld": asset["title"] == WITHHELD,
            "reuse_score": asset["reuse_score"],
            "clearance_state": state,
            "review_required": DEFAULT_REVIEW_REQUIRED,
            "reason": "; ".join(reasons),
            "confidence": confidence,
            "source": "engine:sanitize_check",
            "citation": "; ".join(dict.fromkeys(citations)) or "confidentiality-sanitisation-rules.md #6.2",
        }
        own = finding("asset", asset["asset_id"], disposition, state, rec["reason"], rec["citation"], confidence)
        own_finding[asset["asset_id"]] = own
        findings.append(own)
        (held if disposition == "hold" else released).append(rec)

    tokens, unknown_tokens, group = set(), set(), set()
    for asset in candidates:
        for token in asset["aggregation_tokens"]:
            (tokens if token in AGGREGATION_TOKENS else unknown_tokens).add(token)
            group.add(asset["asset_id"])
    if len(tokens) + len(unknown_tokens) >= AGGREGATION_MIN_TOKENS:
        listed = ", ".join(sorted(tokens)) + (f" and {len(unknown_tokens)} unrecognised" if unknown_tokens else "")
        reason = (f"aggregation risk: {len(tokens) + len(unknown_tokens)} identifying token categories across "
                  f"candidate assets ({listed})")
        citation = "confidentiality-sanitisation-rules.md #5.1,#5.2"
        escalations.append(reason + " - group HOLD (" + citation + ")")
        still = []
        for rec in released:
            if rec["asset_id"] in group:
                moved = dict(rec, clearance_state="HOLD_AGGREGATION_RISK", reason=reason, citation=citation)
                held.append(moved)
                own_finding[rec["asset_id"]].update(disposition="hold", clearance_state="HOLD_AGGREGATION_RISK",
                                                     reason=reason, citation=citation)  # A10
                findings.append(finding("asset_group", rec["asset_id"], "hold", "HOLD_AGGREGATION_RISK", reason,
                                        citation, rec["confidence"]))
            else:
                still.append(rec)
        released = still

    sensitive = set()
    for item in doc["retrospective_inputs"]:
        withheld = retro_withheld(item)
        text = "" if withheld else item["text"]
        named = list(item["named_people"])
        blame = bool(BLAME_PATTERN.search(text))
        if blame and not named:
            named = PERSON_NAME_PATTERN.findall(text)
        client_hit = bool(terms) and contains_identity(text, terms)
        confidence = min(item["confidence"], 0.91)
        state = guidance = None
        if withheld:
            state, guidance = "HOLD_EMBEDDED_INSTRUCTION", "Source text withheld for embedded-instruction review; do not draft from this evidence."
            citation = "confidentiality-sanitisation-rules.md #8.1,#6.2"
        elif blame:
            state, guidance = "HOLD_PERSONAL_DATA_REWRITE", "Rewrite at role/process level; remove named person and blame attribution."
            citation = "confidentiality-sanitisation-rules.md #2.1,#2.2,#6.2"
        elif named:
            state, guidance = "HOLD_PERSONAL_DATA_REWRITE", "Remove named person; use role-level description."
            citation = "confidentiality-sanitisation-rules.md #2.1,#6.2"
        elif client_hit:
            state, guidance = "HOLD_REDACTION_REQUIRED", "Remove the client identity; use a generalized description."
            citation = "confidentiality-sanitisation-rules.md #1.1,#6.2"
        elif identity_unscreenable:
            state, guidance = "HOLD_IDENTITY_UNSCREENABLE", "Client identity cannot be screened; hold for review."
            citation = "confidentiality-sanitisation-rules.md #8.3,#6.2"
        if state:
            sensitive.add(item["input_id"])
            findings.append(finding("lesson", item["input_id"], "rewrite", state, guidance, citation, confidence))
    for item in doc["decision_log"]:
        withheld = decision_withheld(item)
        text = "" if withheld else item["summary"] + " " + item["impact"]
        if withheld or (terms and contains_identity(text, terms)):
            sensitive.add(item["decision_id"])
            state = "HOLD_EMBEDDED_INSTRUCTION" if withheld else "HOLD_REDACTION_REQUIRED"
            citation = "confidentiality-sanitisation-rules.md #8.1,#6.2" if withheld else "confidentiality-sanitisation-rules.md #1.1,#6.2"
            guidance = ("Source text withheld for embedded-instruction review; do not draft from this evidence."
                        if withheld else "Remove the client identity; use a generalized description.")
            findings.append(finding("lesson", item["decision_id"], "rewrite", state, guidance, citation,
                                    min(item["confidence"], 0.91)))

    governed = []
    for cluster in doc["lesson_clusters"]:
        rewrite = bool(cluster["sensitivity_signals"] or sensitive.intersection(cluster["evidence_ids"])
                       or identity_unscreenable)
        if rewrite:
            guidance = ("Draft only at role and process level. Remove names, blame attribution, "
                        "client identifiers and source wording.")
            policy = "confidentiality-sanitisation-rules.md #2.1,#2.2,#6.2"
        else:
            guidance = ("Draft a generalized lesson from the category and evidence IDs only. "
                        "Do not quote, reconstruct or paraphrase source text.")
            policy = "confidentiality-sanitisation-rules.md #6.2"
        governed.append({
            "cluster_id": cluster["cluster_id"],
            "category": cluster["category"],
            "priority_score": cluster["priority_score"],
            "review_candidate": cluster["review_candidate"],
            "evidence_ids": list(cluster["evidence_ids"]),
            "evidence_citations": list(cluster["evidence_citations"]),
            "citation_withheld": WITHHELD in cluster["evidence_citations"],
            "rewrite_required": rewrite,
            "drafting_guidance": guidance,
            "confidence": min(float(cluster["confidence"]), 0.91),
            "source": "engine:sanitize_check",
            "citation": f"{policy}; {cluster['citation']}",
        })

    if terms_unavailable:
        findings.append(finding("register", "confidentiality_terms", "hold", "HOLD_TERMS_UNAVAILABLE",
                                "no confidentiality terms supplied; client terms cannot be checked",
                                "confidentiality-sanitisation-rules.md #7.5", 0.99))
        escalations.append("confidentiality_terms is empty - client terms cannot be checked; every asset held "
                           "(confidentiality-sanitisation-rules.md #7.5)")
    if identity_unscreenable:
        findings.append(finding("engagement", engagement["engagement_id"], "hold", "HOLD_IDENTITY_UNSCREENABLE",
                                "engagement client name withheld; client identity cannot be screened",
                                "confidentiality-sanitisation-rules.md #8.3", 0.99))
        escalations.append("engagement client name withheld - client identity cannot be screened; every asset held "
                           "(confidentiality-sanitisation-rules.md #8.3)")
    for hold in doc["screening_holds"]:
        state = "HOLD_IDENTITY_UNSCREENABLE" if hold["family"] == "client_identity" else "HOLD_EMBEDDED_INSTRUCTION"
        findings.append(finding("screening", hold["hold_id"], "hold", state, hold["reason"], hold["citation"], 0.95))

    escalations = _merge([], escalations)
    overall = ("HOLD" if held or escalations or any(f["disposition"] in ("hold", "rewrite") for f in findings)
               else RELEASE)
    rewrite_count = sum(1 for lesson in governed if lesson["rewrite_required"])
    summary = (f"{len(released)} release candidate asset(s), {len(held)} held asset(s), "
               f"{rewrite_count} lesson rewrite(s).")
    if doc["screening_holds"]:
        summary += f" {len(doc['screening_holds'])} field(s) withheld for embedded-instruction review."
    out = {key: value for key, value in doc.items() if key not in ("screening_holds", "lesson_clusters")}
    out["escalations"] = escalations
    out["provenance"] = dict(doc["provenance"])
    out["provenance"]["engines"] = doc["provenance"]["engines"] + [ENGINE_VERSIONS["sanitize_check"]]
    out["provenance"]["policies"] = doc["provenance"]["policies"] + ["confidentiality-sanitisation-rules.md #1-#8"]
    out["lesson_clusters"] = governed
    out["sanitisation_report"] = {
        "overall_disposition": overall,
        "findings": findings,
        "governance_note": "Release candidates require human practice review; the engine never clears publication or external use.",
        "source": "engine:sanitize_check",
        "citation": "confidentiality-sanitisation-rules.md #6.2,#7.1,#7.2",
    }
    out["released_assets"] = released
    out["held_assets"] = held
    out["lessons_for_draft"] = governed
    out["knowledge_record"] = {
        "record_id": f"{engagement['engagement_id']}-KR-DRAFT",
        "status": "draft_pending_practice_review",
        "title": "Engagement closeout knowledge record",
        "engagement_context_guidance": CONTEXT_GUIDANCE,
        "reusable_assets": released,
        "held_assets_summary": [{"asset_id": a["asset_id"], "clearance_state": a["clearance_state"],
                                 "reason": a["reason"], "citation": a["citation"]} for a in held],
        "lessons": governed,
        "sanitisation_summary": summary,
        "downstream_handoff": {
            "consumer_template": "credential-case-study-assembly",
            "contract_fields": list(HANDOFF_FIELDS),
            "handoff_note": HANDOFF_NOTE,
        },
        "clearance_state": "DRAFT_NOT_PUBLISHED",
        "confidence": 0.9 if overall != "HOLD" else 0.86,
        "source": "engine:sanitize_check",
        "citation": "confidentiality-sanitisation-rules.md #6.2; downstream handoff contract",
        "draft_label": DRAFT_LABEL,
    }
    out["screening_holds"] = doc["screening_holds"]
    return out


# ---------------------------------------------------------------------------------------------
# Knowledge-record skeleton (knowledge-record SKILL.md; #8.2, #8.5)
# ---------------------------------------------------------------------------------------------

CONTEXT_SLOT = "<<CONTEXT: generalized engagement context that follows engagement_context_guidance>>"
NO_CONTEXT_LINE = "No generalized context drafted: the client identity could not be screened (see Held or excluded material)."
TITLE_WITHHELD_MARK = "title_withheld"
CITATION_WITHHELD_MARK = "citation_withheld"


def lesson_slot(cluster_id):
    return f"<<LESSON {cluster_id}: role- and process-level lesson>>"


def _num(value):
    return json.dumps(value)


def withheld_evidence(doc):
    return {ev["id"] for ev in evidence_items(doc) if ev["withheld"]}


def skeleton(doc):
    """The deterministic knowledge-record skeleton as [(line, slot, contributor paths)]. A slot line
    is the only text the drafter writes; every other line is fixed by the governed payload."""
    kr = doc["knowledge_record"]
    report = doc["sanitisation_report"]
    unscreenable = doc["engagement"]["client_name"] == WITHHELD
    asset_index = {a["asset_id"]: i for i, a in enumerate(doc["candidate_assets"])}
    cite_paths = {}
    for i, item in enumerate(doc["decision_log"]):
        cite_paths[item["decision_id"]] = f"decision_log[{i}].citation"
    for i, item in enumerate(doc["retrospective_inputs"]):
        cite_paths[item["input_id"]] = f"retrospective_inputs[{i}].citation"
    withheld = withheld_evidence(doc)
    lines = []

    def add(text, slot=None, contributors=()):
        lines.append((text, slot, tuple(contributors)))

    add(DRAFT_LABEL)
    add("")
    add(f"# {kr['title']} ({kr['record_id']})")
    add("")
    add("## Generalized engagement context")
    if unscreenable:
        add(NO_CONTEXT_LINE)
    else:
        add(CONTEXT_SLOT, slot="CONTEXT")
    add("")
    add("## Released reusable assets")
    if kr["reusable_assets"]:
        add("| Asset ID | Title | Reuse score | Clearance state | Rule citation |")
        add("|---|---|---|---|---|")
        for asset in kr["reusable_assets"]:
            title = TITLE_WITHHELD_MARK if asset["title"] == WITHHELD else asset["title"]
            add(f"| {asset['asset_id']} | {title} | {_num(asset['reuse_score'])} | "
                f"{asset['clearance_state']} | {asset['citation']} |",
                contributors=[f"candidate_assets[{asset_index[asset['asset_id']]}].title"])
    else:
        add("No reusable assets released by Govern.")
    add("")
    add("## Governed lesson themes")
    if not kr["lessons"]:
        add("No lesson themes clustered.")
    for lesson in kr["lessons"]:
        citations = [CITATION_WITHHELD_MARK if c == WITHHELD else c for c in lesson["evidence_citations"]]
        tail = (f" - evidence {', '.join(lesson['evidence_ids'])}; "
                f"{'; '.join(citations)}")
        head = f"- {lesson['cluster_id']} ({lesson['category']}): "
        contributors = [cite_paths[e] for e in lesson["evidence_ids"]]
        if unscreenable:
            add(head + "No lesson text: the client identity could not be screened" + tail, contributors=contributors)
        elif withheld.intersection(lesson["evidence_ids"]):
            add(head + "No lesson text: evidence withheld for embedded-instruction review" + tail,
                contributors=contributors)
        else:
            add(head + lesson_slot(lesson["cluster_id"]) + tail, slot=lesson["cluster_id"], contributors=contributors)
    add("")
    add("## Held or excluded material")
    rows = [(a["asset_id"], a["clearance_state"], a["reason"], a["citation"]) for a in kr["held_assets_summary"]]
    rows += [(f["target_id"], f["clearance_state"], LESSON_HELD_REASON, f["citation"])
             for f in report["findings"] if f["target_type"] == "lesson"]
    rows += [(f["target_id"], f["clearance_state"], f["reason"], f["citation"])
             for f in report["findings"] if f["target_type"] in ("screening", "register", "engagement")]
    if rows:
        add("| Asset, lesson or hold ID | Clearance state | Reason | Rule citation |")
        add("|---|---|---|---|")
        for row in rows:
            add("| " + " | ".join(row) + " |")
    else:
        add("No assets or lessons held by Govern.")
    add("")
    add("## Sanitisation summary")
    add(f"{kr['sanitisation_summary']} Overall disposition: {report['overall_disposition']}.")
    add("")
    add("## Credential handoff")
    add(f"Consumer: {kr['downstream_handoff']['consumer_template']}. Readable fields: "
        f"{', '.join(kr['downstream_handoff']['contract_fields'])}.")
    add(kr["downstream_handoff"]["handoff_note"])
    add("")
    add("## Required approvals")
    add("Practice review, legal review where flagged, and engagement-owner review. Nothing has been published.")
    return lines


def skeleton_text(doc):
    return "\n".join(line for line, _, _ in skeleton(doc)) + "\n"


def rendered_hits(doc):
    """Screen the rendered skeleton line by line, as each line's contributing values joined, and in
    adjacent pairs (D22). Returns the supplied
    contributor paths to withhold: {path: (families, "rendered")}."""
    lines = skeleton(doc)
    held = {p for p, b, k in _layout(doc)[0] if b[k] == WITHHELD}
    out = {}

    def take(found, *entries):
        for _, _, contributors in entries:
            for path in contributors:
                if path not in held and path not in out:
                    out[path] = (found, "rendered")

    def body(entry):
        text, slot, _ = entry
        if slot == "CONTEXT":
            return ""
        if slot:
            text = text.replace(lesson_slot(slot), " ")
        return strip_placeholders(text)

    values = {p: b[k] for p, b, k in _layout(doc)[0]}
    for entry in lines:
        if entry[2]:
            found = text_hits(body(entry))
            if not found:
                # The values that land on one line are also screened as a run, so punctuation the
                # template puts between them cannot hide a split instruction.
                parts = tuple(values[p] for p in entry[2] if p in values and values[p] != WITHHELD)
                if len(parts) > 1:
                    found = fields_hits(parts)
            if found:
                take(found, entry)
    for first, second in zip(lines, lines[1:]):
        if (first[2] or second[2]) and body(first).strip() and body(second).strip():
            found = fields_hits((body(first), body(second)))
            if found:
                take(found, first, second)
    return out


# ---------------------------------------------------------------------------------------------
# The chain, its replay and the command-line wrapper (A19, A22, A23, B1a, B5, D21)
# ---------------------------------------------------------------------------------------------


def derive(raw, timestamp, prior=None, upto=3):
    """Run the deterministic chain on a validated input up to stage `upto`. Stage 3 also screens the
    rendered skeleton and re-runs the chain until no rendered value is left to withhold (#8.2)."""
    forced = {}
    while True:
        screened, holds = screen(raw, prior, forced)
        doc = stage_asset_identify(screened, holds, timestamp)
        if upto >= 2:
            doc = stage_lesson_cluster(doc)
        if upto >= 3:
            doc = stage_sanitize_check(doc)
            extra = rendered_hits(doc)
            if extra:
                forced.update(extra)
                continue
        return doc


def reconstruct(doc, stage):
    """Validate an intermediate's shape and rebuild the screened input it carries."""
    _check_contract_version(doc)
    expected = STAGE_KEYS[stage]
    missing = sorted(expected - set(doc))
    if missing:
        raise InputError(f"input is not {STAGE_NAMES[stage]} output: {missing[0]} is required")
    extra = [key for key in doc if key not in expected]
    if extra:
        raise InputError(f"input is not {STAGE_NAMES[stage]} output: {seg(extra[0])} is not a member here (name not repeated)")
    provenance = need_object(doc["provenance"], "provenance")
    if "input_escalations" not in provenance:
        raise InputError("provenance.input_escalations is required")
    if not timestamp_ok(provenance.get("generated_at")):
        raise InputError("provenance.generated_at must be an ISO-8601 UTC timestamp YYYY-MM-DDTHH:MM:SSZ (value not repeated)")
    prior = parse_holds(doc["screening_holds"])
    raw = {key: doc[key] for key in RAW_REQUIRED}
    raw["run_metadata"] = doc["run_metadata"]
    raw["escalations"] = provenance["input_escalations"]
    clean, timestamp = validate_input(raw, prior=prior)
    if timestamp != provenance["generated_at"]:
        raise InputError("provenance.generated_at disagrees with run_metadata.generated_at")
    return clean, timestamp, prior


def first_difference(expected, supplied):
    for key in expected:
        if json.dumps(expected[key], sort_keys=True) != json.dumps(supplied.get(key), sort_keys=True):
            return key
    return None


def verify(doc, stage):
    """Re-derive the whole intermediate from the input it carries and require exact equality of
    every member, provenance and holds included. Returns (input, timestamp, prior)."""
    raw, timestamp, prior = reconstruct(doc, stage)
    expected = derive(raw, timestamp, prior, upto=stage)
    if json.dumps(expected, sort_keys=True) != json.dumps(doc, sort_keys=True):
        section = first_difference(expected, doc) or "document"
        raise InputError(f"{section} does not re-derive from the screened input it carries; "
                         f"the {STAGE_NAMES[stage]} output was edited or is from another engine version")
    return raw, timestamp, prior


def run(engine, argv, body):
    """Run an engine body; an InputError prints one value-free line and exits 2 with nothing written."""
    try:
        return body(argv)
    except InputError as error:
        print(f"{engine}: input error: {error}; nothing written", file=sys.stderr)
        return 2
