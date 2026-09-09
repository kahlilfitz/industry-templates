# Scenario A - happy path
The inspector's no-go pin already caught it: the 12 mm bore reads 12.11 / 12.08 on
SN-004 / SN-009 (2/12 = 16.67%). Major characteristic, re-boring prohibited by note 6,
incidence over the 1% MRB threshold.
Expected: hole_diameter_mm out_of_tolerance -> MAJOR, hold_for_review (#1.2, #3.2);
lot recommendation hold_for_review; no certificate conflict (the CoC makes no dimensional
claim); everything else in tolerance. Start from raw/ to exercise spec-ingest, or from
the structured inputs to exercise the engines alone.
