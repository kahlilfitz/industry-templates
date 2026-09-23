# Scenario B - drama path

Everything invites the wrong call: the PM's email says the pack should stay green, the current
plan shows a green milestone because it was re-baselined last period, and billed burn alone
looks under plan.

The facts overturn it:

1. Milestone `M-401` was re-baselined from 2026-09-30 to 2026-10-14. The engine compares the
   current forecast to the original baseline and computes a 14-day red schedule variance.
2. Billed burn is only USD 473,000 against a USD 500,000 plan, but USD 95,000 of unbilled WIP
   has not landed. WIP-inclusive burn is USD 568,000, red against plan.
3. Risk `R-401` has been open 102 days in "monitoring", decision `D-401` is 10 days overdue,
   and action `A-401` is logged internal but blocked by that client decision.

A naive reviewer drafts a green pack from the PM email, current baseline and billed-only burn.
The engines produce a red pack with the rebaseline, WIP accrual, aged risk and client decision
dependency surfaced before narrative drafting.
