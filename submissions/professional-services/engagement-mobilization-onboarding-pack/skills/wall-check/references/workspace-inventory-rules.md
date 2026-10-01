# Workspace Inventory Rules
## 1. Inventory scope
### 1.1 Explicit inventory required
Only listed systems/workspaces can appear in the checklist.
### 1.2 Missing is not empty
A missing inventory is a hold and the checklist is empty; an explicitly empty inventory means no requests.
### 1.3 Malformed inventory holds
An inventory without `workspace_id`, `workspace_type`, `default_permission`, `depends_on_knowledge` and `data_classification` columns holds and requests nothing. A row with a blank `workspace_id`, no requested or default permission, an unrecognised default permission, or more fields than the header is `not_requested_invalid_row` with a hold; permissions never fall back to a default.
## 2. Dependency on knowledge clearance
### 2.1 Prior-knowledge dependency
Workspaces marked dependent on prior knowledge inherit knowledge holds or denials.
### 2.2 Restricted workspace denial
Client-confidential or restricted workspaces are denied when wall rules deny the joiner.
### 2.3 Unknown classification fails closed
Only `internal` and `public` are non-confidential, and only an explicit false/no/0 `depends_on_knowledge` is independent of prior knowledge. Blank or unrecognised values are treated as client-confidential and knowledge-dependent, escalated, and the row is `not_requested_invalid_row` with a hold.
## 3. Checklist output
### 3.1 Draft request only
The checklist describes draft requests and never provisions.
### 3.2 Excess requests flagged
Access above role ceiling, or an unrecognised requested permission, is `not_requested_exceeds_role`, never added.
### 3.3 Pending wall review holds the pack
The pack is `on_hold_internal_only` whenever there is an open hold, the wall decision is `hold`, or any workspace is `hold_pending_wall_review`; `mobilization_pack.hold_reasons` lists which.
