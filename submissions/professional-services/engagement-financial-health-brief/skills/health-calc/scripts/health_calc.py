#!/usr/bin/env python3
"""health_calc - deterministic engagement financial health engine.

Reads normalized engagement financials, WIP, time, plan, rate-card and benchmark JSON.
Writes ps.engagement-financial-health-brief.v1 JSON. No network, no model calls, no
side effects beyond the requested output file.

Constants mirror references/engagement-financial-metric-definitions.md by section number.
"""
import argparse
import json
import sys

ENGINE = "engine:health_calc"
CONTRACT_VERSION = "ps.engagement-financial-health-brief.v1"
DEFINITION_SET_RULE = "engagement-financial-metric-definitions.md #1.1"  # definition comparability
REALISATION_RULE = "engagement-financial-metric-definitions.md #2.1"
UTILISATION_RULE = "engagement-financial-metric-definitions.md #2.2"
EFFECTIVE_RATE_RULE = "engagement-financial-metric-definitions.md #2.3"
MARGIN_RULE = "engagement-financial-metric-definitions.md #2.4"
BURN_RULE = "engagement-financial-metric-definitions.md #3.1"
WIP_AGEING_RULE = "engagement-financial-metric-definitions.md #4.1"
UNBILLED_RULE = "engagement-financial-metric-definitions.md #4.2"
ETC_RULE = "engagement-financial-metric-definitions.md #5.1"
EAC_RULE = "engagement-financial-metric-definitions.md #5.2"
MILESTONE_RULE = "engagement-financial-metric-definitions.md #5.3"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def money(value):
    return round(float(value) + 0.0000001, 2)


def pct(numerator, denominator):
    if denominator == 0:
        return None
    return round(100.0 * numerator / denominator, 2)


def status_min(value, rule):
    if value is None:
        return "not_evaluated"
    if value >= rule["green_min"]:
        return "green"
    if value >= rule["amber_min"]:
        return "amber"
    return "red"


def status_abs_max(value, rule):
    if value is None:
        return "not_evaluated"
    if abs(value) <= rule["green_abs_max"]:
        return "green"
    if abs(value) <= rule["amber_abs_max"]:
        return "amber"
    return "red"


def status_max(value, rule):
    if value is None:
        return "not_evaluated"
    if value <= rule["green_max"]:
        return "green"
    if value <= rule["amber_max"]:
        return "amber"
    return "red"


def score_for(status):
    return {"green": 100.0, "amber": 65.0, "red": 25.0, "not_evaluated": 0.0}[status]


def role_costs(rate_card):
    return {r["role"]: float(r["cost_rate"]) for r in rate_card.get("rates", [])}


def sum_hours(timesheets, field):
    return sum(float(r.get(field, 0.0)) for r in timesheets.get("rows", []))


def actual_senior_review_hours(timesheets):
    by_role = {}
    for row in timesheets.get("rows", []):
        if row.get("work_type") == "senior_review":
            by_role[row["role"]] = by_role.get(row["role"], 0.0) + float(row.get("chargeable_hours", 0.0))
    return by_role


def wip_bucket(age_days):
    if age_days <= 30:
        return "0-30"
    if age_days <= 60:
        return "31-60"
    if age_days <= 90:
        return "61-90"
    return "90+"


def indicator(name, value, unit, status, threshold, section, definition_set_id, citation, plan_value=None):
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "status": status,
        "plan_value": plan_value,
        "threshold": threshold,
        "definition_section": section,
        "metric_definition_set_id": definition_set_id,
        "confidence": 0.98,
        "source": ENGINE,
        "citation": citation
    }


def main():
    parser = argparse.ArgumentParser(description="Compute fixed-definition engagement financial health indicators.")
    parser.add_argument("--engagement", required=True, help="Engagement JSON")
    parser.add_argument("--financials", required=True, help="Financial actuals JSON")
    parser.add_argument("--wip", required=True, help="WIP ageing JSON")
    parser.add_argument("--timesheets", required=True, help="Timesheet summary JSON")
    parser.add_argument("--plan", required=True, help="Plan and budget JSON")
    parser.add_argument("--rate-card", required=True, help="Rate-card JSON")
    parser.add_argument("--benchmarks", default=None, help="Practice benchmark JSON")
    parser.add_argument("--config", required=True, help="config/thresholds.json")
    parser.add_argument("--out", required=True, help="Output health.json path")
    args = parser.parse_args()

    engagement = load(args.engagement)
    financials = load(args.financials)
    wip = load(args.wip)
    timesheets = load(args.timesheets)
    plan = load(args.plan)
    rate_card = load(args.rate_card)
    benchmarks = load(args.benchmarks) if args.benchmarks else None
    config = load(args.config)

    for name, payload in [("engagement", engagement), ("financials", financials), ("wip", wip),
                          ("timesheets", timesheets), ("plan", plan), ("rate_card", rate_card)]:
        assert payload["contract_version"] == CONTRACT_VERSION, f"wrong contract version in {name}"

    definition_set_id = engagement["engagement"]["metric_definition_set_id"]
    config_definition_set_id = config["metric_definition_set"]["id"]
    escalations = []
    if definition_set_id != config_definition_set_id:
        escalations.append(
            f"Engagement definition set {definition_set_id} differs from config {config_definition_set_id}; "
            f"benchmark comparison refused ({DEFINITION_SET_RULE})"
        )

    fin = financials["financials"]
    plan_data = plan["plan"]
    thresholds = config["thresholds"]
    weights = config["weights"]
    costs = role_costs(rate_card["rate_card"])

    chargeable_hours = sum_hours(timesheets["timesheets"], "chargeable_hours")
    available_hours = sum_hours(timesheets["timesheets"], "available_hours")
    realisation = pct(fin["billed_revenue_to_date"], fin["standard_value_of_billed_work_to_date"])
    utilisation = pct(chargeable_hours, available_hours)
    effective_rate = money(fin["billed_labour_revenue_to_date"] / chargeable_hours) if chargeable_hours else None
    margin = pct(fin["recognised_revenue_to_date"] - fin["delivery_cost_to_date"], fin["recognised_revenue_to_date"])
    burn_delta = pct(fin["delivery_cost_to_date"] - plan_data["planned_delivery_cost_to_date"], plan_data["planned_delivery_cost_to_date"])

    buckets = {name: {"bucket": name, "amount": 0.0, "positive_amount_for_threshold": 0.0, "record_ids": []}
               for name in ["0-30", "31-60", "61-90", "90+"]}
    for row in wip["wip_records"]:
        bucket = wip_bucket(int(row["age_days"]))
        amount = float(row["amount"])
        buckets[bucket]["amount"] += amount
        if amount > 0:
            buckets[bucket]["positive_amount_for_threshold"] += amount
        buckets[bucket]["record_ids"].append(row["record_id"])
    for bucket in buckets.values():
        bucket["amount"] = money(bucket["amount"])
        bucket["positive_amount_for_threshold"] = money(bucket["positive_amount_for_threshold"])

    total_positive_wip = money(sum(b["positive_amount_for_threshold"] for b in buckets.values()))
    over_90 = buckets["90+"]["positive_amount_for_threshold"]
    over_90_pct = pct(over_90, total_positive_wip) or 0.0
    reserve_by_bucket = []
    reserve_total = 0.0
    for name in ["0-30", "31-60", "61-90", "90+"]:
        reserve_pct = float(config["wip_collectability_reserve_pct"][name])
        reserve_amount = money(buckets[name]["positive_amount_for_threshold"] * reserve_pct / 100.0)
        reserve_total += reserve_amount
        reserve_by_bucket.append({
            "bucket": name,
            "amount": buckets[name]["positive_amount_for_threshold"],
            "reserve_pct": reserve_pct,
            "reserve_amount": reserve_amount,
            "definition_section": UNBILLED_RULE,
            "source": ENGINE,
            "citation": wip["wip_report"]["citation"]
        })
    reserve_total = money(reserve_total)

    unbilled_exposure = money(total_positive_wip + fin.get("eligible_unbilled_time_amount", 0.0) +
                              fin.get("eligible_unbilled_expense_amount", 0.0))
    unbilled_exposure_pct = pct(unbilled_exposure, plan_data["planned_revenue_to_date"])

    actual_review = actual_senior_review_hours(timesheets["timesheets"])
    deferred_senior_review_cost = 0.0
    deferred_detail = []
    for role, planned_hours in plan_data.get("senior_review_plan_to_date", {}).items():
        missing = max(0.0, float(planned_hours) - actual_review.get(role, 0.0))
        cost = money(missing * costs.get(role, 0.0))
        if missing:
            deferred_detail.append({"role": role, "missing_hours": missing, "cost": cost})
        deferred_senior_review_cost += cost
    deferred_senior_review_cost = money(deferred_senior_review_cost)

    slipped = 0
    due = 0
    milestone_slip_cost = 0.0
    slipped_milestones = []
    for milestone in plan_data.get("milestones", []):
        if milestone.get("due_by_review"):
            due += 1
            if milestone.get("status") == "slipped":
                slipped += 1
                cost = 0.0
                for role, hours in milestone.get("remediation_hours", {}).items():
                    cost += float(hours) * costs.get(role, 0.0)
                cost = money(cost)
                milestone_slip_cost += cost
                slipped_milestones.append({"milestone_id": milestone["milestone_id"], "name": milestone["name"], "cost": cost})
    milestone_slip_cost = money(milestone_slip_cost)
    milestone_slip_pct = pct(slipped, due) if due else None

    etc_cost = money(plan_data["system_etc_cost"] + milestone_slip_cost + deferred_senior_review_cost)
    eac_cost = money(fin["delivery_cost_to_date"] + etc_cost)
    eac_variance = money(eac_cost - plan_data["planned_total_delivery_cost"])
    eac_over_plan_pct = pct(eac_variance, plan_data["planned_total_delivery_cost"])

    citation = f"{financials['financials']['citation']}; {timesheets['timesheets']['citation']}; {plan_data['citation']}"
    indicators = [
        indicator("realisation_pct", realisation, "%", status_min(realisation, thresholds["realisation_pct"]),
                  thresholds["realisation_pct"], REALISATION_RULE, definition_set_id, citation),
        indicator("utilisation_pct", utilisation, "%", status_min(utilisation, thresholds["utilisation_pct"]),
                  thresholds["utilisation_pct"], UTILISATION_RULE, definition_set_id, timesheets["timesheets"]["citation"]),
        indicator("effective_rate", effective_rate, "currency/hour", "green" if effective_rate is not None else "not_evaluated",
                  {}, EFFECTIVE_RATE_RULE, definition_set_id, citation),
        indicator("margin_pct", margin, "%", status_min(margin, thresholds["margin_pct"]),
                  thresholds["margin_pct"], MARGIN_RULE, definition_set_id, citation, plan_data.get("planned_margin_pct")),
        indicator("burn_vs_plan_delta_pct", burn_delta, "%", status_abs_max(burn_delta, thresholds["burn_vs_plan_delta_pct"]),
                  thresholds["burn_vs_plan_delta_pct"], BURN_RULE, definition_set_id, citation, 0.0),
        indicator("wip_over_90_pct", over_90_pct, "%", status_max(over_90_pct, thresholds["wip_over_90_pct"]),
                  thresholds["wip_over_90_pct"], WIP_AGEING_RULE, definition_set_id, wip["wip_report"]["citation"]),
        indicator("unbilled_exposure_pct_of_plan", unbilled_exposure_pct, "%",
                  status_max(unbilled_exposure_pct, thresholds["unbilled_exposure_pct_of_plan"]),
                  thresholds["unbilled_exposure_pct_of_plan"], UNBILLED_RULE, definition_set_id, wip["wip_report"]["citation"]),
        indicator("eac_over_plan_pct", eac_over_plan_pct, "%", status_max(eac_over_plan_pct, thresholds["eac_over_plan_pct"]),
                  thresholds["eac_over_plan_pct"], EAC_RULE, definition_set_id, citation, 0.0),
        indicator("milestone_slip_pct", milestone_slip_pct, "%", status_max(milestone_slip_pct, thresholds["milestone_slip_pct"]),
                  thresholds["milestone_slip_pct"], MILESTONE_RULE, definition_set_id, plan_data["citation"])
    ]

    early_flags = []
    for item in indicators:
        if item["status"] in {"amber", "red"}:
            early_flags.append(f"{item['name']} {item['value']}{item['unit']} is {item['status']} under {item['definition_section']}")
    if status_max(over_90_pct, thresholds["wip_over_90_pct"]) in {"amber", "red"}:
        early_flags.append(f"WIP collectability reserve is ${reserve_total:,.2f} under {UNBILLED_RULE}")

    weighted_score = 0.0
    total_weight = 0.0
    for item in indicators:
        if item["name"] in weights:
            weight = float(weights[item["name"]])
            weighted_score += score_for(item["status"]) * weight
            total_weight += weight
    composite_score = round(weighted_score / total_weight, 1) if total_weight else 0.0
    composite_cfg = config["composite_status"]
    if composite_score >= composite_cfg["green_min_score"]:
        overall_status = "green"
    elif composite_score >= composite_cfg["amber_min_score"]:
        overall_status = "amber"
    else:
        overall_status = "red"

    benchmark_block = {
        "status": "refused",
        "reason": "No benchmark file supplied; single-engagement health only.",
        "definition_set_match": False,
        "benchmark_definition_set_id": "",
        "comparisons": [],
        "source": ENGINE,
        "citation": DEFINITION_SET_RULE,
        "confidence": 0.95
    }
    if benchmarks:
        benchmark_set = benchmarks["benchmarks"]["metric_definition_set_id"]
        match = benchmark_set == definition_set_id == config_definition_set_id
        benchmark_block["benchmark_definition_set_id"] = benchmark_set
        benchmark_block["definition_set_match"] = match
        benchmark_block["citation"] = benchmarks["benchmarks"]["citation"] + "; " + DEFINITION_SET_RULE
        if not match:
            benchmark_block["reason"] = (
                f"Benchmark definition set {benchmark_set} does not match engagement/config definition set "
                f"{definition_set_id}; comparison refused to avoid misleading cross-engagement metrics."
            )
            escalations.append(benchmark_block["reason"])
        else:
            benchmark_block["status"] = "compared"
            benchmark_block["reason"] = "Benchmark definition set matches engagement and config."
            benchmark_block["comparisons"] = []
            by_name = {i["name"]: i for i in indicators}
            for name, median in benchmarks["benchmarks"].get("median_values", {}).items():
                if name in by_name and by_name[name]["value"] is not None:
                    benchmark_block["comparisons"].append({
                        "name": name,
                        "engagement_value": by_name[name]["value"],
                        "practice_median": median,
                        "delta": round(by_name[name]["value"] - float(median), 2),
                        "definition_section": by_name[name]["definition_section"],
                        "source": ENGINE,
                        "citation": benchmarks["benchmarks"]["citation"]
                    })

    actual_to_plan_variance = money(fin["delivery_cost_to_date"] - plan_data["planned_delivery_cost_to_date"])
    system_remaining_variance = money(plan_data["system_etc_cost"] - plan_data["planned_remaining_delivery_cost"])

    payload = {
        "contract_version": CONTRACT_VERSION,
        "engagement": engagement["engagement"],
        "plan": plan_data,
        "indicators": indicators,
        "wip_ageing": {
            "buckets": [buckets[name] for name in ["0-30", "31-60", "61-90", "90+"]],
            "total_wip": total_positive_wip,
            "over_90_amount": over_90,
            "over_90_pct": over_90_pct,
            "collectability_reserve": reserve_total,
            "reserve_by_bucket": reserve_by_bucket,
            "definition_section": WIP_AGEING_RULE + "; " + UNBILLED_RULE,
            "source": ENGINE,
            "citation": wip["wip_report"]["citation"],
            "confidence": 0.98
        },
        "forecast": {
            "etc_cost": etc_cost,
            "eac_cost": eac_cost,
            "eac_variance_amount": eac_variance,
            "eac_over_plan_pct": eac_over_plan_pct,
            "system_etc_cost": plan_data["system_etc_cost"],
            "milestone_slip_remediation_cost": milestone_slip_cost,
            "deferred_senior_review_cost": deferred_senior_review_cost,
            "slipped_milestones": slipped_milestones,
            "deferred_senior_review_detail": deferred_detail,
            "definition_section": ETC_RULE + "; " + EAC_RULE,
            "source": ENGINE,
            "citation": plan_data["citation"] + "; " + rate_card["rate_card"]["citation"],
            "confidence": 0.97
        },
        "health": {
            "composite_score": composite_score,
            "overall_status": overall_status,
            "early_warning_flags": early_flags,
            "source": ENGINE,
            "citation": "config/thresholds.json; " + DEFINITION_SET_RULE,
            "confidence": 0.97
        },
        "benchmark_comparison": benchmark_block,
        "driver_basis": {
            "eac_components": [
                {"name": "actual_to_plan_variance", "amount": actual_to_plan_variance, "citation": BURN_RULE},
                {"name": "system_remaining_variance", "amount": system_remaining_variance, "citation": ETC_RULE},
                {"name": "milestone_slip_remediation_cost", "amount": milestone_slip_cost, "citation": ETC_RULE + "; " + MILESTONE_RULE},
                {"name": "deferred_senior_review_cost", "amount": deferred_senior_review_cost, "citation": ETC_RULE}
            ],
            "wip_reserve_components": reserve_by_bucket
        },
        "escalations": escalations,
        "provenance": {
            "engines": ["health_calc/1.0"],
            "generated_at": engagement.get("generated_at", "2026-09-23T00:00:00Z"),
            "demo_scenario": engagement.get("demo_scenario", "")
        }
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(
        f"health_calc: {len(indicators)} indicators, status={overall_status}, "
        f"benchmark={benchmark_block['status']}, flags={len(early_flags)} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
