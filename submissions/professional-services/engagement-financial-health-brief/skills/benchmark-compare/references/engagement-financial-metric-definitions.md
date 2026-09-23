# Engagement Financial Metric Definitions
Deterministic rules consumed by health_calc.py and driver_attribute.py. Engines cite these by
section number; constants and formula choices in the engines mirror this document.

## 1. Definition set and comparability
1.1 Every health output carries `metric_definition_set_id`. Cross-engagement or practice benchmark
comparison is allowed only when the engagement, package config and benchmark source use the same
definition set id. If the ids differ, benchmark comparison is refused rather than normalised by the
model.
1.2 The metric definition section used for each indicator is emitted as `definition_section`.

## 2. Core economics indicators
2.1 Realisation percentage = `billed_revenue_to_date / standard_value_of_billed_work_to_date * 100`.
The denominator is the rate-card standard value for billed labour and billed fixed-fee work at the
planned or contracted standard rate, not cost. Credits, write-offs and discounts reduce billed
revenue in the numerator. Unbilled WIP is excluded until billed.
2.2 Utilisation percentage = `chargeable_hours / available_hours * 100`. Available hours are each
person's contracted working hours for the period after subtracting firm holidays, approved leave,
non-chargeable leave and documented part-time schedule reductions. Training, internal practice
meetings, proposals and bench time remain available hours unless the practice's controlled
definition explicitly removes them. Subcontractor delivery hours are chargeable hours only when the
subcontractor is managed as part of the engagement team and the hours are captured in time records.
2.3 Effective rate = `billed_labour_revenue_to_date / chargeable_hours`. Reimbursable expenses,
pass-through taxes and subcontractor invoice markups are excluded from billed labour revenue.
2.4 Margin percentage = `(recognised_revenue_to_date - delivery_cost_to_date) /
recognised_revenue_to_date * 100`. Delivery cost includes employee labour cost, subcontractor
delivery cost and non-reimbursable delivery expenses. Reimbursable client expenses and pass-through
taxes are excluded from both revenue and cost for margin. If recognised revenue is zero, margin is
not evaluated and the engagement is escalated.

## 3. Plan comparison
3.1 Burn versus plan delta percentage = `(actual_delivery_cost_to_date -
planned_delivery_cost_to_date) / planned_delivery_cost_to_date * 100`. Positive values are over
plan. If planned delivery cost to date is zero, burn is not evaluated.
3.2 Plan comparison must use the plan baseline in force for the review period. The engine reports
plan revision and citation so a later reforecast cannot be mistaken for the original commercial
baseline.

## 4. WIP and unbilled exposure
4.1 WIP ageing buckets are invoice-eligible unbilled WIP by oldest age in days: `0-30`, `31-60`,
`61-90`, and `90+`. Negative WIP balances and unapplied credits stay visible but do not offset
positive aged WIP for threshold tests.
4.2 Unbilled exposure = open WIP + eligible unbilled time + eligible reimbursable expenses not yet
invoiced. Unbilled exposure percentage of plan = `unbilled_exposure / planned_revenue_to_date *
100`. WIP collectability reserve applies the configured reserve percentage to each ageing bucket.

## 5. Forecast indicators
5.1 Estimate-to-complete cost = system ETC + milestone slip remediation cost + deferred senior
review cost. System ETC is accepted only as a starting point; slipped milestones and planned senior
review hours not yet booked are added deterministically from the plan and time records.
5.2 Estimate-at-completion cost = `actual_delivery_cost_to_date + estimate_to_complete_cost`.
EAC over plan percentage = `(EAC cost - planned_total_delivery_cost) /
planned_total_delivery_cost * 100`.
5.3 Milestone slip percentage = `slipped_milestones / total_milestones * 100`, counting only
milestones due on or before the review date.

## 6. Driver attribution
6.1 The largest variance is decomposed arithmetically. For EAC cost variance, components are:
`actual_to_plan_variance + system_remaining_variance + milestone_slip_remediation_cost +
deferred_senior_review_cost = EAC cost - planned_total_delivery_cost`.
6.2 WIP collectability risk is decomposed by ageing bucket. The reserve dollars by bucket must sum
to total collectability reserve.
6.3 The model may describe the drivers but never invents a causal driver that is not in the engine
component table.

## 7. Boundary
7.1 The package reports, explains and drafts. It does not adjust WIP, write off balances, change a
rate, reforecast the plan, reallocate budget, invoice the client or update a finance system.
