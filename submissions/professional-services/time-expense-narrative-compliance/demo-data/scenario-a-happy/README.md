# Scenario A - Happy path

Alex has three clean engagement activities and three matching time entries with no narrative yet. The engines should draft narratives, map codes and pass guideline compliance with no missing time.

Run order:

1. `narrative_draft.py --activity activity.json --out expected/drafted.json`
2. `code_map.py --drafted expected/drafted.json --out expected/coded.json`
3. `guideline_check.py --coded expected/coded.json --out expected/governed.json`
