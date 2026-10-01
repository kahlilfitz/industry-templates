#!/usr/bin/env python3
"""guideline_check - deterministic billing-guideline compliance engine (Govern, step 4 of 5).

Constants mirror references/client-billing-guidelines.md section by section. The model
reports these flags; it never decides, suppresses or downgrades compliance verdicts.

v1.0.4 rules:
- Signals from disabled or unknown sources are dropped first (signal_policy.py, #10.1); an
  entry that linked one gets a hold_for_review flag and the signal never counts as evidence.
- Rows outside the recorded timekeeper scope are withheld before any check (#12.1).
- #1.1 under 12 words = reject. #1.2 actor's work / subject / purpose are checked on the
  narrative text itself for every entry (1 missing = needs_review, 2+ = reject).
- #2.1 >2.0 h with more than one class = reject; #2.2 <=2.0 h may combine at most two classes,
  and only with an explicit subject and purpose.
- #3.2 a vague phrase is reject unless the narrative states a specific subject AND purpose.
- #1.2 the subject is credited only against the entry's own linked signals (no fall-back to
  every packet signal).
- #6.2 evidence counts only linked activity on the entry's own date; off-date links are flagged.
  An entry over 0.2 h with NO linked evidence gets a no_linked_evidence hold (never compliant).
- #11.1 embedded_instruction hold (shared tripwire in signal_policy.py): reviewer/AI-addressed
  notes, approval/waiver/sign-off claims and paraphrased steering, forward/send instructions, or
  any e-mail address or URL in narrative, note, suggested-rewrite or linked signal text (NFKC,
  Unicode Cf stripped, Cyrillic/Greek look-alikes folded first).
- #11.2 flagged text is withheld: a flagged suggested rewrite or missing-time subject is replaced
  by a withheld marker before output.
- #7.1 near-duplicate = SequenceMatcher ratio or token Jaccard >= 0.92 against earlier
  narratives for the same meeting.
"""
import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signal_policy  # noqa: E402  (shared copy shipped next to each engine)

ENGINE = "engine:guideline_check"
ENGINE_VERSION = "guideline_check/1.0.4"
CONTRACT = "ps.time-expense-narrative-compliance.v1"
MIN_NARRATIVE_WORDS = 12  # client-billing-guidelines.md #1.1
BLOCK_BILLING_HOURS = 2.0  # client-billing-guidelines.md #2.1 / #2.2
BLOCK_BILLING_CLASS_LIMIT = 1  # client-billing-guidelines.md #2.1
RELATED_CLASS_LIMIT = 2  # client-billing-guidelines.md #2.2
PROHIBITED_TERMS = ("attention to", "various matters", "miscellaneous", "work on file", "general follow up")  # #3.1
VAGUE_PHRASES = ("review and revise", "work on", "handle", "follow up", "touch base")  # #3.2
CODE_MISMATCH_REVIEW_CONFIDENCE = 0.80  # client-billing-guidelines.md #4.2
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
# Narrative fields are data. The tripwire is shared by every engine (signal_policy.py, #11.1).
embedded_instruction = signal_policy.embedded_instruction


class InputError(ValueError):
    pass


def generated_at(override):
    if override:
        try:
            datetime.datetime.fromisoformat(override.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InputError(f"--generated-at is not an ISO-8601 timestamp: {override!r}") from exc
        return override
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_packet(path):
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read {os.path.basename(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise InputError("input is not a JSON object")
    if payload.get("contract_version") != CONTRACT:
        raise InputError(f"expected contract {CONTRACT}, got {payload.get('contract_version')!r}")
    signal_policy.validate_packet(payload, "coded")
    return payload


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
        "source": ENGINE,
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


def main():
    ap = argparse.ArgumentParser(description="Govern time-entry narratives against client billing guidelines.")
    ap.add_argument("--coded", required=True, help="Input coded contract JSON")
    ap.add_argument("--out", required=True, help="Output governed contract JSON")
    ap.add_argument("--signal-config", help="Additional signal policy JSON; it can only narrow the plugin's config/signal-sources.json, which is always applied (most restrictive wins)")
    ap.add_argument("--generated-at", help="Fixed ISO-8601 UTC timestamp for reproducible golden files")
    args = ap.parse_args()

    try:
        stamp = generated_at(args.generated_at)
        out = deepcopy(load_packet(args.coded))
        signal_policy.enforce_timekeeper_scope(out, engine=ENGINE)
        signal_policy.filter_packet(out, config_path=args.signal_config,
                                    script_dir=os.path.dirname(os.path.abspath(__file__)), engine=ENGINE)
    except (InputError, signal_policy.PolicyError) as exc:
        sys.exit(f"guideline_check: {exc}")

    signals = out["activity_signals"]
    by_id = {a["activity_id"]: a for a in signals}
    used_activity_ids = set()
    meeting_seen = {}
    exception_list = []

    for entry in out["time_entries"]:
        narrative = (entry.get("draft", {}).get("narrative") or entry.get("narrative") or "").strip()
        narrative_norm = normalize(narrative)
        linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
        used_activity_ids.update(a["activity_id"] for a in linked)
        classes = sorted({a.get("activity_class") for a in linked if a.get("activity_class")})
        duration = entry["duration_hours"]
        same_day = [a for a in linked if a.get("date") == entry.get("date")]
        off_date = [a for a in linked if a.get("date") != entry.get("date")]
        evidence_hours = round(sum(a.get("duration_hours", 0) for a in same_day), 2)
        all_date_hours = round(sum(a.get("duration_hours", 0) for a in linked), 2)
        flags = []

        excluded_links = entry.get("excluded_activity_ids") or []
        if excluded_links:
            add_flag(flags, "disabled_source_signal", "hold_for_review",
                     f"linked signal(s) from a disabled or unresolvable source were excluded and not counted as evidence: "
                     f"{', '.join(excluded_links)}", [signal_policy.POLICY_CITATION], 0.99)

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

        draft = entry.get("draft") or {}
        rewrites = [r for r in draft.get("suggested_rewrites") or [] if isinstance(r, dict)]
        rewrite_texts = [r.get("narrative") for r in rewrites]
        # Any upstream marker or any field (or field aggregate) that trips holds the entry; never compliant.
        injected = (entry.get("embedded_instruction") is True
                    or any(a.get("embedded_instruction") is True for a in linked)
                    or embedded_instruction(narrative, signal_policy.entry_texts(entry, linked), *rewrite_texts,
                                            *[signal_policy.signal_texts(a) for a in linked]))
        if injected:
            add_flag(flags, "embedded_instruction", "hold_for_review",
                     "narrative or linked activity text addresses the reviewer/engine, steers the verdict, claims an "
                     "approval or waiver, asks for forwarding, mixes scripts in one word, or carries an e-mail "
                     "address or URL; treated as data and not followed",
                     [signal_policy.INJECTION_CITATION], 0.95)
        for rewrite in rewrites:
            if embedded_instruction(rewrite.get("narrative")):
                rewrite["narrative"] = signal_policy.WITHHELD_TEXT
                rewrite["status"] = "withheld_embedded_instruction"
                rewrite["citations"] = sorted(set(rewrite.get("citations", []) + [signal_policy.WITHHOLD_CITATION]))

        task_code = entry.get("code_mapping", {}).get("recommended_task_code")
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

        for map_flag in entry.get("code_mapping", {}).get("flags", []):
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
                          + [entry.get("draft", {}).get("confidence", 1.0),
                             entry.get("code_mapping", {}).get("confidence", 1.0)])
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
            "source": ENGINE,
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
                "source": ENGINE,
                "confidence": entry["compliance"]["confidence"],
                "citations": entry["compliance"]["citations"],
            }
            if excluded_links:
                item["excluded_activity_ids"] = list(excluded_links)
            exception_list.append(item)

    missing_time = []
    for activity in signals:
        if activity["activity_id"] in used_activity_ids:
            continue
        if activity.get("billable_signal") and activity.get("duration_hours", 0) >= MISSING_TIME_MIN_HOURS:
            flagged = (activity.get("embedded_instruction") is True
                       or embedded_instruction(signal_policy.signal_texts(activity)))
            item = {
                "activity_id": activity["activity_id"],
                "person": activity.get("person"),
                "date": activity.get("date"),
                "activity_class": signal_policy.redact(activity.get("activity_class")),
                "duration_hours": activity.get("duration_hours"),
                "subject": signal_policy.WITHHELD_TEXT if flagged else activity.get("subject"),
                "finding": "engagement activity has no matching time entry",
                "source": ENGINE,
                "confidence": activity.get("confidence", 0.9),
                "citations": [c for c in activity.get("citations", [])
                              if c not in (signal_policy.POLICY_CITATION, signal_policy.INJECTION_CITATION)]
                + ["client-billing-guidelines.md #8.1"],
            }
            if flagged:
                item["embedded_instruction"] = True
                item["finding"] += "; activity text flagged as embedded_instruction and withheld"
                item["citations"] += [signal_policy.INJECTION_CITATION, signal_policy.WITHHOLD_CITATION]
            missing_time.append(item)
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
            "source": ENGINE,
            "confidence": min(m["confidence"] for m in missing_time),
            "citations": sorted({c for m in missing_time for c in m["citations"]}),
        })

    out["missing_time_report"] = missing_time
    out["exception_list"] = exception_list
    counts = {}
    for entry in out["time_entries"]:
        verdict = entry.get("compliance", {}).get("verdict", "unknown")
        counts[verdict] = counts.get(verdict, 0) + 1
    excluded = out.get("provenance", {}).get("excluded_signals", [])
    out["prebill_summary"] = {
        "period": out.get("period"),
        "total_entries": len(out["time_entries"]),
        "total_hours": round(sum(e.get("duration_hours", 0) for e in out["time_entries"]), 2),
        "verdict_counts": dict(sorted(counts.items())),
        "missing_time_hours": round(sum(m["duration_hours"] for m in missing_time), 2),
        "exception_count": len(exception_list),
        "excluded_signal_ids": [e.get("activity_id") for e in excluded],
        "source": ENGINE,
        "confidence": 0.96,
        "citations": ["client-billing-guidelines.md #2.1", "client-billing-guidelines.md #3.1",
                      "client-billing-guidelines.md #8.1", "client-billing-guidelines.md #9.2",
                      "client-billing-guidelines.md #10.1"],
    }
    out.setdefault("provenance", {}).setdefault("engines", []).append(ENGINE_VERSION)
    out["provenance"]["generated_at"] = stamp
    try:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        sys.exit(f"guideline_check: cannot write output: {exc}")
    print(f"guideline_check: {len(out['time_entries'])} entries, {len(exception_list)} exception(s), "
          f"{len(missing_time)} missing-time item(s), {len(excluded)} excluded signal(s) -> {os.path.basename(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
