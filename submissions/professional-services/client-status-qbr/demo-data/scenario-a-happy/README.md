# Scenario A - happy path

The clean case: the plan is broadly on track, burn including WIP is within tolerance, there are
no open scope changes and the few open items are current.

Expected: `variance-calc` computes schedule=green, budget=green, scope=green and overall=green;
`item_age` finds no stale risks, no overdue decisions and no overdue actions. Two pending client
items appear, the palette decision D-301 and the dependent action A-302, neither overdue — they
are two views of the same client request, so report the request once and cite both ids.

Start from `raw/` to exercise the Connect skills, or from `status-input.json` to exercise the
engines alone.
