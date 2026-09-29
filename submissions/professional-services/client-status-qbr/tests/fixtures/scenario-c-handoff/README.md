# Scenario C - handoff (chain regression for HS-1)

Guards the defect that blocked v1.6.0: **both engines deleted every escalation written in the
contract's object form.**

The contract allows an `escalations[]` item to be a string *or* an object
(`{message, rule, item_id, source}`), and `burn-pull` SKILL.md step 5 mandates the object form.
`merge_escalations()` kept a prior entry only when `isinstance(message, str)`, so every object
was dropped — with exit 0 and no warning. The 2026-09-28 evaluation lost 5 of 5 upstream
escalations across the chain, 3 runs out of 3.

This fixture carries the exact shape a live `plan-retrieve` run produces:

| # | Form | Rule | Source | Why it must survive |
|---|---|---|---|---|
| 1 | object | `#7.3` | `skill:plan-retrieve` | the PM's *"keep it green if possible"*, recorded and not followed |
| 2 | object | `#7.2` | `skill:burn-pull` | a named day rate and a personal phone number withheld |
| 3 | string | `#1.2` | — | prior pack and plan disagree on M-401 |

**Expected: all three reach `expected/aged.json` unchanged**, having passed through
`variance-calc` and then `risk-summarize`. Neither engine owns them, so neither may rewrite or
drop them. The string entry is the control: it survived even with the defect present, so a test
that used only strings would have stayed green while client disclosures were being deleted.

Rules #6.2 and #6.3 require each engine to keep every other source's escalations. `item_age.py`
shares this logic verbatim with `variance_calc.py`, so the regression is only caught by running
the **full chain**, which is what `tests/regression/blind_review_2026_09_28.py` does here.

This fixture lives under `tests/`, which is in `NEVER_BUNDLE`, so it does not change the
distributable's hash.
