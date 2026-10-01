#!/usr/bin/env python3
import argparse
from safety_text import *
ENGINE="engine:access_checklist"
M={"delivery analyst":{"engagement-sharepoint":"viewer","delivery-planner":"viewer","client-teams-channel":"member","knowledge-repository":"viewer"},"delivery manager":{"engagement-sharepoint":"contributor","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"},"client delivery manager":{"engagement-sharepoint":"contributor","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"},"engagement coordinator":{"engagement-sharepoint":"viewer","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"}}  # role-access-matrix.md #1.1-#1.3
O={"none":0,"viewer":1,"member":2,"contributor":3,"admin":4,"owner":5}  # role-access-matrix.md #2.1-#2.3: every permission has its own rank
NAMES={v:k for k,v in O.items() if k!="owner"}
ADMIN_EXCLUDED=True  # workspace-inventory-rules.md #3.2
WALL_STATUSES={"clear","denied","hold"}  # confidentiality-and-ethical-wall-rules.md #2.2
INVENTORY_COLUMNS=("workspace_id","workspace_type","default_permission","depends_on_knowledge","data_classification")  # workspace-inventory-rules.md #1.3
KNOWN_CLASSIFICATIONS={"client_confidential","confidential","restricted","internal","public"}  # workspace-inventory-rules.md #2.3
def low(v): return (v or "").strip().lower()
def safe(x): return WITHHELD if hits(x) else x  # confidentiality-and-ethical-wall-rules.md #4.3
def pack(p):
    e=p.get("engagement") or {}; s=p.get("scope_summary") or {}; j=p.get("joiner") or {}; kd=p.get("knowledge_digest") or {}; mp=p.get("mobilization_pack") or {}
    hc=len(p.get("holds",[])); pend=sum(i.get("status")=="hold_pending_wall_review" for i in p.get("access_checklist",[]))
    parts=([f"{hc} open hold(s)"] if hc else [])+([f"{pend} workspace(s) pending wall review"] if pend else [])+(["wall status on hold"] if "wall_status_hold" in mp.get("hold_reasons",[]) and not hc else [])
    L=["# Engagement Mobilization & Onboarding Pack","","**DRAFT - for internal review only. Do not send to the client or provision access.**","",f"Pack status: {mp.get('status','on_hold_internal_only')}"+(" - "+"; ".join(parts)+"; resolve before sharing with the joiner." if parts else ""),f"Generated at: {p.get('run_metadata',{}).get('generated_at',p.get('provenance',{}).get('generated_at',''))}",f"Engagement: {e.get('title','')} ({e.get('engagement_id','')})",f"Client: {e.get('client_name','')}",f"Joiner: {j.get('person','')} - {j.get('role','')}","","## Client context and objectives"]+[f"- {x}" for x in s.get("objectives",[])]+["","## SOW scope and exclusions","","### In scope"]+[f"- {x}" for x in s.get("in_scope",[])]+["","### Exclusions"]+[f"- {x}" for x in s.get("exclusions",[])]+["","## Deliverables and key dates"]
    L += [f"- Deliverable: {x}" for x in s.get("deliverables",[])] + [f"- Key date: {x}" for x in s.get("key_dates",[])]
    L += ["","## Prior-knowledge digest",f"Status: {kd.get('status','unknown')}"]
    L += [f"- {i.get('title')} ({i.get('knowledge_id')}) [{i.get('review_status','pending_practice_review')}] - {i.get('summary')} Source: {'; '.join(i.get('citations',[]))}" for i in kd.get("items",[])] or ["- No knowledge items are cleared for this joiner in this run."]
    L += ["","## Team roster"] + [f"- {r.get('person')} - {r.get('role')} - {', '.join(r.get('responsibilities',[]))} - POC: {r.get('point_of_contact')}" for r in p.get("team_roster",[])] + [f"- Proposed, not assigned: {r.get('candidate_name')} for {r.get('role_title')}" for r in p.get("proposed_staffing",[])]
    L += ["","## Access-request checklist"] + ([f"- {i.get('workspace_name')} ({i.get('workspace_id')}): {i.get('status')} - {i.get('requested_permission','none')} - {i.get('reason')}" for i in p.get("access_checklist",[])] or ["- No access is requested in this run; see Escalations and holds."])
    L += ["","## Confidentiality and ethical-wall briefing"] + ([f"- May not access/discuss {i.get('type')}: {i.get('item')} - {i.get('restriction')}" for i in (p.get("wall_decision") or {}).get("may_not_access_discuss",[])] or ["- No wall restriction was found for the joiner, subject to human review of this draft."])
    L += ["","## First-week plan"] + [f"{n}. {x}" for n,x in enumerate(s.get("first_week_focus",[]),1)] + ["","## Escalations and holds"] + [f"- {x}" for x in p.get("escalations",[])] + [f"- HOLD {h.get('hold_id')}: {h.get('reason')} at {h.get('path')} ({h.get('citation')})" for h in p.get("holds",[])]
    return "\n".join(L[:5]+[x if x.startswith(("#","- HOLD ","Status:")) or not x else safe(x) for x in L[5:]])+"\n"
def check_governed(p):
    need(isinstance(p,dict),f"governed input must be a JSON object, got {type(p).__name__}; fail closed")
    if p.get("contract_version")!=CONTRACT_VERSION: raise InputError(f"expected contract {CONTRACT_VERSION} in governed input")
    if not isinstance(p.get("wall_decision"),dict): raise InputError("governed input has no wall_decision object; run wall_check first; fail closed")
    # An unrecognised wall_decision.status is held below rather than rejected (confidentiality-and-ethical-wall-rules.md #2.2).
    check_contract(p,"governed",lenient=("wall_decision.status",))  # confidentiality-and-ethical-wall-rules.md #1.3
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--governed",required=True); ap.add_argument("--workspace-inventory",required=True); ap.add_argument("--out",required=True); ap.add_argument("--pack-out",required=True); ap.add_argument("--generated-at",required=True); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    p=load_json(a.governed); check_governed(p); set_trusted_domains((p.get("engagement") or {}).get("trusted_domains"))
    holds=list(p.get("holds",[])); esc=p.setdefault("escalations",[]); role=low((p.get("joiner") or {}).get("role")); allowed=M.get(role,{}); wall=p["wall_decision"]; denied=set(wall.get("denied_workspace_ids",[])); held=set(wall.get("held_workspace_ids",[])); hidden=set(wall.get("name_withheld_workspace_ids",[])); out=[]
    def add_hold(hid,path,why,cit): holds.append({"hold_id":hid,"path":path,"reason":why,"source":ENGINE,"confidence":.99,"citation":cit})
    wstat=wall.get("status")
    if wstat not in WALL_STATUSES:
        add_hold("HOLD-UNKNOWN-WALL-DECISION","governed.wall_decision.status",f"unrecognised wall_decision status {wstat!r}; treated as hold","confidentiality-and-ethical-wall-rules.md #2.2"); wstat="hold"
    rows=read_csv(a.workspace_inventory,False)
    if rows is None:
        add_hold("HOLD-MISSING-WORKSPACE-INVENTORY",a.workspace_inventory,"missing workspace inventory; no access is requested","workspace-inventory-rules.md #1.2"); rows=[]
    elif missing_columns(rows,INVENTORY_COLUMNS):
        add_hold("HOLD-MALFORMED-WORKSPACE-INVENTORY","raw/workspace-inventory.csv header",f"workspace inventory is missing required column(s): {', '.join(missing_columns(rows,INVENTORY_COLUMNS))}; no access is requested","workspace-inventory-rules.md #1.3"); rows=[]
    else: holds+=scan_rows(rows,"raw/workspace-inventory.csv")
    bad_rows=set(getattr(rows,"malformed",()))
    if not allowed: add_hold("HOLD-ROLE-NOT-IN-MATRIX","scope.joiner.role",f"joiner role {role or '(none)'} is not in the role-access matrix; no access is requested","role-access-matrix.md #4.3")
    for n,r in enumerate(rows,2):
        wid=(r.get("workspace_id") or "").strip(); wt=low(r.get("workspace_type")); req=low(r.get("requested_permission")) or low(r.get("default_permission")); default=low(r.get("default_permission")) or req; dep=depends_on_knowledge(r.get("depends_on_knowledge")); conf=client_confidential(r.get("data_classification")); maxp=allowed.get(wt); status="request"; reason="role matrix allows requested workspace access"; perm=req; cit=f"{r.get('citation') or 'raw/workspace-inventory.csv'}; role-access-matrix.md #2.1; workspace-inventory-rules.md #3.1"
        invalid=[x for x,bad in (("workspace_id blank",not wid),("row has more fields than the header",n in bad_rows),("no requested or default permission",not req),("unrecognised default_permission",default not in O),("unrecognised data_classification",low(r.get("data_classification")) not in KNOWN_CLASSIFICATIONS),("unrecognised depends_on_knowledge",low(r.get("depends_on_knowledge")) not in TRUE_VALUES|FALSE_VALUES)) if bad]
        if wid and wid in denied: status="denied_by_wall"; reason="workspace denied by wall_check"; perm="none"; cit+="; confidentiality-and-ethical-wall-rules.md #2.3"
        elif invalid:
            status="not_requested_invalid_row"; reason="invalid inventory row ("+"; ".join(invalid)+"); nothing requested"; perm="none"; cit+="; workspace-inventory-rules.md #1.3,#2.3"
            add_hold("HOLD-INVALID-WORKSPACE-ROW",f"raw/workspace-inventory.csv row {n}","invalid workspace inventory row: "+"; ".join(invalid),"workspace-inventory-rules.md #1.3,#2.3")
        elif wid in held or (wstat in {"hold","denied"} and (dep or conf)): status="hold_pending_wall_review"; reason="prior-knowledge dependent access held until wall status is clear" if dep else "client-confidential workspace held pending wall review"; perm="none"; cit+="; workspace-inventory-rules.md #2.1"
        elif not maxp: status="not_requested_role_not_allowed"; reason="role matrix does not allow this workspace type"; perm="none"; cit+="; role-access-matrix.md #1"
        elif req not in O or O[req]>=O["admin"]: status="not_requested_exceeds_role"; reason=f"requested {req} exceeds role ceiling {maxp}; admin rights are never requested" if req in O else f"unrecognised requested permission exceeds role ceiling {maxp}"; perm="none"; cit+="; role-access-matrix.md #2.1,#2.2; workspace-inventory-rules.md #3.2"
        elif O[req]>min(O[default],O[maxp]):
            # Request = min(requested, workspace default, role ceiling); anything wider is clamped and held, never granted (#2.3).
            perm=NAMES[min(O[req],O[default],O[maxp])]; reason=f"requested {req} clamped to {perm} (workspace default {default}, role ceiling {maxp}); held for engagement manager review"; cit+="; role-access-matrix.md #2.3"
            add_hold("HOLD-PERMISSION-CLAMPED",f"raw/workspace-inventory.csv row {n}.requested_permission",f"requested {req} is wider than min(workspace default {default}, role ceiling {maxp}); request clamped to {perm}","role-access-matrix.md #2.3")
            if perm=="none": status="not_requested_exceeds_role"
        name=r.get("name") or wid
        if wid in hidden or hits(name) or name==WITHHELD: name=wid or "(blank workspace_id)"
        out.append({"workspace_id":wid,"workspace_name":name,"workspace_type":wt,"status":status,"requested_permission":perm,"reason":reason,"source":ENGINE,"confidence":.96,"citation":cit})
    holds=dedup_holds(holds); pend=sum(i["status"]=="hold_pending_wall_review" for i in out)
    reasons=(["open_holds"] if holds else [])+(["wall_status_hold"] if wstat=="hold" else [])+(["workspaces_pending_wall_review"] if pend else [])  # workspace-inventory-rules.md #3.3
    if pend: esc.append(f"{pend} workspace(s) held pending wall review; the pack stays on hold until Risk/Conflicts resolve the wall decision (workspace-inventory-rules.md #3.3)")
    p["access_checklist"]=out; p["holds"]=holds; p["mobilization_pack"]={"status":"on_hold_internal_only" if reasons else "draft_internal_only","hold_reasons":reasons,"label":"DRAFT - for internal review only. Do not send to the client or provision access.","sections":["client_context","scope","prior_knowledge","team_roster","access_checklist","wall_briefing","first_week_plan"],"source":ENGINE,"confidence":.94,"citation":"workspace-inventory-rules.md #3.1,#3.3; confidentiality-and-ethical-wall-rules.md #3.1"}; p.setdefault("provenance",{}).setdefault("engines",[]).append(f"access_checklist/{VERSION}"); p["provenance"]["generated_at"]=ts; dump_json(a.out,p); write_text(a.pack_out,pack(p))
if __name__=="__main__": guard(main)
