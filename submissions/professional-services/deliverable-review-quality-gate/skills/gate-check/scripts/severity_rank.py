#!/usr/bin/env python3
"""severity_rank - deterministic finding ranking and review-status verdict."""
import argparse
import copy
import os
import sys
from datetime import datetime

import assertion_rules as rules
import gate_check as gc

ENGINE = "engine:severity_rank"
ENGINE_VERSION = "1.0.4"
CONTRACT_VERSION = "ps.deliverable-review-quality-gate.v1"
SEVERITY_ORDER = {"release_blocker": 0, "must_fix": 1, "advisory": 2}  # severity-rules.md #1.1-#1.3
CONFIDENCE_FLOOR = 0.72  # severity-rules.md #2.1
BLOCKER_NEVER_DOWNGRADE = True  # severity-rules.md #3.1
STATUS_WITH_BLOCKER = "not_ready_for_release"  # severity-rules.md #3.3
STATUS_WITH_MUST_FIX = "partner_review_required_must_fix"  # severity-rules.md #3.3
STATUS_WITH_ADVISORIES = "partner_review_required_advisories_only"  # severity-rules.md #3.3
STATUS_CLEAN = "partner_review_required_no_engine_findings"  # severity-rules.md #3.3

GATE_IDS = tuple(gc.GATES)
MAX_G8_HITS = gc.MAX_G8_HITS
SR_G8_PREFIX = "SR-G8-embedded-instruction-"

InputError = rules.InputError

def load_json(path):
    return rules.load_json_file(path)

def validate_generated_at(value):
    if value is None:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("--generated-at must be an ISO-8601 timestamp") from exc
    return value

def require_contract(payload):
    if not isinstance(payload, dict):
        raise InputError("input must be a JSON object")
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise InputError(f"expected contract {CONTRACT_VERSION}, got {rules.describe(payload.get('contract_version'))}")
    # gate_check always emits both arrays; an absent one means the gate run is missing, never "nothing found".
    for key in ("findings", "escalations"):
        if key not in payload:
            raise InputError(f"missing required array: {key} (run gate_check first; an empty run still emits [])")
        if not isinstance(payload[key], list):
            raise InputError(f"{key} must be an array")
    for index, item in enumerate(payload["escalations"]):
        if not (isinstance(item, dict) or (isinstance(item, str) and item.strip())):
            raise InputError(f"escalations[{index}] must be a non-blank string or an object, got {rules.describe(item)}")

def validate_finding(index, item):
    """Fail closed with a clear message on values the ranking cannot order (severity-rules.md #3.2)."""
    if not isinstance(item, dict):
        raise InputError(f"findings[{index}] must be an object")
    label = f"findings[{index}]"
    if not isinstance(item.get("finding_id"), str) or not item["finding_id"].strip():
        raise InputError(f"findings[{index}] missing required field: finding_id")
    if item.get("severity") not in SEVERITY_ORDER:
        raise InputError(f"{label}: unknown severity ({rules.describe(item.get('severity'))}); severity must be one of {', '.join(SEVERITY_ORDER)}")
    if "confidence" in item and not rules.is_number(item["confidence"]):
        raise InputError(f"{label}: confidence must be a number, got {rules.describe(item['confidence'])}")
    location = item.get("location")
    if location is None:
        return
    if not isinstance(location, dict):
        raise InputError(f"{label}: location must be an object")
    for key in ("page", "paragraph"):
        value = location.get(key)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise InputError(f"{label}: location.{key} must be an integer or null, got {rules.describe(value)}; record the physical "
                             f"page number and keep printed labels such as roman numerals in location.label")

def sort_key(item):
    # Findings without a page or paragraph (register- or field-level) rank after page-located findings
    # of the same severity and confidence.
    location = item.get("location") or {}
    page, paragraph = location.get("page"), location.get("paragraph")
    return (SEVERITY_ORDER[item["severity"]], -float(item.get("confidence", 0.0)), 9999 if page is None else page, 9999 if paragraph is None else paragraph, item.get("finding_id", ""))

def collapse_duplicates(findings):
    """Keep one finding per finding_id at the highest severity (first occurrence on a tie), so a duplicate is never
    counted twice and can never lower severity (severity-rules.md #3.1). Returns (kept, {finding_id: copies})."""
    kept, positions, copies = [], {}, {}
    for item in findings:
        finding_id = item["finding_id"]
        if finding_id not in positions:
            positions[finding_id] = len(kept)
            kept.append(item)
            continue
        copies[finding_id] = copies.get(finding_id, 1) + 1
        current = kept[positions[finding_id]]
        if SEVERITY_ORDER[item["severity"]] < SEVERITY_ORDER[current["severity"]]:
            kept[positions[finding_id]] = item
    return kept, copies

def gate_status(highest):
    return "no_engine_findings" if highest == "none" else "blocked" if highest == "release_blocker" else "attention_required"

def gate_summary(findings, gate_id):
    """(status, highest_severity, finding_count) for one gate, computed exactly as gate_check computes it."""
    severities = [item["severity"] for item in findings if item["gate_id"] == gate_id]
    highest = min(severities, key=SEVERITY_ORDER.get) if severities else "none"
    return gate_status(highest), highest, len(severities)

def reconcile_gate_results(findings, gate_results):
    """Refuse input whose gate_results disagree with findings[] (severity-rules.md #3.5): one entry per gate G1-G8,
    and each entry's status, highest_severity and finding_count must equal what the findings give. A gate reported
    blocked can therefore never reach a lower verdict because its findings were removed or downgraded."""
    seen = [item["gate_id"] for item in gate_results]
    if sorted(seen) != sorted(GATE_IDS):
        raise InputError(f"gate_results must contain exactly one entry per gate {', '.join(GATE_IDS)}, got {', '.join(rules.safe_token(gate, '<invalid>') for gate in seen) or 'none'}")
    mismatches = []
    for item in gate_results:
        status, highest, count = gate_summary(findings, item["gate_id"])
        if (item["status"], item["highest_severity"], item["finding_count"]) != (status, highest, count):
            mismatches.append(f"{item['gate_id']} reports {item['status']}/{item['highest_severity']}/{item['finding_count']} but findings[] give {status}/{highest}/{count}")
    if mismatches:
        raise InputError("gate_results do not match findings[] (status/highest_severity/finding_count): " + "; ".join(mismatches) + "; re-run gate_check, findings cannot be removed or downgraded after the gate run")

SEVERITY_RANK = {severity: len(SEVERITY_ORDER) - order for severity, order in SEVERITY_ORDER.items()}


def rederive_gate_findings(payload):
    """Re-run the gate_check engine on the mapped input that gate-checked.json carries and require every
    engine-derived finding to be present with the same gate at no lower severity (severity-rules.md #3.7).

    gate_results[] and findings[] are equally editable, so agreeing with each other proves nothing; the evidence is
    the mapped input itself (the primary sections, top-level fields and assertion_mappings). The AM- findings are
    passed back, collapsed to one per finding_id at the highest severity, because gate_check verifies them against
    assertion_map; everything else gate_check or a reviewer added (GC- findings, other findings, escalations,
    provenance) is left out. Those can only add: extra findings are allowed, and their text is screened afterwards
    (severity-rules.md #3.6). Raises InputError when anything engine-derived is missing or lower."""
    derived_sections = ("findings", "escalations", "provenance", "gate_results", "ranked_findings", "release_readiness")
    mapped = {key: copy.deepcopy(value) for key, value in payload.items() if key not in derived_sections}
    am_findings = [copy.deepcopy(item) for item in payload["findings"] if item["finding_id"].startswith("AM-")]
    mapped["findings"], _ = collapse_duplicates(am_findings)
    mapped["escalations"] = []
    try:
        derived = gc.evaluate(mapped)["findings"]
    except InputError as exc:
        raise InputError(f"gate_check re-derivation failed on the carried mapped input ({exc}); re-run gate_check") from exc
    supplied = {}
    for item in payload["findings"]:
        key = (item["finding_id"], item.get("gate_id"))
        supplied[key] = max(supplied.get(key, 0), SEVERITY_RANK[item["severity"]])
    problems = []
    for item in derived:
        present = supplied.get((item["finding_id"], item["gate_id"]), 0)
        if present < SEVERITY_RANK[item["severity"]]:
            label = gc.safe_token(item["finding_id"], "an engine finding")
            problems.append(f"{label} ({item['gate_id']}, {item['severity']}) is {'missing' if not present else 'downgraded'}")
    if problems:
        shown = "; ".join(problems[:10]) + (f"; and {len(problems) - 10} more" if len(problems) > 10 else "")
        raise InputError(f"findings[] do not contain every finding gate_check derives from the carried mapped input: {shown}. Re-run gate_check; engine findings cannot be removed or downgraded after the gate run (severity-rules.md #3.7)")


def covered_by_gate_check(findings, escalations, path):
    """True when gate_check already holds this primary-field hit under its own G8 finding."""
    if any(item["finding_id"].startswith("GC-G8-embedded-instruction-") and f"Untrusted field {path} " in item.get("detail", "") for item in findings):
        return True
    listed = sum(1 for item in findings if item["finding_id"].startswith("GC-G8-embedded-instruction-"))
    overflow = any(isinstance(entry, str) and entry.startswith("G8: ") and "further embedded-instruction hit(s) not listed individually" in entry for entry in escalations)
    return listed >= MAX_G8_HITS and overflow

def screen_embedded_instructions(payload):
    """Screen every incoming string through steering_guard exactly as gate_check does (severity-rules.md #3.6) and
    withhold every string that trips, everywhere it appears (quality-gate-criteria.md #8.7).

    A primary-field hit gate_check already holds under its own G8 finding is not counted twice. Every string in the
    derived sections (findings, escalations, gate_results, provenance, assertion_mappings and any other notes) that
    trips the detector, and is not a copy of primary text already held, is a new hit. Text already replaced by a
    withheld marker upstream stays withheld. Returns (path, reason) for each new hit; the payload is updated in place."""
    findings, escalations = list(payload["findings"]), list(payload["escalations"])
    hits = [(path, reason) for path, reason, derived in rules.withhold_untrusted(payload) if derived or not covered_by_gate_check(findings, escalations, path)]
    for index, item in enumerate(payload["findings"]):
        if rules.is_withheld(item["finding_id"]):
            item["finding_id"] = f"withheld-finding-{index + 1}"
    return hits

def add_g8_findings(payload, hits):
    """One SR-G8 release blocker per new hit (up to MAX_G8_HITS) plus escalations; withheld text is never repeated."""
    findings, escalations = payload["findings"], payload["escalations"]
    for hit_index, (path, reason) in enumerate(hits[:MAX_G8_HITS], start=1):
        location = gc.location_for_scan_path(payload, path)
        if reason == gc.OVERSIZE:
            title, detail, section = "Field too long to screen for embedded instructions", f"Field {path} reached severity_rank too long to screen for embedded instructions, so it was withheld and must be held for human review.", "quality-gate-criteria.md #8.6"
            escalations.append(f"G8: {path} reached severity_rank too long to screen for embedded instructions - hold for reviewing partner/QRM (severity-rules.md #3.6)")
        else:
            title, detail, section = "Embedded instruction found in gate-check output", f"Field {path} reached severity_rank with instruction-like, forwarding or look-alike-character text that gate_check did not hold; the text was withheld and must be held for human review.", "quality-gate-criteria.md #8.1-#8.3"
            escalations.append(f"G8: embedded-instruction tripwire in {path} at severity_rank - text withheld; hold for reviewing partner/QRM (severity-rules.md #3.6)")
        findings.append({"finding_id": f"{SR_G8_PREFIX}{hit_index}", "gate_id": "G8", "severity": "release_blocker", "title": title, "detail": detail, "location": location, "criteria_section": section, "confidence": 0.99, "source": ENGINE, "citation": "quality-gate-criteria.md #8.1-#8.3, #8.7; severity-rules.md #1.1, #3.6"})
    if len(hits) > MAX_G8_HITS:
        escalations.append(f"G8: {len(hits) - MAX_G8_HITS} further embedded-instruction hit(s) at severity_rank not listed individually - hold for reviewing partner/QRM (severity-rules.md #3.6)")
    for item in payload["gate_results"]:
        if item["gate_id"] == "G8":
            item["status"], item["highest_severity"], item["finding_count"] = gate_summary(findings, "G8")

def main():
    parser = argparse.ArgumentParser(description="Rank gate findings and compute release-readiness status.")
    parser.add_argument("--gates", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    try:
        generated_at = validate_generated_at(args.generated_at)
        payload = load_json(args.gates)
        require_contract(payload)
        for index, item in enumerate(payload["findings"]):
            validate_finding(index, item)
        rules.validate_contract(payload, "severity_rank")
        reconcile_gate_results(payload["findings"], payload["gate_results"])
        rederive_gate_findings(payload)
        g8_hits = screen_embedded_instructions(payload)
        if g8_hits:
            add_g8_findings(payload, g8_hits)
        findings, duplicates = collapse_duplicates(payload["findings"])
        payload["findings"] = findings
        escalations = payload["escalations"]
        for finding_id, count in duplicates.items():
            kept = next(item for item in findings if item["finding_id"] == finding_id)
            escalations.append(f"{finding_id}: {count} findings shared this finding_id; one was kept at the highest severity ({kept['severity']}) - reviewing partner/QRM to confirm (severity-rules.md #3.4)")
        for item in findings:
            if float(item.get("confidence", 1.0)) < CONFIDENCE_FLOOR:
                escalations.append(f"{item['finding_id']}: confidence {item.get('confidence')} below {CONFIDENCE_FLOOR} - human confirmation required (severity-rules.md #2.1)")
        ranked = []
        for index, item in enumerate(sorted(findings, key=sort_key), start=1):
            ranked_item = dict(item)
            ranked_item["rank"] = index
            ranked_item["ranking_basis"] = "severity, confidence, page, paragraph (severity-rules.md #3.2)"
            ranked.append(ranked_item)
        blockers = sum(1 for item in findings if item["severity"] == "release_blocker")
        must_fix = sum(1 for item in findings if item["severity"] == "must_fix")
        advisories = sum(1 for item in findings if item["severity"] == "advisory")
        if blockers:
            status = STATUS_WITH_BLOCKER
            summary = f"{blockers} release blocker(s) require reviewing-partner/QRM judgement before any client issue. Blockers cannot be auto-downgraded."
        elif must_fix:
            status = STATUS_WITH_MUST_FIX
            summary = f"{must_fix} must-fix item(s) remain before partner/QRM judgement."
        elif advisories:
            status = STATUS_WITH_ADVISORIES
            summary = "Only advisory items remain; partner/QRM judgement still required."
        elif escalations:
            # An escalation is a hold even without a finding: it can never end in the no-findings verdict.
            status = STATUS_WITH_BLOCKER
            summary = f"No engine findings, but {len(escalations)} escalation(s) hold release for reviewing-partner/QRM judgement before any client issue."
        else:
            status = STATUS_CLEAN
            summary = "No engine findings; partner/QRM judgement still required."
        if escalations and (blockers or must_fix or advisories):
            # The verdict follows the highest finding severity; the summary must still surface every escalation.
            count = len(escalations)
            summary += f" {count} escalation{' needs' if count == 1 else 's need'} partner/QRM confirmation before release."
        payload["ranked_findings"] = ranked
        payload["release_readiness"] = {"status": status, "release_blockers": blockers, "must_fix": must_fix, "advisories": advisories, "summary": summary, "confidence": 0.96, "source": ENGINE, "citation": "severity-rules.md #3.1-#3.3; severity-rules.md #4.1-#4.2"}
        provenance = payload.setdefault("provenance", {})
        if generated_at:
            provenance["generated_at"] = generated_at
        provenance.setdefault("engines", []).append(f"severity_rank/{ENGINE_VERSION}")
        rules.write_json_atomic(args.out, payload)
        print(f"severity_rank: status={status}, ranked_findings={len(ranked)} -> {os.path.basename(args.out)}")
        return 0
    except InputError as exc:
        print(f"severity_rank input error: {exc}", file=sys.stderr)
        return 1
    except RecursionError:
        print("severity_rank input error: input is nested too deeply to process safely", file=sys.stderr)
        return 1
    except (KeyError, TypeError, AttributeError, ValueError, IndexError) as exc:
        print(f"severity_rank input error: malformed input ({type(exc).__name__}; details withheld because they may quote untrusted text)", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
