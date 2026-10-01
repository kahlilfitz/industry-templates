"""Shared fail-closed sanitizer for untrusted staffing source text."""
import hashlib
import re
import unicodedata


SUSPECT_PATTERNS = (
    re.compile(r"\bignore\s+(?:(?:all|any|the|previous|prior)\s+)?instructions?\b", re.I),
    re.compile(r"\b(?:system|developer)\s+(?:message|prompt|instructions?)\b", re.I),
    re.compile(
        r"(?:^|[\s;|])(?:system|developer|assistant|ai|note\s+to\s+(?:ai|assistant))\s*[:,]",
        re.I,
    ),
    re.compile(r"\bpartner\s+override\b", re.I),
    re.compile(r"\bput\b.{0,80}\bat\s+the\s+top\b.{0,40}\bslate\b", re.I),
    re.compile(r"\btop\s+of\s+the\s+slate\b", re.I),
    re.compile(r"\bpre-?approved\b.{0,80}\bindependence\b", re.I),
    re.compile(r"\bindependence\b.{0,80}\b(?:confirmed|approved|cleared)\b", re.I),
    re.compile(r"\bcall\b.{0,80}\bindependent\b", re.I),
    re.compile(
        r"\b(?i:pick|select|choose|recommend|approve|clear)\s+(?:this\s+)?"
        r"(?:[Cc]andidate|[Cc]onsultant|[Pp]erson|him|her|them|"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
    ),
    re.compile(r"\b(?i:rank|place)\b.{0,80}\b(?i:first|top|#?1)\b"),
    re.compile(
        r"\b(?i:mark|label|treat)\b.{0,80}\b"
        r"(?i:eligible|ineligible|cleared|approved|recommended)\b"
    ),
    re.compile(r"\b(?:do not|don't)\s+(?:mention|report|flag|cite)\b", re.I),
    re.compile(r"\bpre-?cleared\b", re.I),
    re.compile(
        r"\boverride\b.{0,80}\b(?:rule|verdict|constraint|conflict|rank|score|eligibility)\b",
        re.I,
    ),
)
SPLIT_RECORD_PATTERNS = (
    re.compile(
        r"\b(?:system|developer|assistant)\s*[:,].{0,160}"
        r"\b(?:rank|pick|select|choose|recommend|approve|clear|mark|label)\b",
        re.I,
    ),
    re.compile(
        r"\bignore\b.{0,80}\binstructions?\b.{0,160}"
        r"\b(?:rank|pick|select|choose|recommend|approve|clear|override)\b",
        re.I,
    ),
    re.compile(
        r"\bput\b.{0,80}\bat\s+the\s+top\b.{0,80}\bslate\b",
        re.I,
    ),
)

CONFUSABLES = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "І": "I", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X", "У": "Y", "Ѕ": "S",
    "а": "a", "е": "e", "і": "i", "к": "k", "м": "m", "н": "h", "о": "o",
    "р": "p", "с": "c", "т": "t", "х": "x", "у": "y", "ѕ": "s",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K",
    "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Χ": "X", "Υ": "Y",
    "α": "a", "β": "b", "ε": "e", "ι": "i", "κ": "k", "ο": "o", "ρ": "p",
    "τ": "t", "χ": "x", "υ": "y",
})
STRUCTURAL_FIELDS = {
    "candidate_id",
    "role_id",
    "engagement_id",
    "contract_version",
    "start",
    "end",
    "start_date",
    "end_date",
    "resolved_date",
    "generated_at",
    "type",
    "status",
    "disposition",
    "verdict",
    "recommendation_status",
    "source",
    "currency",
}
AGGREGATE_ROLE_FIELDS = {
    "candidate_scores",
    "candidate_slate",
    "recommended_candidates",
}


def normalized_detection_text(text):
    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    )
    normalized = normalized.translate(CONFUSABLES)
    return re.sub(r"\s+", " ", normalized).strip()


def has_format_characters(text):
    return any(unicodedata.category(character) == "Cf" for character in str(text))


def has_mixed_script_token(text):
    for token in re.findall(r"\w+", str(text), flags=re.UNICODE):
        scripts = set()
        for character in token:
            if not character.isalpha():
                continue
            name = unicodedata.name(character, "")
            if name.startswith("LATIN"):
                scripts.add("latin")
            elif name.startswith("CYRILLIC"):
                scripts.add("cyrillic")
            elif name.startswith("GREEK"):
                scripts.add("greek")
        if len(scripts) > 1:
            return True
    return False


def is_suspect(text):
    raw = str(text)
    if has_format_characters(raw) or has_mixed_script_token(raw):
        return True
    normalized = normalized_detection_text(raw)
    return any(pattern.search(normalized) for pattern in SUSPECT_PATTERNS)


def _redacted(text, label):
    digest = hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:12]
    return f"[FLAGGED: instruction-like source {label} redacted; sha256={digest}]"


def safe_citation(text):
    text = str(text).strip()
    return _redacted(text, "citation") if is_suspect(text) else text


def safe_text(text):
    text = str(text).strip()
    return _redacted(text, "text") if is_suspect(text) else text


def _record_texts(value, field_name=None):
    if isinstance(value, dict):
        for key, item in value.items():
            if key not in STRUCTURAL_FIELDS:
                yield from _record_texts(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from _record_texts(item, field_name)
    elif isinstance(value, str):
        yield value


def _record_is_suspect(value):
    texts = list(_record_texts(value))
    if any(is_suspect(text) for text in texts):
        return False
    combined = [normalized_detection_text(" ".join(texts))]
    combined.extend(
        normalized_detection_text("".join(texts[index:]))
        for index in range(len(texts))
    )
    return any(
        pattern.search(text)
        for text in combined
        for pattern in SPLIT_RECORD_PATTERNS
    )


def _is_scan_record(value):
    if "candidate_id" in value:
        return True
    return "role_id" in value and not AGGREGATE_ROLE_FIELDS.intersection(value)


def sanitize_free_text(
    value,
    path,
    escalations,
    field_name=None,
    force_redact=False,
):
    if isinstance(value, dict):
        redact_record = force_redact or (
            _is_scan_record(value) and _record_is_suspect(value)
        )
        return {
            key: sanitize_free_text(
                item,
                f"{path}.{key}",
                escalations,
                key,
                redact_record and key not in STRUCTURAL_FIELDS,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            sanitize_free_text(
                item,
                f"{path}[{index}]",
                escalations,
                field_name,
                force_redact,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, str):
        if force_redact and value.strip():
            label = "citation" if field_name == "citation" else "text"
            safe = _redacted(value.strip(), label)
        else:
            safe = safe_citation(value) if field_name == "citation" else safe_text(value)
        if safe != value.strip():
            escalations.append(
                f"{path}: instruction-like text redacted; review source record"
            )
        return safe
    return value
