# Role Access Matrix
## 1. Role floor
### 1.1 Delivery analyst
Viewer/member access to collaboration spaces and viewer access to cleared internal knowledge.
### 1.2 Delivery manager
Contributor access to engagement workspaces and member access to channels; no admin.
### 1.3 Engagement coordinator
Contributor access to planning trackers and viewer access to references.
## 2. Permission ceiling
### 2.1 Least privilege
Request the lower of role ceiling and workspace default.
### 2.2 Admin rights excluded
Admin, owner and site-collection rights are never requested by this template.
### 2.3 Distinct ranks; clamp and hold
Permissions rank none < viewer < member < contributor < admin < owner; no two permission types share a rank. The request is min(requested, workspace default, role ceiling). A requested or default permission wider than that is clamped to it and raises `HOLD-PERMISSION-CLAMPED` for engagement manager review; a wider permission is never granted silently. Admin, owner or unrecognised requests request nothing (rule 2.2).
## 3. Staffing slate handoff
### 3.1 Recommendations are not assignments
Scenario 02 names are proposed unless confirmed by roster.
### 3.2 Ineligible candidates excluded
Ineligible or conflicted candidates from Scenario 02 are excluded, using the verdict for the confirmed role (otherwise the most restrictive verdict across roles). A recommendation is proposed only when the slate holds a record for the same candidate (canonical `candidate_id` and name) and the most restrictive verdict across that person's slate records is `eligible`; a blocked, conflicted, ineligible, needs-review, unrecognised or unmatched recommendation is never proposed and raises `HOLD-STAFFING-RECOMMENDATION-NOT-ELIGIBLE` with an escalation to the engagement manager. Independence and conflict reasons stay in the staffing record; only the verdict and rule citation travel.
### 3.3 Needs-review candidates escalate
A confirmed roster member with a `needs_review` Scenario 02 verdict stays on the roster with an escalation to the engagement manager.
### 3.4 Unrecognised verdicts hold
A Scenario 02 verdict that is blank, null or not one of `eligible`, `ineligible`, `conflicted`, `blocked` or `needs_review` is unrecognised: the confirmed roster member stays on the roster flagged for staffing review and the run holds.
## 4. Roster evidence
### 4.1 Confirmed roster controls
The onboarding roster is built from `raw/confirmed-roster.csv`. Only rows with `assignment_status` = `confirmed` are assigned; blank or other values are not.
### 4.2 One joiner per pack
The first joining roster member is the pack subject; additional joiners are escalated for a separate run.
### 4.3 Unknown roles hold
A joiner role absent from section 1 requests no access and raises a hold.
### 4.4 Unknown onboarding status holds
`onboarding_status` must be `active`, `joining`, `mid-engagement joiner` or `new_joiner`. A blank or other value raises a hold and an escalation; the person is not treated as the joiner. The roster must have `person`, `role`, `assignment_status` and `onboarding_status` columns, and rows with more fields than the header stop the run.
