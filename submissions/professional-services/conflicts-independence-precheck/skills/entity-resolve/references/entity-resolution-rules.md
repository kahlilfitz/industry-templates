# Entity Resolution Rules — Conflicts & Independence Pre-Check

Illustrative operational summaries for demo grounding. These are not controlled firm policy and do not reproduce any professional-conduct or independence standard. Engines cite these sections; constants in `entity_resolve.py` mirror the numbered rules.

## 1. Name normalization
1.1 Convert names to lowercase, trim punctuation, collapse whitespace and normalize `&` to `and`.
1.2 Preserve the original submitted name and every generated search variant in the output; never replace the intake evidence.

## 2. Legal suffix handling
2.1 Remove common legal suffixes (`inc`, `llc`, `ltd`, `plc`, `corp`, `company`, `limited`, `gmbh`, `sa`, `bv`) for scoring, but keep the suffix-bearing legal name for citations.
2.2 Do not treat different legal suffixes as proof of different entities.

## 3. Aliases, trade names and transliteration
3.1 Exact matches on controlled aliases, trading names or transliterations score as controlled matches.
3.2 If an intake name matches only an uncontrolled free-text alias, keep provenance and require the underlying source citation.

## 4. Fuzzy-match bands
4.1 Score >= 0.92 is an automatic entity match when the candidate has controlled provenance.
4.2 Score >= 0.78 and < 0.92 is a forced human-review band. The engine may name the candidate, but it must not treat the candidate as the resolved entity.
4.3 Score < 0.78 is not a match; include the best candidate and score for transparency.

## 5. Corporate-family expansion
5.1 Affiliates count for conflicts search when ownership or control is greater than or equal to 50%.
5.2 Ultimate parent, controlled subsidiaries and controlled siblings are emitted into the search scope. The engine does not decide whether attribution is legally sufficient; it assembles the family evidence for QRM.

## 6. Search scope
6.1 The register-search step must use the submitted name, normalized name, resolved legal name, controlled aliases and corporate-family names.
6.2 The output memo must state which variants were tried and which registers and date ranges were covered.

## 7. Provenance
7.1 Every resolved entity carries match score, source, citation and rule reference.
7.2 Below-threshold or ambiguous resolution must create a human-review escalation rather than a silent non-match.
