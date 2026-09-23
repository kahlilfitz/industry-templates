# Scenario B - Drama path

This scenario is built to fool a skim reviewer. The longest entry reads like professional English, but it is rejectable: 7.5 hours, four activity classes, prohibited wording and vague phrases. A duplicate same-meeting narrative, a plausible but wrong task code, a non-billable internal entry and three hours of unrecorded document work are all surfaced by deterministic engines.

Run order:

1. `narrative_draft.py --activity activity.json --out expected/drafted.json`
2. `code_map.py --drafted expected/drafted.json --out expected/coded.json`
3. `guideline_check.py --coded expected/coded.json --out expected/governed.json`
