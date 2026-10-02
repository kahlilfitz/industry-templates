#!/usr/bin/env python3
"""severity_rank - deterministic finding ranking and review-status verdict."""
import copy
import re
import sys

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
SR_SPOOF_ID = "SR-G8-engine-id-spoof"
ESCALATION_GATES = GATE_IDS + ("other",)
# G8 holds that re-derivation cannot reproduce from gate-checked.json alone: gate_check's spoof and pre-restoration hits
# depend on input it has since corrected, and severity_rank's own holds come from an earlier severity_rank run. Each is
# accepted only as a G8 release blocker carrying its own engine's source tag, so accepting one can only hold the run.
# The numbered suffix is bounded by what the engines can emit (1..MAX_G8_HITS), so an impossible sixth hold is forged.
G8_HIT_NUMBER = "(?:" + "|".join(str(number) for number in range(1, MAX_G8_HITS + 1)) + ")"
HISTORY_HOLD_ID = re.compile(r"^(?:GC|SR)-G8-(?:engine-id-spoof|embedded-instruction-" + G8_HIT_NUMBER + r")$")

InputError = rules.InputError

def load_json(path):
    return rules.load_json_file(path, "gate-check input")

validate_generated_at = rules.validate_generated_at

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
        if value is not None and not rules.is_position(value):
            raise InputError(f"{label}: location.{key} must be an integer of {rules.MIN_POSITION} or more, or null, got "
                             f"{rules.describe(value) if not rules.is_integer(value) else 'an integer below ' + str(rules.MIN_POSITION)}; record the physical "
                             f"page number and keep printed labels such as roman numerals in location.label")

def sort_key(item):
    # Findings without a page or paragraph (register- or field-level) rank after page-located findings
    # of the same severity and confidence.
    location = item.get("location") or {}
    page, paragraph = location.get("page"), location.get("paragraph")
    return (SEVERITY_ORDER[item["severity"]], -float(item.get("confidence", 0.0)), 9999 if page is None else page, 9999 if paragraph is None else paragraph, item.get("finding_id", ""))

def collapse_duplicates(findings):
    """Keep one finding per finding_id at the highest severity (first occurrence on a tie), so a duplicate is never
    counted twice and can never lower severity (severity-rules.md #3.1). Entry validation already refuses copies that
    differ (quality-gate-criteria.md #8.11), so this is a backstop. IDs are compared in canonical form (rules.canonical_id),
    and the kept finding keeps its original ID. Returns (kept, {canonical finding_id: copies})."""
    kept, positions, copies = [], {}, {}
    for item in findings:
        finding_id = rules.canonical_id(item["finding_id"])
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
        missing = [gate for gate in GATE_IDS if gate not in seen]
        repeated = [gate for gate in GATE_IDS if seen.count(gate) > 1]
        raise InputError(f"gate_results must contain exactly one entry per gate {', '.join(GATE_IDS)}; got {len(seen)} entries"
                         + (f", missing {', '.join(missing)}" if missing else "") + (f", repeated {', '.join(repeated)}" if repeated else ""))
    by_gate = {item["gate_id"]: item for item in gate_results}
    mismatched = [gate for gate in GATE_IDS
                  if (by_gate[gate]["status"], by_gate[gate]["highest_severity"], by_gate[gate]["finding_count"]) != gate_summary(findings, gate)]
    if mismatched:
        raise InputError(f"gate_results do not match findings[] for {', '.join(mismatched)} (status/highest_severity/finding_count); re-run gate_check, findings cannot be removed or downgraded after the gate run")

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
    mapped["findings"] = am_findings_for_rederivation(mapped, [copy.deepcopy(item) for item in payload["findings"] if item["finding_id"].startswith("AM-")])
    mapped["escalations"] = []
    try:
        evaluated = gc.evaluate(mapped)
    except InputError as exc:
        raise InputError(f"gate_check re-derivation failed on the carried mapped input ({exc}); re-run gate_check") from exc
    derived = evaluated["findings"]
    supplied = {}
    for item in payload["findings"]:
        key = (item["finding_id"], item.get("gate_id"))
        supplied[key] = max(supplied.get(key, 0), SEVERITY_RANK[item["severity"]])
    # Counted by gate and severity (engine constants), never named: an engine finding ID carries an assertion, register
    # or evidence ID from the input (quality-gate-criteria.md #8.9).
    counts = {"missing": {}, "downgraded": {}}
    for item in derived:
        present = supplied.get((item["finding_id"], item["gate_id"]), 0)
        if present < SEVERITY_RANK[item["severity"]]:
            tally = counts["downgraded" if present else "missing"]
            tally[(item["gate_id"], item["severity"])] = tally.get((item["gate_id"], item["severity"]), 0) + 1
    if counts["missing"] or counts["downgraded"]:
        shown = "; ".join(f"{sum(counts[kind].values())} {kind} (" + ", ".join(f"{gate} {severity} x{counts[kind][(gate, severity)]}" for gate in GATE_IDS for severity in SEVERITY_ORDER if (gate, severity) in counts[kind]) + ")"
                          for kind in ("missing", "downgraded") if counts[kind])
        raise InputError(f"findings[] do not contain every finding gate_check derives from the carried mapped input: {shown}. Re-run gate_check; engine findings cannot be removed or downgraded after the gate run (severity-rules.md #3.7)")
    reconcile_derived_escalations(payload["escalations"], evaluated["escalations"])
    reconcile_gate_fields(payload["gate_results"], evaluated["gate_results"])
    return evaluated


def escalation_gate(entry):
    """The gate an escalation names (a `Gn:` prefix or an object's gate_id), as an engine constant, else None."""
    gate = entry.get("gate_id") if isinstance(entry, dict) else entry.split(":", 1)[0] if isinstance(entry, str) else None
    return next((known for known in GATE_IDS if known == gate), None)


def reconcile_derived_escalations(supplied, derived):
    """Every escalation gate_check derives from the carried mapped input must still be in escalations[] (#3.7). An
    escalation is a hold that needs partner/QRM confirmation, so deleting one would relax the review; extra escalations
    may only add. Counted by gate (engine constants), never quoted (quality-gate-criteria.md #8.9)."""
    missing = [entry for entry in derived if entry not in supplied]
    if not missing:
        return
    gates = [escalation_gate(entry) or "other" for entry in missing]
    shown = ", ".join(f"{gate} x{sum(1 for named in gates if named == gate)}" for gate in ESCALATION_GATES if gate in gates)
    raise InputError(f"escalations[] do not contain every escalation gate_check derives from the carried mapped input: {len(missing)} missing ({shown}). Re-run gate_check; engine escalations cannot be removed after the gate run (severity-rules.md #3.7)")


GATE_ENGINE_FIELDS = ("name", "confidence", "source", "citation")


def reconcile_gate_fields(supplied, derived):
    """gate_results' name, confidence, source and citation are gate_check constants; they must equal what
    re-derivation gives, so an edited gate entry can never relabel or re-source a gate (#3.5, #3.7)."""
    expected = {item["gate_id"]: item for item in derived}
    differing = [gate for gate in GATE_IDS if any(entry["gate_id"] == gate and any(entry.get(field) != expected[gate][field] for field in GATE_ENGINE_FIELDS) for entry in supplied)]
    if differing:
        raise InputError(f"gate_results for {', '.join(differing)} do not carry gate_check's own {'/'.join(GATE_ENGINE_FIELDS)}; re-run gate_check, gate entries cannot be edited after the gate run (severity-rules.md #3.7 and #3.5)")


def am_findings_for_rederivation(mapped, am_findings):
    """One AM- finding per canonical ID for gate_check re-derivation: the genuine copy (what assertion_map recomputes
    from the carried assertions and evidence, gc.genuine_am_finding) when one is present, otherwise the highest
    severity. A forged copy colliding with a genuine one is then removed and held by remove_forged_engine_findings,
    exactly as gate_check holds it (quality-gate-criteria.md #8.4)."""
    probe = copy.deepcopy(mapped)
    probe["findings"] = []
    rules.withhold_untrusted(probe)
    expected = gc.expected_assertion_outputs(probe, probe.get("evidence_set")) if isinstance(probe.get("assertions"), list) else None
    expected_am = expected["findings"] if expected else None
    chosen = {}
    for item in am_findings:
        key, genuine = rules.canonical_id(item["finding_id"]), gc.genuine_am_finding(item, expected_am)
        current = chosen.get(key)
        if current is None or (genuine and not current[1]) or (genuine == current[1] and SEVERITY_ORDER[item["severity"]] < SEVERITY_ORDER[current[0]["severity"]]):
            chosen[key] = (item, genuine)
    return [item for item, _ in chosen.values()]


def engine_owner(item):
    """The engine an incoming finding claims, by finding-ID prefix or source tag, both compared in canonical form
    (rules.engine_id_owner, rules.canonical_tag: `gc_G8-x`, `Engine :gate_check`); None for other findings. Called on
    the raw finding, before any text is withheld, so a flagged `GC-<instruction>` ID keeps its owner (#8.11)."""
    owner = rules.engine_id_owner(item.get("finding_id"))
    return owner or (rules.canonical_tag(item.get("source")) if rules.is_engine_tag(item.get("source")) else None)


def is_history_hold(item):
    """A G8 history hold (HISTORY_HOLD_ID) carried as a release blocker under its own engine's source tag."""
    return bool(HISTORY_HOLD_ID.match(item["finding_id"])) and item["gate_id"] == "G8" and item["severity"] == "release_blocker" \
        and item.get("source") == (ENGINE if item["finding_id"].startswith("SR-") else gc.ENGINE)


def remove_forged_engine_findings(payload, derived, raw_owners=()):
    """Hold every engine-owned finding to re-derivation (severity-rules.md #3.8, quality-gate-criteria.md #8.4).

    A finding with an engine-owned ID prefix (AM-, GC-, SR-) or an engine source tag stands only when gate_check
    re-derivation produces exactly that finding (same ID and every field equal), or when it is a G8 history hold
    (HISTORY_HOLD_ID) carried as a release blocker under its own engine's tag. Anything else is forged: it is removed,
    and when its ID is one re-derivation produces and no exact copy remains, the derived finding is restored in its
    place. `raw_owners[i]` is the owner of findings[i] read before screening withheld any text, so a flagged engine ID
    is still treated as engine-owned. Returns the labels of the forged findings (never their text)."""
    derived_by_id = {item["finding_id"]: item for item in derived}
    kept, forged = [], []
    for index, item in enumerate(payload["findings"]):
        owner = (raw_owners[index] if index < len(raw_owners) else None) or engine_owner(item)
        if owner is None or derived_by_id.get(item["finding_id"]) == item:
            kept.append(item)
            continue
        if is_history_hold(item):
            kept.append(item)
            continue
        forged.append((index, item))
    labels = []
    for index, item in forged:
        labels.append(gc.safe_token(item["finding_id"], f"findings[{index}]"))
        restored = derived_by_id.get(item["finding_id"])
        if restored is not None and restored not in kept:
            kept.append(copy.deepcopy(restored))
    payload["findings"] = kept
    return labels


def add_spoof_hold(payload, forged):
    """One SR-G8 release blocker and an escalation for forged engine findings (severity-rules.md #3.8)."""
    payload["findings"].append({"finding_id": SR_SPOOF_ID, "gate_id": "G8", "severity": "release_blocker", "title": "Engine finding forged or altered after the gate run",
                                "detail": f"{len(forged)} finding(s) carried an engine-owned finding ID or engine source tag but are not what gate_check re-derives from the carried mapped input; they were removed and any engine finding they replaced was restored. Engine findings cannot be added, replaced or edited after the gate run.",
                                "location": gc.unplaced("Gate-check findings", "findings[] supplied to severity_rank"), "criteria_section": "quality-gate-criteria.md #8.4", "confidence": 0.99, "source": ENGINE,
                                "citation": "quality-gate-criteria.md #8.1, #8.4; severity-rules.md #1.1, #3.8"})
    payload["escalations"].append(f"G8: finding(s) {', '.join(forged)} used engine-owned IDs or source tags without matching gate_check re-derivation and were removed - hold for reviewing partner/QRM (severity-rules.md #3.8)")


def refresh_gate_results(payload):
    """Recompute every gate's status, highest severity and count from the final findings, after forged findings are
    removed, G8 holds added and duplicates collapsed, so the output always passes its own validation (#3.5)."""
    for item in payload["gate_results"]:
        item["status"], item["highest_severity"], item["finding_count"] = gate_summary(payload["findings"], item["gate_id"])


def covered_by_gate_check(findings, escalations, path):
    """True when gate_check already holds this primary-field hit under its own G8 finding. `findings` and
    `escalations` are what gate_check re-derives from the carried mapped input (#3.7), never the carried copies: a pasted
    G8 history hold or overflow note must not stop severity_rank reporting a field (quality-gate-criteria.md #8.16)."""
    if any(item["finding_id"].startswith("GC-G8-embedded-instruction-") and f"Untrusted field {path} " in item.get("detail", "") for item in findings):
        return True
    listed = sum(1 for item in findings if item["finding_id"].startswith("GC-G8-embedded-instruction-"))
    overflow = any(isinstance(entry, str) and entry.startswith("G8: ") and "further embedded-instruction hit(s) not listed individually" in entry for entry in escalations)
    return listed >= MAX_G8_HITS and overflow

# Escalations severity_rank itself writes about an engine finding (severity-rules.md #2.1, #3.4); the finding ID may
# carry a withheld assertion ID, which the engine finding binds.
OWN_ESCALATIONS = (
    re.compile(r": confidence [^\r\n]* below " + re.escape(str(CONFIDENCE_FLOOR)) + r" - human confirmation required \(severity-rules\.md #2\.1\)"),
    re.compile(r": [0-9]+ findings shared this finding_id; one was kept at the highest severity \((?:release_blocker|must_fix|advisory)\) - reviewing partner/QRM to confirm \(severity-rules\.md #3\.4\)"),
)


def own_escalation(entry, engine_ids):
    """True when entry is one of severity_rank's own escalations about an engine finding in `engine_ids`."""
    if not isinstance(entry, str):
        return False
    return any(entry.startswith(finding_id + ": ") and pattern.fullmatch(entry[len(finding_id):]) for finding_id in engine_ids for pattern in OWN_ESCALATIONS)


def placeholder_hits(payload, rederived, raw_owners, hits):
    """A G8 hit for each withheld placeholder in a position no stage recomputes (a reviewer finding, an escalation no
    engine derived, provenance or another note) that no standing G8 hold names exactly (quality-gate-criteria.md
    #8.18). A hold binds a placeholder only when it names that path: gate_check's `Untrusted field <path> ` or
    severity_rank's `Field <path> reached`, from a re-derived finding or a G8 history hold. A hold elsewhere never
    binds a newly placed placeholder."""
    findings = payload["findings"]
    engine_ids = [item["finding_id"] for index, item in enumerate(findings) if index < len(raw_owners) and raw_owners[index] is not None]
    derived_escalations = rederived["escalations"]
    holds = [item.get("detail", "") for item in list(rederived["findings"]) + [item for item in findings if is_history_hold(item)] if item["gate_id"] == "G8"]
    held = {path for path, _ in hits}

    def bound(path):
        return path in held or any(f"Untrusted field {path} " in detail or f"Field {path} reached" in detail for detail in holds)

    paths = rules.placeholder_paths(payload, lambda index, item: index < len(raw_owners) and raw_owners[index] is not None,
                                    lambda entry: entry in derived_escalations or own_escalation(entry, engine_ids))
    return rules.unbound_placeholder_hits(paths, bound)


def screen_embedded_instructions(payload, rederived, raw_owners=()):
    """Screen every incoming string through steering_guard exactly as gate_check does (severity-rules.md #3.6) and
    withhold every string that trips, everywhere it appears (quality-gate-criteria.md #8.7).

    A primary-field hit gate_check already holds under its own G8 finding is not counted twice. Every string in the
    derived sections (findings, escalations, gate_results, provenance, assertion_mappings and any other notes) that
    trips the detector, and is not a copy of primary text already held, is a new hit. Text already replaced by a
    withheld marker upstream stays withheld. Returns (path, reason) for each new hit; the payload is updated in place."""
    findings, escalations = rederived["findings"], rederived["escalations"]
    hits = [(path, reason) for path, reason, derived in rules.withhold_untrusted(payload) if derived or not covered_by_gate_check(findings, escalations, path)]
    hits += placeholder_hits(payload, rederived, raw_owners, hits)
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

def main():
    parser = rules.EngineArgumentParser(prog="severity_rank.py", description="Rank gate findings and compute release-readiness status.")
    parser.add_argument("--gates", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    try:
        generated_at = validate_generated_at(args.generated_at)
        payload = load_json(args.gates)
        require_contract(payload)
        # Every section is checked against the contract before any reader touches it (quality-gate-criteria.md #8.16).
        rules.validate_contract(payload, "severity_rank")
        for index, item in enumerate(payload["findings"]):
            validate_finding(index, item)
        reconcile_gate_results(payload["findings"], payload["gate_results"])
        rederived = rederive_gate_findings(payload)
        derived = rederived["findings"]
        # Ownership is read before screening can withhold an ID (quality-gate-criteria.md #8.4, #8.11).
        raw_owners = [engine_owner(item) for item in payload["findings"]]
        # Screen first, so instruction text planted in a forged finding still raises its own G8 hold before removal.
        g8_hits = screen_embedded_instructions(payload, rederived, raw_owners)
        if g8_hits:
            add_g8_findings(payload, g8_hits)
        forged = remove_forged_engine_findings(payload, derived, raw_owners)
        if forged:
            add_spoof_hold(payload, forged)
        findings, duplicates = collapse_duplicates(payload["findings"])
        payload["findings"] = findings
        refresh_gate_results(payload)
        escalations = payload["escalations"]
        for key, count in duplicates.items():
            kept = next(item for item in findings if rules.canonical_id(item["finding_id"]) == key)
            escalations.append(f"{kept['finding_id']}: {count} findings shared this finding_id; one was kept at the highest severity ({kept['severity']}) - reviewing partner/QRM to confirm (severity-rules.md #3.4)")
        for item in findings:
            if float(item.get("confidence", 1.0)) < CONFIDENCE_FLOOR:
                escalations.append(f"{item['finding_id']}: confidence {item.get('confidence')} below {CONFIDENCE_FLOOR} - human confirmation required (severity-rules.md #2.1)")
        # Escalations already carried in the input are not repeated, so a re-run on severity_rank's own output reproduces it.
        escalations[:] = rules.unique_entries(escalations)
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
        rules.record_engine(payload, f"severity_rank/{ENGINE_VERSION}", generated_at)
        rules.write_json_atomic(args.out, payload, "ranked output")
        print(f"severity_rank: status={status}, ranked_findings={len(ranked)} -> ranked output written")
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
