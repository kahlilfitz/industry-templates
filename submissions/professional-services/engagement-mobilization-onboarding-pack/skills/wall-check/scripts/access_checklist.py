#!/usr/bin/env python3
import argparse
from safety_text import *
ENGINE="engine:access_checklist"
M={"delivery analyst":{"engagement-sharepoint":"viewer","delivery-planner":"viewer","client-teams-channel":"member","knowledge-repository":"viewer"},"delivery manager":{"engagement-sharepoint":"contributor","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"},"client delivery manager":{"engagement-sharepoint":"contributor","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"},"engagement coordinator":{"engagement-sharepoint":"viewer","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"}}  # role-access-matrix.md #1.1-#1.3
O={"none":0,"viewer":1,"member":1,"contributor":2,"admin":3,"owner":3}  # role-access-matrix.md #2.1,#2.2
ADMIN_EXCLUDED=True  # workspace-inventory-rules.md #3.2
def low(v): return (v or "").strip().lower()
WITHHELD="[withheld - source text held for embedded-instruction review]"  # confidentiality-and-ethical-wall-rules.md #4.1
def safe(x): return WITHHELD if hits(x) else x
def pack(p):
    e=p.get("engagement",{}); s=p.get("scope_summary",{}); j=p.get("joiner",{}); kd=p.get("knowledge_digest",{})
    hc=len(p.get("holds",[])); L=["# Engagement Mobilization & Onboarding Pack","","**DRAFT - for internal review only. Do not send to the client or provision access.**","",f"Pack status: {p.get('mobilization_pack',{}).get('status','draft_internal_only')}"+(f" - {hc} open hold(s); resolve before sharing with the joiner." if hc else ""),f"Generated at: {p.get('run_metadata',{}).get('generated_at',p.get('provenance',{}).get('generated_at',''))}",f"Engagement: {e.get('title','')} ({e.get('engagement_id','')})",f"Client: {e.get('client_name','')}",f"Joiner: {j.get('person','')} - {j.get('role','')}","","## Client context and objectives"]+[f"- {x}" for x in s.get("objectives",[])]+["","## SOW scope and exclusions","","### In scope"]+[f"- {x}" for x in s.get("in_scope",[])]+["","### Exclusions"]+[f"- {x}" for x in s.get("exclusions",[])]+["","## Deliverables and key dates"]
    L += [f"- Deliverable: {x}" for x in s.get("deliverables",[])] + [f"- Key date: {x}" for x in s.get("key_dates",[])]
    L += ["","## Prior-knowledge digest",f"Status: {kd.get('status','unknown')}"]
    L += [f"- {i.get('title')} ({i.get('knowledge_id')}) [{i.get('review_status','pending_practice_review')}] - {i.get('summary')} Source: {'; '.join(i.get('citations',[]))}" for i in kd.get("items",[])] or ["- No knowledge items are cleared for this joiner in this run."]
    L += ["","## Team roster"] + [f"- {r.get('person')} - {r.get('role')} - {', '.join(r.get('responsibilities',[]))} - POC: {r.get('point_of_contact')}" for r in p.get("team_roster",[])] + [f"- Proposed, not assigned: {r.get('candidate_name')} for {r.get('role_title')}" for r in p.get("proposed_staffing",[])]
    L += ["","## Access-request checklist"] + [f"- {i.get('workspace_name')} ({i.get('workspace_id')}): {i.get('status')} - {i.get('requested_permission','none')} - {i.get('reason')}" for i in p.get("access_checklist",[])]
    L += ["","## Confidentiality and ethical-wall briefing"] + ([f"- May not access/discuss {i.get('type')}: {i.get('item')} - {i.get('restriction')}" for i in p.get("wall_decision",{}).get("may_not_access_discuss",[])] or ["- No wall restriction was found for the joiner, subject to human review of this draft."])
    L += ["","## First-week plan"] + [f"{n}. {x}" for n,x in enumerate(s.get("first_week_focus",[]),1)] + ["","## Escalations and holds"] + [f"- {x}" for x in p.get("escalations",[])] + [f"- HOLD {h.get('hold_id')}: {h.get('reason')} at {h.get('path')} ({h.get('citation')})" for h in p.get("holds",[])]
    return "\n".join(L[:5]+[x if x.startswith(("#","- HOLD ","Status:")) or not x else safe(x) for x in L[5:]])+"\n"
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--governed",required=True); ap.add_argument("--workspace-inventory",required=True); ap.add_argument("--out",required=True); ap.add_argument("--pack-out",required=True); ap.add_argument("--generated-at",required=True); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    p=load_json(a.governed)
    if p.get("contract_version")!=CONTRACT_VERSION: raise InputError(f"expected contract {CONTRACT_VERSION} in governed input")
    rows=read_csv(a.workspace_inventory); holds=list(p.get("holds",[]))+scan_rows(rows,"raw/workspace-inventory.csv"); role=low((p.get("joiner") or {}).get("role")); allowed=M.get(role,{}); wall=p.get("wall_decision",{}); denied=set(wall.get("denied_workspace_ids",[])); held=set(wall.get("held_workspace_ids",[])); out=[]
    if not allowed: holds.append({"hold_id":"HOLD-ROLE-NOT-IN-MATRIX","path":"scope.joiner.role","reason":f"joiner role {role or '(none)'} is not in the role-access matrix; no access is requested","source":ENGINE,"confidence":.99,"citation":"role-access-matrix.md #4.3"})
    for r in rows:
        wid=r.get("workspace_id"); wt=low(r.get("workspace_type")); req=low(r.get("requested_permission")) or low(r.get("default_permission")) or "viewer"; default=low(r.get("default_permission")) or req; dep=low(r.get("depends_on_knowledge")) in {"true","yes","1"}; maxp=allowed.get(wt); status="request"; reason="role matrix allows requested workspace access"; perm=req; cit=f"{r.get('citation') or 'raw/workspace-inventory.csv'}; role-access-matrix.md #2.1; workspace-inventory-rules.md #3.1"
        if wid in denied: status="denied_by_wall"; reason="workspace denied by wall_check"; perm="none"; cit+="; confidentiality-and-ethical-wall-rules.md #2.3"
        elif wid in held or (wall.get("status") in {"hold","denied"} and dep): status="hold_pending_wall_review"; reason="prior-knowledge dependent access held until wall status is clear" if dep else "client-confidential workspace held pending wall review"; perm="none"; cit+="; workspace-inventory-rules.md #2.1"
        elif not maxp: status="not_requested_role_not_allowed"; reason="role matrix does not allow this workspace type"; perm="none"; cit+="; role-access-matrix.md #1"
        elif O.get(req,99)>O.get(maxp,0) or O.get(req,0)>=O["admin"]: status="not_requested_exceeds_role"; reason=f"requested {req} exceeds role ceiling {maxp}"; perm="none"; cit+="; role-access-matrix.md #2.1,#2.2; workspace-inventory-rules.md #3.2"
        elif O.get(default,0)<O.get(req,0): perm=default; reason="workspace default is narrower than requested permission"
        out.append({"workspace_id":wid,"workspace_name":r.get("name") or wid,"workspace_type":wt,"status":status,"requested_permission":perm,"reason":reason,"source":ENGINE,"confidence":.96,"citation":cit})
    seen=set(); holds=[h for h in holds if (h.get("hold_id"),h.get("path"),h.get("reason")) not in seen and not seen.add((h.get("hold_id"),h.get("path"),h.get("reason")))]
    p["access_checklist"]=out; p["holds"]=holds; p["mobilization_pack"]={"status":"on_hold_internal_only" if holds else "draft_internal_only","label":"DRAFT - for internal review only. Do not send to the client or provision access.","sections":["client_context","scope","prior_knowledge","team_roster","access_checklist","wall_briefing","first_week_plan"],"source":ENGINE,"confidence":.94,"citation":"workspace-inventory-rules.md #3.1; confidentiality-and-ethical-wall-rules.md #3.1"}; p.setdefault("provenance",{}).setdefault("engines",[]).append(f"access_checklist/{VERSION}"); p["provenance"]["generated_at"]=ts; dump_json(a.out,p); write_text(a.pack_out,pack(p))
if __name__=="__main__": guard(main)
