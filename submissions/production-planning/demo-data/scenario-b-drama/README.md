# Scenario B - drama path
"84% loaded, run it by due date." Three things the paper number hides:
1. The naive due-date sequence alternates families (PUMP-VALVE-PUMP-VALVE-COMP-PUMP) and
   burns ~10+ hours in changeovers (#1.1 - run-hours-only utilization is not a plan).
2. MO-9105 (committed Northwind compressor) is MATERIAL-GATED until Wed 08-19 (#2.1).
3. With changeovers + the gate, the naive sequence finishes the committed compressor late.
Expected: engine reports naive late_committed=[MO-9105], optimized campaign sequence
protects both committed orders (late_committed_optimized=[]), changeover hours drop, and
the escalations name the gate and the naive miss. A naive planner posts the due-date
sequence; the engine shows why not.
