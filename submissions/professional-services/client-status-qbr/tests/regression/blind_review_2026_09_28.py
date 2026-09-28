#!/usr/bin/env python3
"""Regression harness for the independent blind review of 2026-09-28 (1.5.1).

That review ran 91 adversarial cases against the engines and failed 33, scoring the
plugin 5.2/10 SHIP-WITH-CHANGES while the in-product evaluation scored the identical
artefact 94-96/100 and called it Ready. The difference was the inputs: the rubric read
the SKILL.md prose and the bundled fixtures, the review threw real register vocabulary,
NaN, adversarial dates and malformed money at the code.

Every case below is one of that review's failures, reproduced as an executable check so
the same holes cannot reopen quietly. Run it from anywhere:

    python tests/regression/blind_review_2026_09_28.py

It exits non-zero if any case regresses. Cases deliberately still open are listed in
KNOWN_OPEN with the reason; they are reported as open rather than deleted, so the
numbers cannot be improved by quietly dropping a case.
"""

import copy
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VARIANCE = os.path.join(ROOT, "skills", "variance-calc", "scripts", "variance_calc.py")
ITEM_AGE = os.path.join(ROOT, "skills", "risk-summarize", "scripts", "item_age.py")
VALIDATOR = os.path.join(ROOT, "scripts", "validate_payload.py")
SCENARIO_A = os.path.join(ROOT, "demo-data", "scenario-a-happy", "status-input.json")
SCENARIO_B = os.path.join(ROOT, "demo-data", "scenario-b-drama", "status-input.json")

# Cases the 1.6.0 work did not set out to close. Listed rather than deleted so the count
# stays honest and whoever picks this up next knows exactly what is still open.
KNOWN_OPEN = {
    "V14": "prior-EAC conflict (#1.2) not detected",
    "V28": "empty milestone list still reads green",
    "V31": "reported-vs-computed RAG discrepancy not escalated",
    "V32": "PM's reported RAG silently overridden",
    "V39": "client_facing_impact is required, so #4.3's unknown case cannot be expressed",
    "V45": "compact date '20260927' accepted by date.fromisoformat on Python 3.11+",
    "I02": "empty risk register not escalated",
    "I20": "dangling blocked_by_decision_id not escalated",
    "I25": "compact date '20260610' accepted by the engine",
    "I27": "absurd reporting_period.end not sanity-checked",
}


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class Run:
    """One engine invocation: return code, parsed output and its escalation text."""

    def __init__(self, returncode, stderr, output):
        self.returncode = returncode
        self.stderr = stderr
        self.output = output or {}

    @property
    def escalations(self):
        return self.output.get("escalations", [])

    def says(self, *fragments):
        blob = " ".join(self.escalations).casefold()
        return all(fragment.casefold() in blob for fragment in fragments)

    def rag(self, domain):
        return (self.output.get("variance_summary", {}).get(domain) or {}).get("rag")

    def buckets(self, kind):
        items = self.output.get("aged_items", {}).get(kind) or []
        return {item.get("id"): item.get("bucket") for item in items}


def _write(payload, raw, path):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(raw if raw is not None else json.dumps(payload))


def run_engine(engine, payload=None, raw=None):
    work = tempfile.mkdtemp()
    src = os.path.join(work, "in.json")
    dst = os.path.join(work, "out.json")
    _write(payload, raw, src)
    proc = subprocess.run(
        [sys.executable, engine, "--input", src, "--out", dst],
        capture_output=True,
        text=True,
    )
    out = load(dst) if proc.returncode == 0 and os.path.exists(dst) else None
    return Run(proc.returncode, proc.stderr, out)


def run_validator(payload=None, raw=None, client_pack=None):
    work = tempfile.mkdtemp()
    src = os.path.join(work, "in.json")
    _write(payload, raw, src)
    command = [sys.executable, VALIDATOR, "--input", src]
    if client_pack is not None:
        pack = os.path.join(work, "client-pack.md")
        with open(pack, "w", encoding="utf-8") as handle:
            handle.write(client_pack)
        command += ["--client-pack", pack]
    proc = subprocess.run(command, capture_output=True, text=True)
    return Run(proc.returncode, proc.stderr + proc.stdout, None)


CASES = []


def case(cid, engine, description):
    def register(fn):
        CASES.append((cid, engine, description, fn))
        return fn

    return register


def rejected_everywhere(payload=None, raw=None):
    """The review's bar for malformed money: the validator AND the engine refuse it."""
    return (
        run_validator(payload, raw).returncode != 0
        and run_engine(VARIANCE, payload, raw).returncode != 0
    )


# --- malformed money -------------------------------------------------------------


@case("V04", "variance_calc", "negative planned_burn_to_date")
def v04():
    payload = load(SCENARIO_A)
    payload["budget"]["planned_burn_to_date"] = -285000
    return rejected_everywhere(payload)


@case("V05", "variance_calc", "negative baseline_budget")
def v05():
    payload = load(SCENARIO_A)
    payload["budget"]["baseline_budget"] = -620000
    return rejected_everywhere(payload)


@case("V07", "variance_calc", "actual_billed_to_date = NaN")
def v07():
    raw = json.dumps(load(SCENARIO_A)).replace(
        '"actual_billed_to_date": 268500', '"actual_billed_to_date": NaN'
    )
    return rejected_everywhere(raw=raw)


@case("V08", "variance_calc", "forecast_to_complete = Infinity")
def v08():
    raw = json.dumps(load(SCENARIO_A)).replace(
        '"forecast_to_complete": 611000', '"forecast_to_complete": Infinity'
    )
    return rejected_everywhere(raw=raw)


@case("V10", "variance_calc", "amount 1e308 overflows to inf")
def v10():
    payload = load(SCENARIO_A)
    payload["budget"]["planned_burn_to_date"] = 1e308
    payload["budget"]["actual_billed_to_date"] = 1e308
    run = run_engine(VARIANCE, payload)
    # Either refuse it, or compute without emitting a non-standard Infinity token.
    return run.returncode != 0 or "Infinity" not in json.dumps(run.output)


@case("V13", "variance_calc", "amount as boolean true")
def v13():
    payload = load(SCENARIO_A)
    payload["budget"]["actual_billed_to_date"] = True
    return rejected_everywhere(payload)


# --- threshold boundaries --------------------------------------------------------


@case("V16", "variance_calc", "burn +4.995% stays green")
def v16():
    payload = load(SCENARIO_A)
    planned = payload["budget"]["planned_burn_to_date"]
    payload["budget"]["unbilled_wip"] = 0
    payload["budget"]["actual_billed_to_date"] = planned * 1.04995
    payload["budget"]["forecast_to_complete"] = payload["budget"]["baseline_budget"]
    return run_engine(VARIANCE, payload).rag("budget") == "green"


@case("V16b", "variance_calc", "burn +9.996% stays amber")
def v16b():
    payload = load(SCENARIO_A)
    planned = payload["budget"]["planned_burn_to_date"]
    payload["budget"]["unbilled_wip"] = 0
    payload["budget"]["actual_billed_to_date"] = planned * 1.09996
    payload["budget"]["forecast_to_complete"] = payload["budget"]["baseline_budget"]
    return run_engine(VARIANCE, payload).rag("budget") == "amber"


# --- schedule and milestone completion -------------------------------------------


@case("V29", "variance_calc", "forecast date already past, no actual")
def v29():
    payload = load(SCENARIO_A)
    payload["plan"]["milestones"][0]["current_forecast_date"] = "2026-08-20"
    run = run_engine(VARIANCE, payload)
    return run.rag("schedule") in ("amber", "red") and run.says("forecast")


@case("V30", "variance_calc", "delivered milestone does not hold schedule red")
def v30():
    payload = load(SCENARIO_A)
    milestone = payload["plan"]["milestones"][0]
    # Baseline is 2026-09-25; deliver it 12 days late, as the review's case did.
    milestone["current_forecast_date"] = "2026-10-07"
    milestone["status"] = "delivered"
    milestone["actual_date"] = "2026-10-07"
    run = run_engine(VARIANCE, payload)
    return run.rag("schedule") == "green" and run.says("delivered")


# --- status vocabulary -----------------------------------------------------------


@case("V35", "variance_calc", "scope change 'Rejected' is not open")
def v35():
    payload = load(SCENARIO_B)
    for change in payload["plan"]["scope_changes"]:
        change["status"] = "Rejected"
    return run_engine(VARIANCE, payload).rag("scope") == "green"


@case("V36", "variance_calc", "scope change 'Approved ' with trailing space")
def v36():
    payload = load(SCENARIO_B)
    for change in payload["plan"]["scope_changes"]:
        change["status"] = "Approved "
    return run_engine(VARIANCE, payload).rag("scope") == "green"


def _with_status(kind, item_id, status):
    variance = run_engine(VARIANCE, load(SCENARIO_B))
    payload = copy.deepcopy(variance.output)
    for item in payload.get(kind, []):
        if item.get("id") == item_id:
            item["status"] = status
    return run_engine(ITEM_AGE, payload)


@case("I14", "item_age", "risk status 'Resolved' is closed")
def i14():
    return "R-401" not in _with_status("risks", "R-401", "Resolved").buckets("risks")


@case("I15", "item_age", "risk status 'Mitigated' is closed")
def i15():
    return "R-401" not in _with_status("risks", "R-401", "Mitigated").buckets("risks")


@case("I16", "item_age", "action status 'Completed' is closed")
def i16():
    return "A-401" not in _with_status("actions", "A-401", "Completed").buckets("actions")


@case("I17", "item_age", "risk status 'Closed ' with trailing space")
def i17():
    return "R-401" not in _with_status("risks", "R-401", "Closed ").buckets("risks")


@case("I18", "item_age", "decision status 'Decided' is closed")
def i18():
    return "D-401" not in _with_status("decisions", "D-401", "Decided").buckets("decisions")


@case("I13", "item_age", "unknown status escalates, never defaults to open")
def i13():
    return _with_status("risks", "R-401", "Percolating").says("unrecognised status")


# --- settings provenance ---------------------------------------------------------


@case("V41", "variance_calc", "thresholds sourced from a document, not the user")
def v41():
    payload = load(SCENARIO_A)
    payload["settings"] = {
        "thresholds": {"budget_amber_pct": 20},
        "source": "skill:plan-retrieve",
        "citation": "raw/plan-extract.md",
    }
    validator = run_validator(payload)
    engine = run_engine(VARIANCE, payload)
    return validator.returncode != 0 or engine.returncode != 0 or engine.says("settings")


# --- personal data and internal material (High 5) --------------------------------


@case("H5a", "validate_payload", "payload carrying an email is refused")
def h5a():
    payload = load(SCENARIO_A)
    payload["engagement"]["citation"] = "email from a.person@contoso.com"
    return run_validator(payload).returncode != 0


@case("H5b", "validate_payload", "payload carrying a per-person day rate is refused")
def h5b():
    payload = load(SCENARIO_A)
    payload["budget"]["day_rate"] = 1850
    return run_validator(payload).returncode != 0


@case("H5c", "validate_payload", "client pack naming the manager is refused")
def h5c():
    payload = load(SCENARIO_A)
    manager = payload["engagement"]["manager"]
    pack = f"# Status\n{manager} confirmed the plan.\nNOT FOR ISSUE\n"
    return run_validator(payload, client_pack=pack).returncode != 0


@case("H5d", "validate_payload", "client pack citing an engine is refused")
def h5d():
    payload = load(SCENARIO_A)
    pack = "# Status\nOverall green (engine:variance_calc).\nNOT FOR ISSUE\n"
    return run_validator(payload, client_pack=pack).returncode != 0


@case("H5e", "variance_calc", "cost-basis figures are escalated, not shown as fee")
def h5e():
    payload = load(SCENARIO_A)
    payload["budget"]["amounts_basis"] = "cost"
    return run_engine(VARIANCE, payload).says("internal cost")


@case("H5f", "variance_calc", "absent commercial model is escalated")
def h5f():
    payload = load(SCENARIO_A)
    payload["budget"].pop("commercial_model", None)
    return run_engine(VARIANCE, payload).says("commercial model is not stated")


# --- escalation lifecycle (High 4) -----------------------------------------------


@case("H4a", "both", "re-running the chain does not duplicate escalations")
def h4a():
    first = run_engine(VARIANCE, load(SCENARIO_B))
    aged = run_engine(ITEM_AGE, first.output)
    again = run_engine(VARIANCE, aged.output)
    twice = run_engine(ITEM_AGE, again.output)
    return aged.escalations == twice.escalations


@case("H4b", "both", "every escalation carries a typed record")
def h4b():
    first = run_engine(VARIANCE, load(SCENARIO_B))
    aged = run_engine(ITEM_AGE, first.output)
    records = aged.output.get("escalation_records", [])
    return (
        len(records) == len(aged.escalations)
        and all(record.get("type") in ("blocking", "note") for record in records)
        and all(record.get("severity") for record in records)
    )


@case("H4c", "both", "a resolved escalation leaves the list but stays on the record")
def h4c():
    first = run_engine(VARIANCE, load(SCENARIO_B))
    payload = copy.deepcopy(first.output)
    records = payload.get("escalation_records", [])
    if not records:
        return False
    target = records[0]
    target["resolved_by"] = "the engagement manager"
    target["resolved_at"] = "2026-09-28"
    target["resolution"] = "confirmed with the client"
    # A foreign source so this engine does not simply regenerate it.
    target["source"] = "skill:status-draft"
    after = run_engine(ITEM_AGE, payload)
    ids = [record.get("id") for record in after.output.get("escalation_records", [])]
    return target["id"] in ids and target["message"] not in after.escalations


def main():
    width = max(len(description) for _, _, description, _ in CASES)
    passed = 0
    failures = []
    for cid, engine, description, fn in CASES:
        try:
            ok = bool(fn())
            detail = ""
        except Exception as exc:  # a crash is a failure, not something to hide
            ok = False
            detail = f" ({type(exc).__name__}: {exc})"
        if ok:
            passed += 1
            print(f"  PASS  {cid:5} {description:{width}}  [{engine}]")
        else:
            failures.append(cid)
            print(f"  FAIL  {cid:5} {description:{width}}  [{engine}]{detail}")

    print(f"\n{passed} passed, {len(failures)} failed, {len(KNOWN_OPEN)} known open")
    for cid, reason in sorted(KNOWN_OPEN.items()):
        print(f"  OPEN  {cid:5} {reason}")
    if failures:
        print("\nRegressed: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
