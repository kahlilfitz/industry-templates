# Effort and Cost Delta Method - Change Order & Scope Control

Deterministic rules consumed by `delta_calc.py`. Engines cite these section numbers; constants in the engine mirror this document.

## 1. Estimate basis
| Rule | Condition | Effect |
|---|---|---|
| 1.1 | Request-level effort estimates are available by role | Use those hours as the estimate basis and preserve the source citation. |
| 1.2 | No estimate exists for a request | Mark the item incomplete and exclude it from the draft change-order total until the delivery lead supplies an estimate. |

## 2. Rate-card application
| Rule | Condition | Effect |
|---|---|---|
| 2.1 | A role appears in the request estimate and the rate card | Multiply hours by the role's hourly rate. |
| 2.2 | A role is missing from the rate card | Escalate; do not substitute a blended rate. |

## 3. Contingency
| Rule | Condition | Effect |
|---|---|---|
| 3.1 | The item is OUT_OF_SCOPE and has complete role estimates | Include it in the draft change-order amount. |
| 3.2 | The item is included in the draft change-order amount | Apply 15% contingency (`CONTINGENCY_PCT`) for coordination, rework and commercial administration. |
| 3.3 | The item is AMBIGUOUS | Show quantified exposure separately. Do not include it in the draft charge total until a human resolves the scope decision. |

## 4. Cumulative drift escalation
| Rule | Condition | Effect |
|---|---|---|
| 4.1 | Cumulative no-charge or unapproved out-of-scope effort exceeds the greater of $10,000 (`DRIFT_ESCALATION_MIN_AMOUNT`) or 2% of contract value (`DRIFT_ESCALATION_THRESHOLD_PCT`) | Escalate to the engagement partner / commercial manager. |
| 4.2 | Prior accepted accommodations have internal cost but no billed change order | Count them toward cumulative margin erosion. |
| 4.3 | IN_SCOPE items are covered by the SOW | Show zero change-order amount and exclude them from drift totals. |
