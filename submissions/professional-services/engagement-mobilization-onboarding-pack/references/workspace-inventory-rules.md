# Workspace Inventory Rules
## 1. Inventory scope
### 1.1 Explicit inventory required
Only listed systems/workspaces can appear in the checklist.
### 1.2 Missing is not empty
A missing inventory is a hold; an explicitly empty inventory means no requests.
## 2. Dependency on knowledge clearance
### 2.1 Prior-knowledge dependency
Workspaces marked dependent on prior knowledge inherit knowledge holds or denials.
### 2.2 Restricted workspace denial
Client-confidential or restricted workspaces are denied when wall rules deny the joiner.
## 3. Checklist output
### 3.1 Draft request only
The checklist describes draft requests and never provisions.
### 3.2 Excess requests flagged
Access above role ceiling is `not_requested_exceeds_role`, never added.
