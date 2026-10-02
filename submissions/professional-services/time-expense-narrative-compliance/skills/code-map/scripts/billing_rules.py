#!/usr/bin/env python3
"""billing_rules - the deterministic code-map and billing-guideline rules (one rule set, three engines).

- code_map.py builds every entry's code_mapping with code_mapping() (task-phase-codes.md).
- guideline_check.py runs govern(). It recomputes every entry's code mapping and holds an entry whose
  supplied mapping disagrees (client-billing-guidelines.md #13.1), then applies #1-#9 and #11.
- exception_report.py runs reconcile_governed(): govern() again on a copy of the governed data. It lists
  every entry, missing-time item, summary figure and exclusion the supplied data understates or contradicts
  (#13.2), and prints only the re-derived flag detail and citations (rendered_flags).

Constants mirror references/task-phase-codes.md and references/client-billing-guidelines.md section
by section. The model reports these results; it never decides, suppresses or downgrades them.

This file ships as identical copies next to code_map.py, guideline_check.py and exception_report.py;
tests/check_shared_copies.py fails when the copies drift.
"""
import os
import re
import sys
import unicodedata
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signal_policy  # noqa: E402  (shared copy shipped next to each engine)

CODE_MAP_ENGINE = "engine:code_map"
GUIDELINE_ENGINE = "engine:guideline_check"
MAPPING_CITATION = "client-billing-guidelines.md #13.1"
RECONCILE_CITATION = "client-billing-guidelines.md #13.2"

# --- Code mapping (task-phase-codes.md) ----------------------------------------------------

DIRECT_MATCH_CONFIDENCE = 0.92  # task-phase-codes.md #5.1
KEYWORD_MATCH_CONFIDENCE = 0.78  # task-phase-codes.md #5.2
UNKNOWN_CONFIDENCE = 0.40  # task-phase-codes.md #5.3
CODE_MISMATCH_REVIEW_CONFIDENCE = 0.80  # client-billing-guidelines.md #4.2
UNMAPPED = ("UNMAPPED", "UNMAPPED", "Unknown or conflicting activity", "task-phase-codes.md #5.3")

CLASS_MAP = {
    "client_meeting": ("DL", "DL300", "Client meeting or working session", "task-phase-codes.md #3.1"),
    "document_analysis": ("AN", "AN200", "Document analysis tied to a client deliverable", "task-phase-codes.md #2.1"),
    "research": ("AN", "AN220", "Research or options analysis", "task-phase-codes.md #2.2"),
    "deliverable_drafting": ("DL", "DL320", "Drafting or finalizing a client deliverable", "task-phase-codes.md #3.2"),
    "internal_admin": ("NB", "NB900", "Internal non-billable administration", "task-phase-codes.md #4.1"),
    "billing_hygiene": ("BH", "BH910", "Pre-bill and WIP hygiene", "task-phase-codes.md #4.2"),
}
NON_BILLABLE_PHASES = ("NB", "BH")  # task-phase-codes.md #4
KEYWORDS = [
    ("meeting", CLASS_MAP["client_meeting"]),
    ("workshop", CLASS_MAP["client_meeting"]),
    ("analy", CLASS_MAP["document_analysis"]),
    ("research", CLASS_MAP["research"]),
    ("draft", CLASS_MAP["deliverable_drafting"]),
    ("staffing", CLASS_MAP["internal_admin"]),
]


def signal_mapping(signal):
    """Map one linked signal to a code tuple, or None when its class is unknown.

    A signal explicitly marked non-billable that would otherwise map to a billable code maps to
    NB900 (#4.1); billing_hygiene keeps BH910 (#4.2).
    """
    mapping = CLASS_MAP.get(signal.get("activity_class"))
    if signal.get("billable_signal") is False and (mapping is None or mapping[0] not in NON_BILLABLE_PHASES):
        return CLASS_MAP["internal_admin"]
    return mapping


def choose_mapping(entry, linked):
    """Return (mapping tuple, confidence, basis).

    Every linked signal is mapped first; more than one target code (non-billable codes included)
    is a conflict and returns UNMAPPED at 0.40 (#5.3). There is no non-billable short-circuit.
    """
    if linked:
        mappings = [signal_mapping(a) for a in linked]
        known = [m for m in mappings if m is not None]
        codes = {m[1] for m in known}
        if len(codes) > 1:
            return UNMAPPED, UNKNOWN_CONFIDENCE, "conflicting_activity_classes"
        if len(known) == len(mappings) and len(codes) == 1:
            return known[0], DIRECT_MATCH_CONFIDENCE, "direct_activity_class"
        return UNMAPPED, UNKNOWN_CONFIDENCE, "unknown_activity_class"
    text = " ".join([entry.get("draft", {}).get("narrative", "") or "", entry.get("narrative", "") or ""]).lower()
    for token, mapping in KEYWORDS:
        if token in text:
            return mapping, KEYWORD_MATCH_CONFIDENCE, "keyword_inference"
    return UNMAPPED, UNKNOWN_CONFIDENCE, "unmapped"


def code_mapping(entry, linked):
    """The code_mapping object code_map.py writes for one entry (and guideline_check.py recomputes)."""
    (phase, task, label, citation), confidence, basis = choose_mapping(entry, linked)
    submitted_task = entry.get("submitted_task_code")
    submitted_phase = entry.get("submitted_phase_code")
    flags = []
    if task == "UNMAPPED":
        detail = ("linked signals point to different codes (" + ", ".join(sorted({
            f"{signal_policy.redact(a.get('activity_class'))}->{(signal_mapping(a) or ('?', '?'))[1]}" for a in linked}))
            + "); no code is recommended"
                  if basis == "conflicting_activity_classes" else "no activity class or keyword maps to a code")
        if submitted_task:
            detail += f"; submitted {submitted_task} cannot be confirmed"
        flags.append({
            "flag": "unmapped_code",
            "detail": detail,
            "severity": "hold_for_review",
            "source": CODE_MAP_ENGINE,
            "confidence": confidence,
            "citations": ["task-phase-codes.md #5.3", "client-billing-guidelines.md #4.1"],
        })
    elif (submitted_task and submitted_task != task) or (submitted_phase and submitted_phase != phase):
        # Either code can be wrong: a matching task code under the wrong phase is still a mismatch (#4.1).
        detail = (f"submitted {submitted_task} does not match recommended {task}" if submitted_task and submitted_task != task
                  else f"submitted phase {submitted_phase} does not match recommended phase {phase} for {task}")
        flags.append({
            "flag": "submitted_code_mismatch",
            "detail": detail,
            "severity": "needs_review" if confidence >= CODE_MISMATCH_REVIEW_CONFIDENCE else "hold_for_review",
            "source": CODE_MAP_ENGINE,
            "confidence": confidence,
            "citations": [citation, "client-billing-guidelines.md #4.1", "client-billing-guidelines.md #4.2"],
        })
    return {
        "recommended_phase_code": phase,
        "recommended_task_code": task,
        "recommended_label": label,
        "submitted_phase_code": submitted_phase,
        "submitted_task_code": submitted_task,
        "basis": basis,
        "flags": flags,
        "confidence": confidence,
        "source": CODE_MAP_ENGINE,
        "citations": [citation],
    }


# --- Billing guidelines (client-billing-guidelines.md) -------------------------------------

MIN_NARRATIVE_WORDS = 12  # client-billing-guidelines.md #1.1
BLOCK_BILLING_HOURS = 2.0  # client-billing-guidelines.md #2.1 / #2.2
BLOCK_BILLING_CLASS_LIMIT = 1  # client-billing-guidelines.md #2.1
RELATED_CLASS_LIMIT = 2  # client-billing-guidelines.md #2.2
PROHIBITED_TERMS = ("attention to", "various matters", "miscellaneous", "work on file", "general follow up")  # #3.1
VAGUE_PHRASES = ("review and revise", "work on", "handle", "follow up", "touch base")  # #3.2
NON_BILLABLE_CLASSES = ("internal_admin", "billing_hygiene")  # client-billing-guidelines.md #5.1
NON_BILLABLE_TASK_CODES = ("NB900", "BH910")  # task-phase-codes.md #4.1 / #4.2
ROUNDING_INCREMENT = Decimal("0.1")  # client-billing-guidelines.md #6.1
EVIDENCE_OVERRUN_HOURS = 0.2  # client-billing-guidelines.md #6.2
NEAR_DUPLICATE_RATIO = 0.92  # client-billing-guidelines.md #7.1
MISSING_TIME_MIN_HOURS = 0.5  # client-billing-guidelines.md #8.1
CONFIDENCE_FLOOR = 0.75  # client-billing-guidelines.md #9.1
SUBJECT_COVERAGE = 0.5  # share of a subject's content words the narrative must contain
SEVERITY_ORDER = {"compliant": 0, "needs_review": 1, "hold_for_review": 2, "reject": 3}

STOPWORDS = {"a", "an", "and", "the", "of", "for", "to", "with", "on", "in", "at", "by", "from", "or", "re", "via"}
# #1.2 "actor's work": the narrative must lead with the timekeeper's own work verb.
ACTION_VERBS = {
    "advised", "analyzed", "analysed", "assessed", "attended", "briefed", "called", "compiled", "conferred",
    "confirmed", "coordinated", "corresponded", "designed", "developed", "discussed", "documented", "drafted",
    "edited", "evaluated", "facilitated", "finalized", "identified", "interviewed", "led", "mapped", "met",
    "modeled", "negotiated", "planned", "prepared", "presented", "reconciled", "researched", "revised",
    "reviewed", "scoped", "summarized", "tested", "updated", "validated", "wrote",
}
# #1.2 "client-facing purpose": an explicit purpose clause.
PURPOSE_VERBS = (
    "address", "advise", "agree", "align", "answer", "assess", "brief", "capture", "clarify", "confirm",
    "decide", "define", "design", "determine", "discuss", "document", "evaluate", "finalize", "identify",
    "inform", "map", "plan", "prepare", "present", "prioritize", "resolve", "respond", "scope", "summarize",
    "support", "test", "update", "validate",
)
PURPOSE_RE = re.compile(r"\b(?:to|so that we can|in order to)\s+(?:" + "|".join(PURPOSE_VERBS) + r")\b")
EMBEDDED_DEFAULT = ("narrative or linked activity text addresses the reviewer/engine, steers the verdict, "
                    "suppresses or overrides the review, claims an approval or waiver, asks for forwarding, mixes "
                    "scripts in one word, or carries an e-mail address or URL")


def normalize(text):
    text = "".join(ch for ch in (text or "") if unicodedata.category(ch) != "Cf")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def tokens(text):
    return normalize(text).split()


def content_tokens(text):
    return {t for t in tokens(text) if t not in STOPWORDS}


def word_count(text):
    return len([w for w in re.split(r"\s+", (text or "").strip()) if w])


def rounded_to_increment(value):
    try:
        return (Decimal(str(value)) % ROUNDING_INCREMENT) == 0
    except InvalidOperation:
        return False


def similarity(a, b):
    """Max of character-sequence ratio and token Jaccard on normalized text."""
    ratio = SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()), set(b.split())
    jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return round(max(ratio, jaccard), 3)


def add_flag(flags, flag, severity, detail, citations, confidence=0.95):
    flags.append({
        "flag": flag,
        "severity": severity,
        "detail": detail,
        "source": GUIDELINE_ENGINE,
        "confidence": confidence,
        "citations": citations,
    })


def required_elements(entry, narrative, linked):
    """#1.2 checks on the narrative text itself. Returns {element: bool}.

    The subject is credited only against the entry's own linked signals; with nothing linked the
    subject cannot be evidenced (no fall-back to every signal in the packet).
    """
    toks = tokens(narrative)
    narrative_tokens = set(toks)
    first = toks[0] if toks else ""
    actor = bool(entry.get("person")) and first in ACTION_VERBS
    subject = False
    for signal in linked:
        for text in (signal.get("subject"), signal.get("deliverable")):
            wanted = content_tokens(text)
            if wanted and len(wanted & narrative_tokens) / len(wanted) >= SUBJECT_COVERAGE:
                subject = True
    purpose = bool(PURPOSE_RE.search(normalize(narrative)))
    return {"actor": actor, "subject": subject, "purpose": purpose}


def withhold_draft(draft, hits):
    """#11.2: replace a flagged draft narrative with the neutral marker; the entry is held separately."""
    draft["narrative"] = signal_policy.WITHHELD_TEXT
    draft["status"] = "needs_review_embedded_instruction"
    draft["needs_review"] = True
    draft["word_count"] = 0
    draft["review_reasons"] = list(draft.get("review_reasons") or []) + [
        signal_policy.hold_reason(hits, "draft narrative flagged as embedded_instruction by guideline_check")
        + "; withheld from the governed output and never followed (client-billing-guidelines.md #11.1, #11.2)"]
    draft["citations"] = sorted(set(list(draft.get("citations") or [])
                                    + [signal_policy.INJECTION_CITATION, signal_policy.WITHHOLD_CITATION]))


def withhold_texts(item):
    """#11.2 for review reasons and citations. When the reasons trip, each reason that trips is replaced by the
    withheld marker (every reason when only their join trips); citations keep only safe ones, and only plain
    source-row or reference citations when the reasons and citations trip together."""
    reasons = [r for r in item.get("review_reasons") or [] if isinstance(r, str)]
    if reasons and signal_policy.embedded_instruction(signal_policy.draft_records({"review_reasons": reasons})[0]):
        single = [signal_policy.embedded_instruction(r) for r in reasons]
        if not any(single):
            single = [True] * len(reasons)
        item["review_reasons"] = [signal_policy.WITHHELD_TEXT if bad else r for r, bad in zip(reasons, single)]
    flagged = signal_policy.embedded_instruction(signal_policy.draft_records(
        {"review_reasons": reasons, "citations": item.get("citations")})[0])
    item["citations"] = signal_policy.safe_citations(item.get("citations") or [], flagged)[0]


def missing_time_item(activity):
    """One #8.1 missing-time item; flagged text is withheld (#11.2)."""
    hits = signal_policy.screen(signal_policy.signal_texts(activity))
    flagged = activity.get("embedded_instruction") is True or bool(hits)
    citations, _ = signal_policy.safe_citations(activity.get("citations", []), flagged)
    item = {
        "activity_id": activity["activity_id"],
        "person": activity.get("person"),
        "date": activity.get("date"),
        "activity_class": signal_policy.redact(activity.get("activity_class")),
        "duration_hours": activity.get("duration_hours"),
        "subject": signal_policy.WITHHELD_TEXT if flagged else activity.get("subject"),
        "finding": "engagement activity has no matching time entry",
        "source": GUIDELINE_ENGINE,
        "confidence": activity.get("confidence", 0.9),
        "citations": [c for c in citations
                      if c not in (signal_policy.POLICY_CITATION, signal_policy.INJECTION_CITATION)]
        + ["client-billing-guidelines.md #8.1"],
    }
    if flagged:
        item["embedded_instruction"] = True
        item["finding"] += "; " + signal_policy.hold_reason(hits, "activity text flagged as embedded_instruction") + "; withheld"
        item["citations"] += [signal_policy.INJECTION_CITATION, signal_policy.WITHHOLD_CITATION]
    return item


def govern(out):
    """Apply the guideline rules to a coded packet in place (after scope and signal policy are enforced).

    Sets every entry's compliance, and the packet's missing_time_report, exception_list and
    prebill_summary. Returns the number of entries whose supplied code mapping was rejected.
    """
    signals = out["activity_signals"]
    by_id = {a["activity_id"]: a for a in signals}
    used_activity_ids = set()
    meeting_seen = {}
    exception_list = []
    rejected_mappings = 0

    for entry in out["time_entries"]:
        draft = entry.get("draft") or {}
        linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
        draft_text = draft.get("narrative").strip() if isinstance(draft.get("narrative"), str) else ""
        draft_hits = []
        if draft_text and draft_text != signal_policy.WITHHELD_TEXT:
            # The main draft alone, and with the entry's notes and linked activity text (split instructions).
            draft_hits = signal_policy.screen(draft_text, signal_policy.entry_texts(
                {"narrative": draft_text, "notes": entry.get("notes")}, linked))
        # #11.2: a withheld draft (flagged now, or already the marker) is never checked as text. Every rule runs
        # on the entry's own narrative instead, so exception_report's re-run reproduces every flag (#13.2).
        draft_withheld = draft_text == signal_policy.WITHHELD_TEXT or bool(draft_hits)
        narrative = ((None if draft_withheld else draft.get("narrative")) or entry.get("narrative") or "").strip()
        narrative_norm = normalize(narrative)
        used_activity_ids.update(a["activity_id"] for a in linked)
        classes = sorted({a.get("activity_class") for a in linked if a.get("activity_class")})
        duration = entry["duration_hours"]
        same_day = [a for a in linked if a.get("date") == entry.get("date")]
        off_date = [a for a in linked if a.get("date") != entry.get("date")]
        evidence_hours = round(sum(a.get("duration_hours", 0) for a in same_day), 2)
        all_date_hours = round(sum(a.get("duration_hours", 0) for a in linked), 2)
        # #13.1: the code mapping is recomputed from the rules (before any draft text is withheld, as
        # code_map.py saw it); a supplied mapping that disagrees is discarded and the entry is held.
        mapping = code_mapping(dict(entry, draft=dict(draft, narrative="")) if draft_withheld else entry, linked)
        mapping_rejected = entry.get("code_mapping") != mapping
        flags = []

        excluded_links = entry.get("excluded_activity_ids") or []
        if excluded_links:
            add_flag(flags, "disabled_source_signal", "hold_for_review",
                     f"linked signal(s) from a disabled or unresolvable source were excluded and not counted as evidence: "
                     f"{signal_policy.describe_excluded(excluded_links, out)}", [signal_policy.POLICY_CITATION], 0.99)

        wc = word_count(narrative)
        if wc < MIN_NARRATIVE_WORDS:
            add_flag(flags, "minimum_detail", "reject", f"{wc} words < {MIN_NARRATIVE_WORDS} required words",
                     ["client-billing-guidelines.md #1.1"], 0.9)

        elements = required_elements(entry, narrative, linked)
        missing = [k for k in ("actor", "subject", "purpose") if not elements[k]]
        if len(missing) >= 2:
            add_flag(flags, "required_elements_missing", "reject", f"missing required elements: {', '.join(missing)}",
                     ["client-billing-guidelines.md #1.2"], 0.88)
        elif missing:
            add_flag(flags, "required_elements_missing", "needs_review", f"missing required element: {missing[0]}",
                     ["client-billing-guidelines.md #1.2"], 0.88)

        if duration > BLOCK_BILLING_HOURS and len(classes) > BLOCK_BILLING_CLASS_LIMIT:
            add_flag(flags, "block_billing", "reject",
                     f"{duration} hours combines {len(classes)} activity classes: {', '.join(classes)}",
                     ["client-billing-guidelines.md #2.1"], 0.97)
        elif duration <= BLOCK_BILLING_HOURS and len(classes) > RELATED_CLASS_LIMIT:
            add_flag(flags, "block_billing", "reject",
                     f"{duration} hours combines {len(classes)} activity classes (at most {RELATED_CLASS_LIMIT} at <= "
                     f"{BLOCK_BILLING_HOURS} hours): {', '.join(classes)}", ["client-billing-guidelines.md #2.2"], 0.95)
        elif (duration <= BLOCK_BILLING_HOURS and len(classes) == RELATED_CLASS_LIMIT
              and not (elements["subject"] and elements["purpose"])):
            add_flag(flags, "block_billing", "needs_review",
                     f"{duration} hours combines {', '.join(classes)} without an explicit subject and purpose",
                     ["client-billing-guidelines.md #2.2"], 0.9)

        for term in PROHIBITED_TERMS:
            if term in narrative_norm:
                add_flag(flags, "prohibited_term", "reject", f"matched prohibited term '{term}'",
                         ["client-billing-guidelines.md #3.1", "client-billing-guidelines.md #3.3"], 0.99)
        cured = elements["subject"] and elements["purpose"]
        for phrase in VAGUE_PHRASES:
            if re.search(r"\b" + re.escape(phrase) + r"\b", narrative_norm):
                if cured:
                    add_flag(flags, "vague_phrase", "needs_review",
                             f"matched vague phrase '{phrase}' (cured by an explicit subject and purpose)",
                             ["client-billing-guidelines.md #3.2", "client-billing-guidelines.md #3.3"], 0.93)
                else:
                    add_flag(flags, "vague_phrase", "reject",
                             f"matched vague phrase '{phrase}' with no specific subject and purpose to cure it",
                             ["client-billing-guidelines.md #3.2", "client-billing-guidelines.md #3.3"], 0.93)

        rewrites = [r for r in draft.get("suggested_rewrites") or [] if isinstance(r, dict)]
        # The draft's review reasons, citations and every rewrite are free text too (#11.1).
        records = signal_policy.draft_records(draft)
        record_hits = [signal_policy.screen(r) for r in records]
        # Any upstream marker or any field (or field aggregate) that trips holds the entry; never compliant.
        hits = signal_policy.screen(narrative, signal_policy.entry_texts(entry, linked),
                                    *[signal_policy.signal_texts(a) for a in linked]) + draft_hits
        hits += [h for found in record_hits for h in found]
        reasons = list(draft.get("review_reasons") or []) + [x for r in rewrites for x in r.get("review_reasons") or []]
        marked = (draft_withheld or entry.get("embedded_instruction") is True
                  or any(a.get("embedded_instruction") is True for a in linked)
                  or any(r.get("status") == "withheld_embedded_instruction" for r in rewrites)
                  or signal_policy.WITHHELD_TEXT in reasons)
        if marked or hits:
            add_flag(flags, "embedded_instruction", "hold_for_review",
                     signal_policy.hold_reason(hits, EMBEDDED_DEFAULT) + "; treated as data and not followed",
                     [signal_policy.INJECTION_CITATION], 0.95)
        if record_hits and record_hits[0]:
            withhold_texts(draft)
        if draft_hits:
            withhold_draft(draft, draft_hits)
        for rewrite, found in zip(rewrites, record_hits[1:]):
            if found:
                rewrite["narrative"] = signal_policy.WITHHELD_TEXT
                rewrite["status"] = "withheld_embedded_instruction"
                withhold_texts(rewrite)
                rewrite["citations"] = sorted(set(rewrite.get("citations", []) + [signal_policy.WITHHOLD_CITATION]))

        if mapping_rejected:
            rejected_mappings += 1
            add_flag(flags, "code_mapping_mismatch", "hold_for_review",
                     f"the supplied code_mapping does not match the code-map rules for this entry and its linked "
                     f"activity; it was discarded and the recomputed mapping ({mapping['recommended_task_code']}, "
                     f"{mapping['basis']}) and its flags are used", [MAPPING_CITATION, "client-billing-guidelines.md #4.1"],
                     0.99)
            entry["code_mapping"] = dict(mapping, supplied_mapping_rejected=True)
        task_code = mapping["recommended_task_code"]
        if any(c in NON_BILLABLE_CLASSES for c in classes) or task_code in NON_BILLABLE_TASK_CODES:
            add_flag(flags, "non_billable_activity", "reject", "entry is linked to internal/non-billable activity",
                     ["client-billing-guidelines.md #5.1", "task-phase-codes.md #4.1"], 0.96)

        if not rounded_to_increment(duration):
            add_flag(flags, "rounding_increment", "needs_review", f"{duration} is not rounded to 0.1 hour",
                     ["client-billing-guidelines.md #6.1"], 0.91)
        if off_date:
            add_flag(flags, "date_mismatch", "needs_review",
                     f"entry dated {entry.get('date')} links activity from another date: "
                     + ", ".join(f"{a['activity_id']} ({a.get('date')})" for a in off_date),
                     ["client-billing-guidelines.md #6.2"], 0.85)
        if not linked and duration > EVIDENCE_OVERRUN_HOURS:
            add_flag(flags, "no_linked_evidence", "hold_for_review",
                     f"{duration} billed hours has no linked activity evidence (0 hours); the #6.2 tolerance is "
                     f"{EVIDENCE_OVERRUN_HOURS} hours", ["client-billing-guidelines.md #6.2"], 0.9)
        elif linked and duration - evidence_hours > EVIDENCE_OVERRUN_HOURS:
            add_flag(flags, "evidence_overrun", "needs_review",
                     f"{duration} billed hours exceeds {evidence_hours} hours of same-date linked evidence "
                     f"({all_date_hours} hours across all linked dates) by more than {EVIDENCE_OVERRUN_HOURS}",
                     ["client-billing-guidelines.md #6.2"], 0.86)

        for map_flag in mapping["flags"]:
            flags.append(map_flag)

        meeting_ids = sorted({a.get("meeting_id") for a in linked if a.get("meeting_id")})
        for meeting_id in meeting_ids:
            prior = meeting_seen.setdefault(meeting_id, [])
            best = None
            for prior_id, prior_text in prior:
                score = similarity(prior_text, narrative_norm)
                if score >= NEAR_DUPLICATE_RATIO and (best is None or score > best[1]):
                    best = (prior_id, score)
            if best:
                add_flag(flags, "duplicate_meeting", "reject",
                         f"near-duplicate meeting narrative for {meeting_id}: similarity {best[1]} >= "
                         f"{NEAR_DUPLICATE_RATIO} with {best[0]}", ["client-billing-guidelines.md #7.1"], 0.92)
            prior.append((entry["entry_id"], narrative_norm))

        lowest_conf = min([f.get("confidence", 1.0) for f in flags]
                          + [draft.get("confidence", 1.0), mapping["confidence"]])
        if lowest_conf < CONFIDENCE_FLOOR:
            add_flag(flags, "confidence_floor", "hold_for_review", f"confidence {lowest_conf} below {CONFIDENCE_FLOOR}",
                     ["client-billing-guidelines.md #9.1"], lowest_conf)

        verdict = "compliant"
        for flag in flags:
            sev = flag.get("severity")
            # An unrecognised severity fails closed to hold_for_review, never to needs_review.
            if SEVERITY_ORDER.get(sev, SEVERITY_ORDER["hold_for_review"]) > SEVERITY_ORDER[verdict]:
                verdict = sev
        entry["compliance"] = {
            "verdict": verdict,
            "flags": flags,
            "required_elements": elements,
            "evidence_hours_same_date": evidence_hours,
            "confidence": round(lowest_conf if flags else 0.96, 2),
            "source": GUIDELINE_ENGINE,
            "citations": sorted({c for f in flags for c in f.get("citations", [])})
            or ["client-billing-guidelines.md #1.1", "client-billing-guidelines.md #1.2"],
        }
        if flags:
            item = {
                "entry_id": entry["entry_id"],
                "person": entry.get("person"),
                "date": entry.get("date"),
                "duration_hours": duration,
                "verdict": entry["compliance"]["verdict"],
                "flags": [f["flag"] for f in flags],
                "recommended_action": ("rewrite_or_remove_before_prebill" if verdict == "reject"
                                       else "billing_coordinator_review"),
                "source": GUIDELINE_ENGINE,
                "confidence": entry["compliance"]["confidence"],
                "citations": entry["compliance"]["citations"],
            }
            if excluded_links:
                item["excluded_activity_ids"] = list(excluded_links)
            exception_list.append(item)

    missing_time = [missing_time_item(a) for a in signals
                    if a["activity_id"] not in used_activity_ids
                    and a.get("billable_signal") and a.get("duration_hours", 0) >= MISSING_TIME_MIN_HOURS]
    if missing_time:
        exception_list.append({
            "entry_id": None,
            "person": "multiple" if len({m["person"] for m in missing_time}) > 1 else missing_time[0]["person"],
            "date": "multiple" if len({m["date"] for m in missing_time}) > 1 else missing_time[0]["date"],
            "duration_hours": round(sum(m["duration_hours"] for m in missing_time), 2),
            "verdict": "missing_time",
            "flags": ["missing_time"] + (["embedded_instruction"] if any(m.get("embedded_instruction")
                                                                         for m in missing_time) else []),
            "recommended_action": "review_activity_and_create_draft_entries_if_billable",
            "source": GUIDELINE_ENGINE,
            "confidence": min(m["confidence"] for m in missing_time),
            "citations": sorted({c for m in missing_time for c in m["citations"]}),
        })

    out["missing_time_report"] = missing_time
    out["exception_list"] = exception_list
    excluded = out.get("provenance", {}).get("excluded_signals", [])
    out["prebill_summary"] = {
        "period": out.get("period"),
        **summary_figures(out["time_entries"], missing_time),
        "exception_count": len(exception_list),
        "excluded_signal_ids": [e.get("activity_id") for e in excluded],
        "source": GUIDELINE_ENGINE,
        "confidence": 0.96,
        "citations": ["client-billing-guidelines.md #2.1", "client-billing-guidelines.md #3.1",
                      "client-billing-guidelines.md #8.1", "client-billing-guidelines.md #9.2",
                      "client-billing-guidelines.md #10.1"],
    }
    return rejected_mappings


def summary_figures(entries, missing_time):
    """The prebill_summary figures derived from the line items (#13.2)."""
    counts = {}
    for entry in entries:
        verdict = entry.get("compliance", {}).get("verdict", "unknown")
        counts[verdict] = counts.get(verdict, 0) + 1
    return {
        "total_entries": len(entries),
        "total_hours": round(sum(e.get("duration_hours", 0) for e in entries), 2),
        "verdict_counts": dict(sorted(counts.items())),
        "missing_time_hours": round(sum(m["duration_hours"] for m in missing_time), 2),
    }


def _flag_keys(flags):
    return {(f.get("flag"), f.get("severity")) for f in flags or [] if isinstance(f, dict)}


def excluded_ids(packet):
    """The excluded signal IDs, derived from provenance.excluded_signals (#10.1)."""
    return [e.get("activity_id") for e in (packet.get("provenance") or {}).get("excluded_signals", [])]


NOT_REDERIVED = "recorded by guideline_check but not raised by a re-run of the rules on this governed data"


def rendered_flags(recorded, rederived):
    """The flags exception_report prints for one entry (#13.2): the re-run's flags with their re-derived detail
    and citations. A recorded flag the re-run does not raise (a stricter earlier run) keeps its name and
    severity with a neutral detail. Supplied detail and citation text is never printed."""
    out = [{"flag": f["flag"], "severity": f["severity"], "detail": f.get("detail", ""),
            "citations": list(f.get("citations", []))} for f in rederived]
    derived = _flag_keys(rederived)
    for flag in recorded or []:
        if isinstance(flag, dict) and (flag.get("flag"), flag.get("severity")) not in derived:
            out.append({"flag": flag.get("flag"), "severity": flag.get("severity"), "detail": NOT_REDERIVED,
                        "citations": [RECONCILE_CITATION]})
    return out


def reconcile_governed(packet, script_dir=None, engine="engine:unknown"):
    """Re-run govern() on a copy of governed data; return (problems, rerun). No problems = consistent (#13.2).

    - Entries: the recorded verdict may never be less severe than the re-run's, and every re-run
      (flag, severity) must be recorded. Extra recorded flags are allowed (a stricter earlier run). An entry
      whose draft was withheld (#11.2) is re-checked on its own narrative like any other, with the
      embedded_instruction hold merged in: a reject stays a reject.
    - Missing time: the recorded items must equal the re-run's exactly.
    - Summary: totals, hours, verdict counts, missing-time hours, the exception count, the period and the
      excluded signal IDs must match the line items, the packet period and provenance.excluded_signals.
    - Exclusions: provenance.excluded_signals must cover every entry's excluded links, list no signal still
      present, be unchanged when the signal policy is re-applied, and carry only the engines' own reason and
      citation wording (signal_policy.exclusion_texts); provenance.excluded_entries only the #13.3 citation.
    Messages name fields, positions, verdicts and the re-run's flag names only; never supplied text.
    """
    rerun = deepcopy(packet)
    signal_policy.filter_packet(rerun, script_dir=script_dir, engine=engine)
    govern(rerun)
    problems = []
    rank = SEVERITY_ORDER
    supplied = packet["time_entries"]
    if len(supplied) != len(rerun["time_entries"]):
        problems.append("time_entries: the entry count changed on re-run")
    for i, (got, want) in enumerate(zip(supplied, rerun["time_entries"])):
        where = f"time_entries[{i}]"
        recorded = got["compliance"]
        have = _flag_keys(recorded.get("flags"))
        need = _flag_keys(want["compliance"]["flags"])
        floor = want["compliance"]["verdict"]
        if (got.get("draft") or {}).get("narrative") == signal_policy.WITHHELD_TEXT:
            need.add(("embedded_instruction", "hold_for_review"))
            floor = max(floor, "hold_for_review", key=rank.__getitem__)
        absent = sorted({f for f, _ in need - have})
        if rank[recorded["verdict"]] < rank[floor] or absent:
            problems.append(f"{where}: recorded verdict {recorded['verdict']}, the rules give {floor}"
                            + (f" (flags not recorded: {', '.join(absent)})" if absent else ""))
    if packet["missing_time_report"] != rerun["missing_time_report"]:
        problems.append(f"missing_time_report: {len(packet['missing_time_report'])} recorded item(s) do not match "
                        f"the {len(rerun['missing_time_report'])} item(s) the rules give")
    summary = packet["prebill_summary"]
    for key, value in summary_figures(supplied, packet["missing_time_report"]).items():
        if summary.get(key) != value:
            problems.append(f"prebill_summary.{key} does not match the line items")
    derived_exceptions = sum(1 for e in supplied if e["compliance"].get("flags")) + bool(packet["missing_time_report"])
    if "exception_count" in summary and summary["exception_count"] != derived_exceptions:
        problems.append("prebill_summary.exception_count does not match the line items")
    if len(packet["exception_list"]) != derived_exceptions:
        problems.append("exception_list does not match the line items")
    if "period" in summary and summary["period"] != packet.get("period"):
        problems.append("prebill_summary.period does not match the packet period")
    ids = excluded_ids(packet)
    if "excluded_signal_ids" in summary and summary["excluded_signal_ids"] != ids:
        problems.append("prebill_summary.excluded_signal_ids does not match provenance.excluded_signals")
    if excluded_ids(rerun) != ids:
        problems.append("activity_signals hold signal(s) the signal policy excludes, or provenance.excluded_signals "
                        "is incomplete")
    present = {a.get("activity_id") for a in packet["activity_signals"]}
    if present & set(ids):
        problems.append("provenance.excluded_signals lists signal(s) still present in activity_signals")
    for i, entry in enumerate(supplied):
        if set(entry.get("excluded_activity_ids") or []) - set(ids):
            problems.append(f"time_entries[{i}].excluded_activity_ids are not recorded in provenance.excluded_signals")
    # Exclusion reasons and citations are printed only when they are the engines' own wording (#13.2).
    provenance = packet.get("provenance") or {}
    for i, record in enumerate(provenance.get("excluded_signals", [])):
        if (record.get("reason"), record.get("citations")) not in signal_policy.exclusion_texts(record, packet):
            problems.append(f"provenance.excluded_signals[{i}] reason or citations are not the signal policy's wording")
    for i, record in enumerate(provenance.get("excluded_entries", [])):
        if record.get("citations") != [signal_policy.ENGAGEMENT_CITATION]:
            problems.append(f"provenance.excluded_entries[{i}] citations are not the engagement-identity rule's")
    return problems, rerun
