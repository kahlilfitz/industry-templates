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
must appear as a standalone number in that paragraph or in a linked evidence entry's title or
description (never in an ID, type, source or confidence), and every evidence ID must be indexed.
In a known register section every record-shaped line (a list item, or a line carrying one of that
register's field labels) must parse; one that does not is an error, never silently dropped. Every
other non-blank line must be one of the documented fixed lines, or it is refused by file, section
and position (never echoed): the client-data register's 'Handling status: <status>', '- <ID>:
<description>' and 'Check basis: <text>' lines, and the licensed-content register's explicit none
statement 'No licensed or third-party content.' as the section's only line (the brand-check
register defines no none statement). Prose such as "TBD" is never read as an empty register. A
section heading that is not a known register, a record or heading line before the first section,
and in the evidence index and prior-findings export a heading after the `# ` title, prose after
the first entry or a file with no entry are errors too. Every draft cover part must be a
documented 'Field: value' pair (COVER_FIELDS), and the criteria extract must give its set ID on one
'Criteria set ID: <ID>' line.
Fields are recognised in any syntactic variant (leading whitespace, a `-`, `*`, `+` or numbered
bullet, bold or backtick emphasis, key case, separators and spacing before the colon): a register
field written as a client-data entry, an entry or Check basis line that carries another register
field label, a set-ID line under a criteria section, a cover field outside the cover block, and a
disclaimer heading or page marker in a variant form are refused, never silently ignored. Every raw
ID that reaches the review input (register entry IDs, cover Engagement and Document ID, criteria
set ID, disclaimer types) is refused in a label form the engines write themselves (#8.11).
Missing is not empty: a raw file that is missing (release-registers.md excepted: a missing
registers file or section is a register that was not supplied, which the engines hold), zero
bytes, or only blank lines and headings, and a known register section with a heading and no
lines, are errors, never parsed as a list with no entries.
Classification fields (class, label, hedging_present, limitation_present, stated_basis,
scope_aligned), prior-finding detail and extraction confidence are ingest judgements: they are
listed in JUDGEMENT_KEYS and are not re-derived, but each is type- and range-checked by
judgement_problems (a confidence is a finite number in 0..1, a class is one of the four contract
classes, a location has a text section and label and positive integer page and paragraph, flags
are true/false), so "high", {} or "certain" never pass. Any other field is reported, so a new
fixture value cannot be added without a raw source or a documented rule. The review input is
loaded with the engines' strict JSON loader (integers within +/-(2^53 - 1), finite numbers,
quality-gate-criteria.md #8.12), and IDs are indexed and compared in the engines' canonical form
(assertion_rules.canonical_id, #8.11): evidence, prior-finding, brand-check and licensed-content
IDs, every other *_id field and each assertion's evidence_ids, so `ev_b1` matches `EV-B1` exactly as
the engines match it. Sample and population sizes are compared as exact Decimals, never floats.
Reports never quote a raw-pack or review-input value, ID or member name: they give the path or line,
the expected form and at most a content-free description (assertion_rules.describe, #8.9), and an
unexpected error is reported by its type only, never as a traceback.

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
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "assertion-map", "scripts"))
import assertion_rules as rules  # noqa: E402  (the engines' strict loader and canonical comparison forms)

CONTRACT_VERSION = "ps.deliverable-review-quality-gate.v1"
CRITERIA_FLOOR = ["quality-gate-criteria.md #1-#8", "severity-rules.md #1-#4"]
PAGE_MARKER = re.compile(r"^\[Page (\d{1,9})\]$")
# Line-oriented patterns use [ \t] and [^\r\n], never \s, so a blank labelled field can never swallow the next line.
SECTION_NUMBER = re.compile(r"^\d+(?:\.\d+)*\.?[ \t]+")
CRITERIA_SET_ID = re.compile(r"^Criteria set ID:[ \t]*([^\r\n]*?)[ \t]*$", re.MULTILINE)
LOCATION = re.compile(r"^(?P<section>.+?), page (?P<page>\d{1,9}), paragraph (?P<paragraph>\d{1,9}), (?P<label>.+)$")
CONF = r"\d{1,3}(?:\.\d{1,9})?"
EVIDENCE = re.compile(r"^- (?P<id>EV-[\w-]+): (?P<title>.+?)\. (?P<desc>.*?) ?Type: (?P<type>\w+)\. Source: (?P<source>[\w ]+)\. Confidence: (?P<conf>" + CONF + r")\.$")
PRIOR = re.compile(r"^- (?P<id>PR-[\w-]+): (?P<request>.+?) Tracker status: (?P<status>closed|open)[^.]*\. Document check: fix (?P<fix>present|absent)[^.]*\. Location: (?P<loc>.+?)\. Confidence: (?P<conf>" + CONF + r")\.$")
BRAND = re.compile(r"^- (?P<id>[\w-]+): (?P<status>\w+)\. (?P<title>.+?)\. (?P<detail>.+?) Legal or release control: (?P<legal>yes|no)\. Location: (?P<loc>.+?)\. Confidence: (?P<conf>" + CONF + r")\. Criteria: (?P<crit>.+?)\.$")
LICENSED = re.compile(r"^- (?P<id>[\w-]+): (?P<detail>.+?) Attribution present: (?P<attr>yes|no)\. License status: (?P<status>[\w ]+)\. Location: (?P<loc>.+?)\. Confidence: (?P<conf>" + CONF + r")\. Register: (?P<register>.+?)\. Criteria: (?P<crit>.+?)\.$")
NO_ASSURANCE = re.compile(r"\bnot (?:provide |be treated as |an? )?assurance\b", re.IGNORECASE)
RELIANCE = re.compile(r"\bmay not be relied (?:up)?on\b|\breliance\b", re.IGNORECASE)
# A number is a standalone token: digits glued to a letter, digit, "_" or "." on either side (EV-X30, EV-30X, X30Y,
# v0.7, 30.5x) are part of an ID or label. A sentence-ending period or comma after the number still ends it ("30.").
NUMBER = re.compile(r"(?<![\w.])[0-9][0-9,]*(?:\.[0-9]+)?(?!\w|\.\w)")
# A record-shaped line: a list item, or a line carrying one of its section's field labels. In a known section every one
# must parse; a line that does not is a PackError, never silently dropped.
RECORD_ITEM = re.compile(r"^(?:[-*+]|[0-9]{1,9}[.)])[ \t]")
HANDLING_LINE = re.compile(r"^handling[ \t]+status\b", re.IGNORECASE)
HANDLING = re.compile(r"^Handling status: (\w+)$")
# The client-data register's other documented lines: one entry per client extract used, and the check basis.
CLIENT_DATA_ENTRY = re.compile(r"^- (?P<id>[\w-]+): [^\r\n]*[^ \t\r\n][^\r\n]*$")
CHECK_BASIS = re.compile(r"^Check basis: [^\r\n]*[^ \t\r\n][^\r\n]*$")
# The only documented explicit "none" statement: the licensed-content register's opening sentence, alone in its section.
LICENSED_NONE = re.compile(r"^No licensed or third-party content\.(?:[ \t][^\r\n]*)?$")
CRITERIA_SET_LINE = re.compile(r"^[ \t]*criteria[ \t]+set[ \t]+id\b", re.IGNORECASE)
# r15-C: a declared field is recognised in every syntactic variant, never only in its documented spelling: leading
# whitespace, one list bullet (-, *, + or a number), bold, italic or backtick emphasis, any case and any spacing or
# separator (-, _, .) between its words, with optional space before the colon. field_key gives a line's (or a cover
# part's) leading key in that folded form; label_pattern finds a field label anywhere in a line in any of those forms.
LEADING_BULLET = re.compile(r"^[ \t]*(?:[-*+]|[0-9]{1,9}[.)])[ \t]+")
EMPHASIS = re.compile(r"[*`]")
# A typed disclaimer heading ('Disclaimer - <type>') in any other case, dash or separator, and a [Page N] marker in any
# other spelling, would otherwise be read as an ordinary section or as body text.
DISCLAIMER_HEADING = re.compile(r"^Disclaimer - (.+)$")
DISCLAIMER_LIKE = re.compile(r"^Disclaimer[ \t]*[-\u2010-\u2015\u2212:|]")
PAGE_MARKER_LIKE = re.compile(r"^\[[ \t]*page\b[^\]]*\]$", re.IGNORECASE)
# Documented cover fields (deliverable-ingest step 5); Status is recorded on the cover but not derived.
COVER_FIELDS = ("Status", "Document type", "Client", "Client aliases", "Engagement", "Document ID", "Version",
                "Confidentiality marking", "Distribution")
COVER_KEYS = {rules.canonical_id(field) for field in COVER_FIELDS}
RECORD_LABELS = {
    "brand-check register": ("Legal or release control:", "Criteria:"),
    "licensed-content register": ("Attribution present:", "License status:", "Register:"),
    "evidence index": ("Type:", "Source:", "Confidence:"),
    "prior-review findings": ("Tracker status:", "Document check:", "Location:"),
}
MISSING = object()

JUDGEMENT_KEYS = {
    "deliverable": {"confidence"},
    "criteria": {"confidence"},
    "assertion": {"assertion_id", "class", "location", "hedging_present", "limitation_present", "stated_basis", "scope_aligned", "confidence"},
    "prior_finding": {"detail"},
}
ASSERTION_CLASSES = tuple(sorted(rules.SUPPORT_TYPES_BY_CLASS))
ASSERTION_FLAGS = ("hedging_present", "limitation_present", "stated_basis", "scope_aligned")
ORDER_FREE = {"present_disclaimer_types", "required_language", "present_language"}
REGISTER_IDS = {"brand_checks": "check_id", "licensed_content": "content_id"}


class PackError(ValueError):
    """A raw pack that cannot be parsed. Messages name a line or position, never the pack's text."""


def emit(line=""):
    """Print one line backslash-escaped to ASCII, so a cp1252 or ASCII console or pipe can always show it."""
    print(str(line).encode("ascii", "backslashreplace").decode("ascii"))


def field_key(text):
    """The folded key of a 'key: value' line or cover part in any variant form (r15-C): leading whitespace and one list
    bullet removed, emphasis (*, `) removed, then rules.canonical_id (case, spacing and -, _, . separators folded).
    None when the text has no colon, or its key is blank or longer than any field name."""
    body = EMPHASIS.sub("", LEADING_BULLET.sub("", text, count=1))
    key, sep, _ = body.partition(":")
    if not sep or len(key) > 60:
        return None
    return rules.canonical_id(key) or None


def label_pattern(labels):
    """One regex finding any of `labels` ('Field name:') anywhere in an emphasis-stripped line, in any case and with any
    spacing or -, _, . separator between its words and before the colon (r15-C)."""
    alternatives = ["[ \t_.-]+".join(map(re.escape, label.rstrip(":").split())) for label in labels]
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(alternatives) + r")[ \t]*:", re.IGNORECASE)


def declares(line, pattern):
    return pattern.search(EMPHASIS.sub("", line)) is not None


def unreserved(value, where):
    """r15-A: a raw-pack ID or key in a label form the engines write themselves (rules.reserved_label: the AM-, GC- or
    SR- finding namespace, or a positional label such as brand-check-2 or withheld-finding-1, in any case or separator
    spelling) is refused naming its position only, exactly as the engines refuse it (quality-gate-criteria.md #8.11)."""
    if rules.reserved_label(value):
        raise PackError(f"{where} gives an ID in a label form the engines write themselves ({rules.RESERVED_LABEL_RULE})")
    return value


RECORD_LABEL_PATTERNS = {kind: label_pattern(labels) for kind, labels in RECORD_LABELS.items()}
# The field labels of the release registers' documented lines: none may appear before the first section, and a
# client-data entry or check basis may not carry one (it would be another line's or register's field, silently ignored).
REGISTER_FIELD_LABELS = (("Handling status:", "Check basis:") + RECORD_LABELS["brand-check register"]
                         + RECORD_LABELS["licensed-content register"])
PREAMBLE_REGISTER_LABELS = label_pattern(REGISTER_FIELD_LABELS)
REGISTER_FIELD_KEYS = {rules.canonical_id(label.rstrip(":")) for label in REGISTER_FIELD_LABELS}


def record_match(pattern, line, kind, where):
    """Parse one line of a known register section. A record-shaped line (a list item, or one carrying a field label of
    that register in any case, spacing or emphasis variant) that the pattern does not match raises PackError naming only
    its position; prose lines return None. A record ID blank after the fold, or in a reserved label form, is refused."""
    match = pattern.match(line)
    if match is None and (RECORD_ITEM.match(line) or declares(line, RECORD_LABEL_PATTERNS[kind])):
        raise PackError(f"{where} is a record line of the {kind} that does not follow the documented line format; fix or remove it")
    if match is not None and "id" in pattern.groupindex and rules.key_of(match["id"]) is None:
        # An ID blank after the fold (for example "-" or "_") names nothing and must never match another (#8.17).
        raise PackError(f"{where} is a record line of the {kind} whose ID is blank after Unicode, case and separator folding; IDs must state a value")
    if match is not None and "id" in pattern.groupindex:
        unreserved(match["id"], where)
    return match


def show(value):
    """Content-free description of a raw-pack or review-input value (rules.describe: JSON type and size, never its
    text), so a mismatch report can never echo embedded instructions (quality-gate-criteria.md #8.9)."""
    return rules.describe(value)


def is_id_key(key):
    return isinstance(key, str) and rules.is_id_field((key,))


def same_value(key, expected, actual):
    """Equality as the engines see it: IDs (any *_id member) by rules.keys_match, so two blank IDs never match
    (quality-gate-criteria.md #8.11, #8.17), everything else exactly."""
    if is_id_key(key) and isinstance(expected, str) and isinstance(actual, str):
        return rules.keys_match(expected, actual)
    return expected == actual


def position(text, where):
    """A page or paragraph number from the raw pack: 1 to 9 digits and at least 1 (quality-gate-criteria.md #8.12)."""
    value = int(text)
    if value < rules.MIN_POSITION:
        raise PackError(f"{where} gives a page or paragraph number below {rules.MIN_POSITION}")
    return value


def read_text(path, label):
    """A raw-pack file's text. Missing is not empty: a missing file, and one that is zero bytes or holds only blank
    lines or headings, states nothing, so it is a PackError naming the file by its fixed `label`, never parsed as a
    file with no records (which would derive an explicit, clean empty list)."""
    if not os.path.isfile(path):
        raise PackError(f"{label} is missing; a missing raw file is never read as an empty one")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not any(line.strip() and not line.lstrip().startswith("#") for line in text.splitlines()):
        raise PackError(f"{label} is empty (zero bytes, or only blank lines or headings); an empty file is not an empty register - list its entries or state that there are none")
    return text


def section_name(heading):
    return SECTION_NUMBER.sub("", heading.strip())


def parse_draft(text):
    """Return (title, cover fields, blocks keyed by (page, paragraph), disclaimer clause titles)."""
    lines = text.splitlines()
    paginated = any(PAGE_MARKER.match(line.strip()) for line in lines)
    page, paragraph, section, title = 1, 0, None, None
    blocks, current, disclaimers, pages = {}, [], [], set()

    def flush():
        nonlocal paragraph
        if current:
            paragraph += 1
            if (page, paragraph) in blocks:
                raise PackError("draft has two blocks at the same page and paragraph; a later one would overwrite the earlier")
            blocks[(page, paragraph)] = {"section": section, "text": " ".join(current), "lines": list(current)}
            current.clear()

    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        marker = PAGE_MARKER.match(line)
        if marker:
            flush()
            page, paragraph = position(marker.group(1), f"draft line {number}"), 0
            # A repeated page marker would restart paragraph numbering and overwrite that page's blocks.
            if page in pages:
                raise PackError(f"draft repeats a page marker (line {number}); page markers must be unique")
            pages.add(page)
        elif line.startswith("# "):
            flush()
            title, section = line[2:].strip(), "Cover"
        elif line.startswith("#"):
            flush()
            section = section_name(line.lstrip("#"))
            clause = DISCLAIMER_HEADING.match(section)
            if (section[:10].lower() == "disclaimer" and not section.startswith("Disclaimer")) or (DISCLAIMER_LIKE.match(section) and not clause):
                raise PackError(f"draft line {number} is a disclaimer heading that does not follow '## Disclaimer - <type>' (case, dash or separator); "
                                "it would be read as an ordinary section and its disclaimer type dropped - fix it")
            if clause:
                disclaimers.append(unreserved(clause.group(1).strip().lower().replace(" ", "_"), f"draft line {number} disclaimer type"))
        elif PAGE_MARKER_LIKE.match(line):
            raise PackError(f"draft line {number} is a page marker that does not follow '[Page N]'; it would be read as body text and shift paragraph numbering - fix it")
        elif not line:
            flush()
        else:
            current.append(line)
    flush()
    if not paginated and any(key[0] != 1 for key in blocks):
        raise PackError("unpaginated draft produced a page other than 1")
    cover, blank = {}, set()
    first = next((block for key, block in sorted(blocks.items()) if block["section"] == "Cover"), None)
    for number, line in enumerate(first["lines"] if first else [], 1):
        for part in line.split(" | "):
            key, sep, value = part.partition(": ")
            if not sep:
                # "Field:" with nothing after it is a blank field (missing); anything else is not a cover field at all.
                if part.strip().endswith(":") and part.strip()[:-1].strip():
                    blank.add(part.strip()[:-1].strip())
                    continue
                raise PackError(f"draft cover line {number} has a part that is not a 'Field: value' pair; a cover part is never skipped - fix or remove it")
            if key.strip() in cover:
                raise PackError(f"draft cover repeats a field name ({show(key.strip())}); a later value would overwrite the earlier")
            cover[key.strip()] = value.strip()
    if any(key not in COVER_FIELDS for key in set(cover) | blank):
        raise PackError(f"draft cover gives a field that is not a documented cover field ({', '.join(COVER_FIELDS)}); a cover field is never skipped - fix or remove it")
    # A cover field belongs to the first Cover block only. One written anywhere else (a second cover block, or a body
    # line), in any spelling (field_key), would be silently ignored, so it is refused by page and paragraph (r15-C).
    for index, (_, block) in enumerate(sorted(blocks.items()), 1):
        if block is first:
            continue
        for line in block["lines"]:
            if any(field_key(part) in COVER_KEYS for part in line.split("|")):
                raise PackError(f"draft paragraph {index} (counting every paragraph from the top) gives a cover field ({', '.join(COVER_FIELDS)}) "
                                "outside the cover block; it would be silently ignored - move it into the cover block or remove it")
    for field in ("Engagement", "Document ID"):
        if cover.get(field):
            unreserved(cover[field], f"draft cover field {field}")
    return title, cover, blocks, disclaimers


def parse_location(text, where):
    match = LOCATION.match(text.strip())
    if not match:
        raise PackError(f"{where}: Location ({show(text)}) does not follow '<section>, page N, paragraph N, <label>'")
    return {"section": match["section"], "page": position(match["page"], where), "paragraph": position(match["paragraph"], where), "label": match["label"]}


def register_sections(text):
    """Split release-registers.md into its sections. Before the first section heading the file holds only its title
    and description: a record-shaped line there (a list item, a Handling status line or a register field label) belongs
    to no register and is a PackError, never skipped."""
    sections, name, first = {}, None, True
    labels = PREAMBLE_REGISTER_LABELS
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            name = line[3:].strip()
            if name in sections:
                raise PackError(f"release registers repeat a section heading (line {number}); a later one would replace the earlier")
            sections[name] = []
        elif name and line.strip():
            sections[name].append(line.strip())
        elif line.strip():
            stripped = line.strip()
            if (RECORD_ITEM.match(stripped) or HANDLING_LINE.match(EMPHASIS.sub("", stripped)) or declares(stripped, labels)
                    or (stripped.startswith("#") and not (first and line.startswith("# ")))):
                raise PackError(f"release-registers.md line {number} is a record or heading line before the first register section; it belongs to no register - move it under its section heading or remove it")
            first = False
    return sections


REGISTER_SECTIONS = ("Client-data handling register", "Brand and formatting checks", "Licensed and third-party content register")


def unrecognised(section_label, number, expected):
    """A non-blank line of a known register section that is neither a record nor a documented fixed line. It is
    refused by section name and position (never echoed): prose such as "TBD" is never read as an empty register."""
    return PackError(f"release-registers.md section {section_label} entry {number} is not a recognised line of that register "
                     f"(expected {expected}); a placeholder or prose line is never read as an empty register - fix or remove it")


def parse_registers(path):
    """Return client_data_handling, brand_checks and licensed_content. A missing file or section is a register that was
    not supplied (unknown/None), which the engines hold; a file that is present but empty, or a known section heading
    with no line under it, states nothing and is a PackError, never an explicit empty register. Every non-blank line of
    a known section must be one of its documented lines (unrecognised() otherwise), and a section heading that is not
    one of REGISTER_SECTIONS is refused rather than ignored."""
    sections = register_sections(read_text(path, "release-registers.md")) if os.path.exists(path) else {}
    if any(name not in REGISTER_SECTIONS for name in sections):
        raise PackError(f"release-registers.md has a section heading that is not a known register ({'; '.join(REGISTER_SECTIONS)}); its lines would be skipped - rename or remove it")
    for section_label in REGISTER_SECTIONS:
        if section_label in sections and not sections[section_label]:
            raise PackError(f"release-registers.md section {section_label} has a heading and no lines; list its entries or state that there are none")
    handling, seen = "unknown", False
    for number, line in enumerate(sections.get("Client-data handling register", []), 1):
        if not HANDLING_LINE.match(line):
            entry, basis = CLIENT_DATA_ENTRY.match(line), CHECK_BASIS.match(line)
            if entry is None and basis is None:
                raise unrecognised("Client-data handling register", number, "'Handling status: <status>', '- <ID>: <description>' or 'Check basis: <text>'")
            where = f"client-data handling register entry {number}"
            if entry is not None:
                if field_key(line) in REGISTER_FIELD_KEYS:
                    raise PackError(f"{where} is a register field written as a client-data entry ('- <field>: ...' in a variant spelling); "
                                    "a declared field is never read as an entry - write it in its documented form or remove it")
                if rules.key_of(entry["id"]) is None:
                    raise PackError(f"{where} is a client-data entry whose ID is blank after Unicode, case and separator folding; IDs must state a value")
                unreserved(entry["id"], where)
            if declares(line.split(":", 1)[1], PREAMBLE_REGISTER_LABELS):
                raise PackError(f"{where} carries a field label of another register line or register (in any spelling); "
                                "it would be silently ignored here - move it to its own line or section, or remove it")
            continue
        match = HANDLING.match(line)
        if match is None:
            raise PackError(f"client-data handling register entry {number} is a Handling status line that does not follow 'Handling status: <status>'")
        if seen:
            raise PackError(f"client-data handling register entry {number} repeats the Handling status line; a later value would overwrite the earlier")
        handling, seen = match.group(1), True
    brand = None
    if "Brand and formatting checks" in sections:
        brand = []
        for number, line in enumerate(sections["Brand and formatting checks"], 1):
            match = record_match(BRAND, line, "brand-check register", f"brand check entry {number}")
            if match is None:
                raise unrecognised("Brand and formatting checks", number, "a brand-check record; this register has no 'none' statement")
            brand.append({"check_id": match["id"], "status": match["status"], "legal_or_release_control": match["legal"] == "yes",
                          "title": match["title"], "detail": match["detail"], "location": parse_location(match["loc"], f"brand check entry {number}"),
                          "confidence": float(match["conf"]), "citation": match["crit"]})
    licensed = None
    if "Licensed and third-party content register" in sections:
        licensed, lines = [], sections["Licensed and third-party content register"]
        for number, line in enumerate(lines, 1):
            match = record_match(LICENSED, line, "licensed-content register", f"licensed-content entry {number}")
            if match is None:
                if LICENSED_NONE.match(line) and len(lines) == 1:
                    continue
                raise unrecognised("Licensed and third-party content register", number,
                                   "a licensed-content record, or 'No licensed or third-party content.' as the section's only line")
            licensed.append({"content_id": match["id"], "attribution_present": match["attr"] == "yes", "license_status": match["status"],
                             "detail": match["detail"], "location": parse_location(match["loc"], f"licensed-content entry {number}"), "confidence": float(match["conf"]),
                             "citation": f"{match['register']}; {match['crit']}"})
    return handling, brand, licensed


def record_lines(text, pattern, kind, label):
    """The match for each line of an evidence index or prior-findings export, by line (None for a blank, title or
    description line), so callers number lines with enumerate. The file opens with its `# ` title and description
    prose; from the first record on every non-blank line must be a record of `kind`. A heading after the title, prose
    after the first entry, or a file with no entry is a PackError naming the file and line, never skipped: prose is
    never read as an empty register."""
    matches, started, first = [], False, True
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        match = record_match(pattern, line, kind, f"{label} line {number}") if line else None
        matches.append(match)
        if not line:
            continue
        if match is not None:
            started = True
        elif started or (line.startswith("#") and not (first and raw.startswith("# "))):
            raise PackError(f"{label} line {number} is not a record of the {kind} (a heading after the title, or prose after the first entry); "
                            "a placeholder or prose line is never skipped - fix or remove it")
        first = False
    if not started:
        raise PackError(f"{label} lists no entries; its prose is never read as an empty register - list its entries")
    return matches


def parse_evidence(text):
    """Return (items, {canonical evidence ID: title and description}); IDs are compared in canonical form
    (rules.canonical_id). Only the title and description are kept for the size check: a number in the evidence ID,
    type, source or confidence is metadata and never substantiates a sample or population size."""
    items, lines = [], {}
    for number, match in enumerate(record_lines(text, EVIDENCE, "evidence index", "supporting-evidence-index.md"), 1):
        if match is None:
            continue
        items.append({"evidence_id": match["id"], "type": match["type"], "title": match["title"], "confidence": float(match["conf"]),
                      "source": "connector:" + match["source"].strip().lower().replace(" ", "-"),
                      "citation": f"supporting-evidence-index.md {match['id']}"})
        if rules.key_of(match["id"]) in lines:
            raise PackError(f"supporting evidence index repeats an evidence ID (line {number}, equal exactly or after folding); evidence IDs must be unique")
        lines[rules.key_of(match["id"])] = f"{match['title']}. {match['desc']}"
    return items, lines


def parse_prior(text):
    items = []
    for number, match in enumerate(record_lines(text, PRIOR, "prior-review findings", "prior-review-findings.md"), 1):
        if match is None:
            continue
        closed, fixed = match["status"] == "closed", match["fix"] == "present"
        citation = f"prior-review-findings.md {match['id']}"
        if closed and not fixed:
            citation += "; quality-gate-criteria.md #7.1-#7.2"
        items.append({"finding_id": match["id"], "claimed_closed": closed, "document_fix_present": fixed,
                      "location": parse_location(match["loc"], f"prior-review-findings.md line {number}"), "confidence": float(match["conf"]),
                      "source": "skill:criteria-retrieve", "citation": citation})
    return items


def criteria_set_id(text):
    """The criteria set ID from the extract's single 'Criteria set ID: <ID>' line (blank value: MISSING), which belongs
    to the extract's header, before the first section heading. The rest of the extract is the criteria prose itself
    and is not derived (criteria_sections is the fixed CRITERIA_FLOOR). A second set-ID line, a set-ID line under a
    criteria section, or a line naming the set ID in another form (a bullet, emphasis, another case or separator:
    field_key) is a PackError, never ignored. A set ID in a reserved label form is refused (unreserved)."""
    found, header = None, True
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("##"):
            header = False
        if not (CRITERIA_SET_LINE.match(line) or field_key(line) == "criteria set id"):
            continue
        match = CRITERIA_SET_ID.match(line)
        if match is None:
            raise PackError(f"qrm-gate-criteria-extract.md line {number} names the criteria set ID but does not follow 'Criteria set ID: <ID>'")
        if not header:
            raise PackError(f"qrm-gate-criteria-extract.md line {number} gives the criteria set ID under a criteria section; it belongs in the extract's header, before the first section heading")
        if found is not None:
            raise PackError(f"qrm-gate-criteria-extract.md repeats the criteria set ID line (line {number}); a later value would be ignored")
        found = match
    return unreserved(found.group(1), "qrm-gate-criteria-extract.md criteria set ID") if found and found.group(1) else MISSING


def derive(scenario_dir):
    """Rebuild every source-derived field of review-input.json from scenario_dir/raw."""
    scenario = os.path.basename(os.path.normpath(scenario_dir))
    raw = os.path.join(scenario_dir, "raw")
    title, cover, blocks, disclaimers = parse_draft(read_text(os.path.join(raw, "draft-deliverable.md"), "draft-deliverable.md"))
    client = cover.get("Client")
    recipients = [item.strip() for item in cover["Distribution"].split(";")] if cover.get("Distribution") else None
    third_party = any(client is None or rules.canonical_name(client) not in rules.canonical_name(item) for item in recipients or [])
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
    extract = read_text(os.path.join(raw, "qrm-gate-criteria-extract.md"), "qrm-gate-criteria-extract.md")
    evidence, evidence_lines = parse_evidence(read_text(os.path.join(raw, "supporting-evidence-index.md"), "supporting-evidence-index.md"))
    return {
        "contract_version": CONTRACT_VERSION, "engagement_id": cover.get("Engagement", MISSING), "scenario_id": scenario,
        "deliverable": deliverable,
        "criteria": {"criteria_set_id": criteria_set_id(extract), "criteria_sections": CRITERIA_FLOOR,
                     "source": "skill:criteria-retrieve", "citation": f"demo-data/{scenario}/raw/qrm-gate-criteria-extract.md"},
        "evidence_set": evidence,
        "prior_findings": parse_prior(read_text(os.path.join(raw, "prior-review-findings.md"), "prior-review-findings.md")),
        "findings": [], "escalations": [],
        "provenance": {"engines": [], "demo_scenario": scenario},
        "_blocks": blocks, "_evidence_lines": evidence_lines,
    }


def numbers_in(text):
    """Every number written in text, as exact Decimals: no float conversion, so no size can overflow or round."""
    found = set()
    for token in NUMBER.findall(text):
        try:
            found.add(Decimal(token.replace(",", "")))
        except InvalidOperation:
            continue
    return found


def block_at(location, blocks):
    """The draft block a location points at; None unless page and paragraph are both positions (rules.is_position)."""
    if not isinstance(location, dict) or not all(rules.is_position(location.get(key)) for key in ("page", "paragraph")):
        return None
    return blocks.get((location["page"], location["paragraph"]))


def location_problems(label, location, blocks):
    if not isinstance(location, dict):
        return [f"{label}.location: must be an object, got {show(location)}"]
    page, paragraph = location.get("page"), location.get("paragraph")
    if not (rules.is_position(page) and rules.is_position(paragraph)):
        # judgement_problems reports the type or range; nothing can be looked up.
        return [f"{label}: location page {show(page)} / paragraph {show(paragraph)} cannot be looked up in the draft"]
    block = blocks.get((page, paragraph))
    if block is None:
        return [f"{label}.location: page and paragraph point at no paragraph of the draft"]
    section = location.get("section")
    if not isinstance(section, str) or not section or not (block["section"] or "").startswith(section):
        return [f"{label}.location.section: the located paragraph is under a different section ({show(section)})"]
    return []


def compare_value(path, expected, actual, problems):
    key = path.rsplit(".", 1)[-1]
    if expected is MISSING:
        problems.append(f"{path}: the review input has {show(actual)} with no raw source")
    elif key in ORDER_FREE and isinstance(expected, list) and isinstance(actual, list):
        if sorted(map(json.dumps, expected)) != sorted(map(json.dumps, actual)):
            problems.append(f"{path}: the review input ({show(actual)}) does not hold the same entries as the raw pack ({show(expected)})")
    elif not same_value(key, expected, actual):
        problems.append(f"{path}: the review input ({show(actual)}) does not match the raw pack ({show(expected)})")


def compare_object(path, expected, actual, judgement, problems):
    if not isinstance(actual, dict):
        problems.append(f"{path}: expected an object, got {show(actual)}")
        return
    for key in sorted(set(expected) | set(actual)):
        if key in judgement:
            continue
        shown = f"{path}.{rules.path_key(key)}"
        if key not in actual:
            problems.append(f"{shown}: the raw pack gives {show(expected[key])} but the review input omits it")
        elif key not in expected:
            problems.append(f"{shown}: {show(actual[key])} is neither derived from the raw pack nor a declared ingest judgement")
        elif key in REGISTER_IDS and isinstance(expected[key], list) and isinstance(actual[key], list):
            compare_list(shown, expected[key], actual[key], REGISTER_IDS[key], set(), problems)
        else:
            compare_value(shown, expected[key], actual[key], problems)


def id_key(value):
    """Comparison form of an ID (rules.key_of); a non-string is compared by its JSON form. An ID blank after the fold
    gets a fresh object, so it never equals another blank ID (quality-gate-criteria.md #8.17)."""
    if not isinstance(value, str):
        return json.dumps(value, sort_keys=True)
    key = rules.key_of(value)
    return key if key is not None else object()


def repeated_positions(ids):
    """Positions of the first ID that repeats (exactly or after canonical folding), or None."""
    seen = {}
    for index, item in enumerate(ids):
        fold = id_key(item)
        if fold in seen:
            return seen[fold], index
        seen[fold] = index
    return None


def compare_list(path, expected, actual, key, judgement, problems):
    """Match register entries by ID in canonical form (rules.canonical_id), in order, then compare each entry."""
    if not isinstance(actual, list):
        problems.append(f"{path}: the raw pack gives a list of {len(expected)}, the review input has {show(actual)}")
        return
    if not all(isinstance(item, dict) for item in actual):
        problems.append(f"{path}: every entry must be an object")
        return
    want, have = [item[key] for item in expected], [item.get(key) for item in actual]
    for side, ids in (("raw pack", want), ("review input", have)):
        repeat = repeated_positions(ids)
        if repeat:
            problems.append(f"{path}: the {side} repeats {key} at positions {repeat[0]} and {repeat[1]} (equal exactly or after folding); IDs must be unique")
            return
    if len(want) != len(have):
        problems.append(f"{path}: the raw pack gives {len(want)} entries, the review input has {len(have)}")
        return
    differing = [index for index, (exp, act) in enumerate(zip(want, have)) if id_key(exp) != id_key(act)]
    if differing:
        problems.append(f"{path}[{differing[0]}].{key}: the review input ({show(have[differing[0]])}) is not the raw pack's ID at that position ({show(want[differing[0]])})"
                        + (f"; {len(differing) - 1} more position(s) differ" if len(differing) > 1 else ""))
        return
    for index, (exp, act) in enumerate(zip(expected, actual)):
        compare_object(f"{path}[{index}]", exp, act, judgement, problems)


def assertion_problems(index, assertion, blocks, evidence_lines):
    label = f"assertions[{index}]"
    if not isinstance(assertion, dict):
        return [f"{label}: must be an object, got {show(assertion)}"]
    location = assertion.get("location")
    problems = location_problems(label, location, blocks)
    block = block_at(location, blocks)
    allowed = JUDGEMENT_KEYS["assertion"] | {"text", "evidence_ids", "sample_size", "population_size", "source", "citation"}
    problems += [f"{label}.{rules.path_key(member)}: value is neither derived from the raw pack nor a declared ingest judgement" for member in sorted(set(assertion) - allowed)]
    text = assertion.get("text")
    if not isinstance(text, str):
        problems.append(f"{label}.text: must be a string, got {show(text)}")
    elif block and text.rstrip(".") not in block["text"]:
        problems.append(f"{label}.text: not quoted from the paragraph at its location")
    if block and assertion.get("citation") != f"draft-deliverable.md p{location['page']} para{location['paragraph']}":
        problems.append(f"{label}.citation: {show(assertion.get('citation'))} does not match its location")
    if assertion.get("source") != "skill:deliverable-ingest":
        problems.append(f"{label}.source: must be skill:deliverable-ingest, got {show(assertion.get('source'))}")
    evidence_ids = assertion.get("evidence_ids")
    linked = []
    if evidence_ids is not None and not isinstance(evidence_ids, list):
        problems.append(f"{label}.evidence_ids: must be an array, got {show(evidence_ids)}")
    else:
        for position_index, evidence_id in enumerate(evidence_ids or []):
            line = evidence_lines.get(rules.key_of(evidence_id)) if rules.key_of(evidence_id) is not None else None
            if line is None:
                problems.append(f"{label}.evidence_ids[{position_index}]: {show(evidence_id)} is not in the evidence index")
            else:
                linked.append(line)
    context = (block["text"] if block else "") + " " + " ".join(linked)
    for key in ("sample_size", "population_size"):
        value = assertion.get(key)
        if value is None:
            continue
        if not rules.is_integer(value) or value < 0:
            problems.append(f"{label}.{key}: must be a non-negative integer or null, got {show(value) if not rules.is_integer(value) else 'a negative integer'}")
        elif Decimal(value) not in numbers_in(context):
            problems.append(f"{label}.{key}: the value appears in neither the located paragraph nor a linked evidence entry")
    return problems + judgement_problems(label, "assertion", assertion)


def is_confidence(value):
    return rules.is_number(value) and 0 <= value <= 1


def is_iso_timestamp(value):
    """The contract's format: date-time, checked by the engines' own rule (rules.is_timestamp, RFC 3339)."""
    return rules.is_timestamp(value)


def judgement_problems(label, kind, item):
    """Type- and range-check the ingest judgements that are not re-derived (JUDGEMENT_KEYS)."""
    if not isinstance(item, dict):
        return []
    problems = []
    if "confidence" in item or kind == "assertion":
        if not is_confidence(item.get("confidence")):
            problems.append(f"{label}.confidence: ingest judgement must be a number from 0 to 1, got {rules.describe(item.get('confidence'))}")
    if kind == "assertion":
        if not isinstance(item.get("assertion_id"), str) or not item["assertion_id"].strip():
            problems.append(f"{label}.assertion_id: must be a non-blank string, got {rules.describe(item.get('assertion_id'))}")
        if item.get("class") not in ASSERTION_CLASSES:
            problems.append(f"{label}.class: must be one of {', '.join(ASSERTION_CLASSES)}, got {rules.describe(item.get('class'))}")
        location = item.get("location")
        if not isinstance(location, dict):
            problems.append(f"{label}.location: must be an object, got {rules.describe(location)}")
        else:
            for key in ("section", "label"):
                if not isinstance(location.get(key), str) or not location[key].strip():
                    problems.append(f"{label}.location.{key}: must be a non-blank string, got {rules.describe(location.get(key))}")
            for key in ("page", "paragraph"):
                value = location.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                    problems.append(f"{label}.location.{key}: must be a positive integer, got {rules.describe(value)}")
        for key in ASSERTION_FLAGS:
            if (key in item or key == "scope_aligned") and not isinstance(item.get(key), bool):
                problems.append(f"{label}.{key}: ingest judgement must be true/false, got {rules.describe(item.get(key))}")
    if kind == "prior_finding" and "detail" in item and not isinstance(item["detail"], str):
        problems.append(f"{label}.detail: must be a string, got {rules.describe(item['detail'])}")
    if kind == "provenance" and "generated_at" in item and not is_iso_timestamp(item["generated_at"]):
        problems.append(f"{label}.generated_at: must be an ISO-8601 timestamp (RFC 3339 date-time such as 2026-10-01T00:00:00Z), got {rules.describe(item['generated_at'])}")
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
    problems += judgement_problems("deliverable", "deliverable", payload.get("deliverable"))
    problems += judgement_problems("criteria", "criteria", payload.get("criteria"))
    problems += judgement_problems("provenance", "provenance", payload.get("provenance"))
    for index, item in enumerate(payload.get("prior_findings") or []):
        problems += judgement_problems(f"prior_findings[{index}]", "prior_finding", item)
    deliverable = derived["deliverable"]
    for name in ("brand_checks", "licensed_content"):
        for index, item in enumerate(deliverable[name] or []):
            problems += location_problems(f"deliverable.{name}[{index}]", item["location"], blocks)
    for index, item in enumerate(derived["prior_findings"]):
        problems += location_problems(f"prior_findings[{index}]", item["location"], blocks)
    assertions = payload.get("assertions")
    if not isinstance(assertions, list):
        problems.append(f"assertions: must be an array, got {show(assertions)}")
        return problems
    repeat = repeated_positions([item.get("assertion_id") for item in assertions if isinstance(item, dict)])
    if repeat:
        problems.append(f"assertions: the review input repeats assertion_id at positions {repeat[0]} and {repeat[1]} (equal exactly or after folding); IDs must be unique")
    for index, assertion in enumerate(assertions):
        problems += assertion_problems(index, assertion, blocks, evidence_lines)
    return problems


def check_scenario(scenario_dir):
    """The difference list for one scenario. Never raises: a malformed review input or raw pack, or any unexpected
    error, is reported as one content-free problem (its type, never its message), so no traceback or untrusted text
    reaches the output (quality-gate-criteria.md #8.9)."""
    try:
        payload = rules.load_json_file(os.path.join(scenario_dir, "review-input.json"), "review input")
    except rules.InputError as exc:
        return [f"review input is malformed: {exc}"]
    if not isinstance(payload, dict):
        return [f"review input must be a JSON object, got {show(payload)}"]
    # Every section compare reads is validated against the contract first, so a wrongly typed section is a clean
    # refusal, never iterated or skipped (quality-gate-criteria.md #8.16).
    try:
        rules.validate_contract(payload, "assertion_map")
    except rules.InputError as exc:
        return [f"review input: {exc}"]
    try:
        return compare(scenario_dir, payload)
    except PackError as exc:
        return [f"raw pack is malformed: {exc}"]
    except Exception as exc:  # noqa: BLE001 - reported by type only; details may quote untrusted text
        return [f"could not compare the scenario ({type(exc).__name__}; details withheld because they may quote untrusted text)"]


SHIPPED_SCENARIOS = ("scenario-a-happy", "scenario-b-drama")


def scenario_label(scenario_dir, position):
    """A fixed, trusted label for a scenario in the report: a shipped demo's own name, otherwise its position on the
    command line. A directory or file name is untrusted input and is never repeated (quality-gate-criteria.md #8.9)."""
    name = os.path.basename(os.path.normpath(scenario_dir))
    return next((shipped for shipped in SHIPPED_SCENARIOS if shipped == name), f"scenario {position}")


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scenarios = argv or [os.path.join(root, "demo-data", name) for name in sorted(os.listdir(os.path.join(root, "demo-data")))]
    failed = False
    for position, scenario_dir in enumerate(scenarios, start=1):
        problems = check_scenario(scenario_dir)
        emit(f"{scenario_label(scenario_dir, position)}: {'derives from its raw pack' if not problems else f'{len(problems)} difference(s)'}")
        for problem in problems:
            emit("  - " + problem)
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
