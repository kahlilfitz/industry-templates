# Scenario A - happy path

Clean commercial-control case: Northstar Labs asks for an additional onsite board-readiness workshop. The SOW includes two operating-model workshops but explicitly excludes board and fundraising presentations. The request is obviously out of scope, has a simple role estimate, and produces a clean draft change order.

Expected: `REQ-A-001` is OUT_OF_SCOPE under SOW clause 4.2 and change-control clause 6.1. `delta_calc.py` calculates a $4,945.00 draft change-order amount, with no ambiguity and no cumulative-drift escalation.
