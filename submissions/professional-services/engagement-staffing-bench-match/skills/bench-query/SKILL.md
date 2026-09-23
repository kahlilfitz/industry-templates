---
name: bench-query
description: Normalizes the bench roster, skills taxonomy, availability, utilisation, location, language and rate data before fit-score. Use when the user says "check the bench", "who is available?", "pull the roster", "include rates", or after role-intake.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Resourcing
---
# Bench Query
## Purpose
Turn bench exports and profile data into `bench_candidates[]` with the fields the deterministic engines need.
## When to use
After `role-intake`, before `fit-score`, for every staffing slate.
## Inputs
- Resource management system roster or bench CSV.
- HR profile data for skills, certifications, seniority, location and languages.
- Availability calendar, approved leave and soft-booked pursuits.
- Rate card or candidate billing-rate export.
## Steps
1. Normalise candidate IDs, names, seniority, skills, certifications, industry experience, location, languages and rate.
2. Carry current allocation, approved leave blocks and soft bookings exactly as records, with citations.
3. Preserve provenance: every candidate row requires `source`, `confidence` and `citation`.
4. Hand off to `fit-score`.
## Output
`bench.json` or an equivalent contract payload containing `bench_candidates[]`.
## Grounding requirements
Each candidate's availability, utilisation, rate and profile fields cite the roster, calendar or profile record used.
## Constraints
- Do not calculate fit score, effective capacity, utilisation after staffing, ranking or eligibility.
- Do not suppress a candidate because they look conflicted; the Govern step decides from cited constraints.
## Escalation / uncertainty
Duplicate candidate IDs, stale availability, missing rate or unclear seniority should be flagged in `escalations[]`; do not smooth over the record.
