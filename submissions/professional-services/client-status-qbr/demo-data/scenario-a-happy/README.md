# Scenario A - happy path

The clean case: the plan is broadly on track, burn including WIP is within tolerance, there are
no open scope changes and the few open items are current.

Expected: `variance-calc` computes schedule=green, budget=green, scope=green and overall=green;
`item_age` finds no stale risks, no overdue decisions and no overdue actions. One client-owned
clarification appears as a pending client action, but it is not overdue.

Start from `raw/` to exercise the Connect skills, or from `status-input.json` to exercise the
engines alone.
