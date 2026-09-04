# Production Planning - Cowork Plugin (Wave 2, heaviest build)
Workflow Orchestrator (Connect -> Analyze -> Automate -> Act) · attended, draft-first; solver/APS and live execution-system publishing are the graduation, not v1.
Skills: demand-pull -> capacity-check -> schedule-optimize -> shift-plan-draft.
Contract: mfg.production-planning.v1. Engines: capacity_check (#1 load/utilization, #2 material gates), sequence_optimize (deterministic campaign heuristic #3, commitment protection #4, naive-vs-optimized comparison). Constants mirror references/scheduling-rules.md.
Demos: scenario-a-happy (normal week - campaigns save changeover hours, everything on time), scenario-b-drama ("92% loaded, we're fine" - run-hours fit, but the naive due-date sequence burns 10h in changeovers and misses the committed Northwind order; material for the hot order gates Wednesday; the campaign sequence protects the commitment).
Grounded in routing/capacity data, changeover matrices, scheduling rules. Boundary: drafted shift plan; publishing is the planner's action.
