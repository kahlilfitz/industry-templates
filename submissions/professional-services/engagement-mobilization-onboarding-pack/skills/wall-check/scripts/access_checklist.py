#!/usr/bin/env python3
import argparse, copy
from safety_text import *
from wall_check import govern
ENGINE="engine:access_checklist"
M={"delivery analyst":{"engagement-sharepoint":"viewer","delivery-planner":"viewer","client-teams-channel":"member","knowledge-repository":"viewer"},"delivery manager":{"engagement-sharepoint":"contributor","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"},"client delivery manager":{"engagement-sharepoint":"contributor","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"},"engagement coordinator":{"engagement-sharepoint":"viewer","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"}}  # role-access-matrix.md #1.1-#1.3
O={"none":0,"viewer":1,"member":2,"contributor":3,"admin":4,"owner":5}  # role-access-matrix.md #2.1-#2.3: every permission has its own rank
NAMES={v:k for k,v in O.items() if k!="owner"}
ADMIN_EXCLUDED=True  # workspace-inventory-rules.md #3.2
WALL_STATUSES={"clear","denied","hold"}  # confidentiality-and-ethical-wall-rules.md #2.2
INVENTORY_COLUMNS=("workspace_id","workspace_type","default_permission","depends_on_knowledge","data_classification")  # workspace-inventory-rules.md #1.3
KNOWN_CLASSIFICATIONS={"client_confidential","confidential","restricted","internal","public"}  # workspace-inventory-rules.md #2.3
def low(v): return canon_text(v)  # enums and roles: the one canonical comparison form (confidentiality-and-ethical-wall-rules.md #1.3)
def cset(xs): return {canon_id(x) for x in xs or []}  # workspace IDs, types and classifications compare canonically (#1.3)
def safe(x): return WITHHELD if hits(x) else x  # confidentiality-and-ethical-wall-rules.md #4.3
def strs(xs): return [x for x in (xs or []) if isinstance(x,str)]  # contract-valid arrays render without a TypeError (#1.3)
DECISION_COLUMNS=("workspace_id","workspace_type","default_permission","requested_permission","depends_on_knowledge","data_classification")  # workspace-inventory-rules.md #1.3
def pack(p):
    e=p.get("engagement") or {}; s=p.get("scope_summary") or {}; j=p.get("joiner") or {}; kd=p.get("knowledge_digest") or {}; mp=p.get("mobilization_pack") or {}
    hc=len(p.get("holds",[])); pend=sum(i.get("status")=="hold_pending_wall_review" for i in p.get("access_checklist",[]))
    parts=([f"{hc} open hold(s)"] if hc else [])+([f"{pend} workspace(s) pending wall review"] if pend else [])+(["wall status on hold"] if "wall_status_hold" in mp.get("hold_reasons",[]) and not hc else [])
    L=["# Engagement Mobilization & Onboarding Pack","","**DRAFT - for internal review only. Do not send to the client or provision access.**","",f"Pack status: {mp.get('status','on_hold_internal_only')}"+(" - "+"; ".join(parts)+"; resolve before sharing with the joiner." if parts else ""),f"Generated at: {p.get('run_metadata',{}).get('generated_at',p.get('provenance',{}).get('generated_at',''))}",f"Engagement: {e.get('title','')} ({e.get('engagement_id','')})",f"Client: {e.get('client_name','')}",f"Joiner: {j.get('person','')} - {j.get('role','')}","","## Client context and objectives"]+[f"- {x}" for x in s.get("objectives",[])]+["","## SOW scope and exclusions","","### In scope"]+[f"- {x}" for x in s.get("in_scope",[])]+["","### Exclusions"]+[f"- {x}" for x in s.get("exclusions",[])]+["","## Deliverables and key dates"]
    L += [f"- Deliverable: {x}" for x in s.get("deliverables",[])] + [f"- Key date: {x}" for x in s.get("key_dates",[])]
    L += ["","## Prior-knowledge digest",f"Status: {kd.get('status','unknown')}"]
    L += [f"- {i.get('title')} ({i.get('knowledge_id')}) [{i.get('review_status','pending_practice_review')}] - {i.get('summary')} Source: {'; '.join(strs(i.get('citations')))}" for i in kd.get("items",[])] or ["- No knowledge items are cleared for this joiner in this run."]
    L += ["","## Team roster"] + [f"- {r.get('person')} - {r.get('role')} - {', '.join(strs(r.get('responsibilities')))} - POC: {r.get('point_of_contact')}" for r in p.get("team_roster",[])] + [f"- Proposed, not assigned: {r.get('candidate_name')} for {r.get('role_title')}" for r in p.get("proposed_staffing",[])]
    L += ["","## Access-request checklist"] + ([f"- {i.get('workspace_name')} ({i.get('workspace_id')}): {i.get('status')} - {i.get('requested_permission','none')} - {i.get('reason')}" for i in p.get("access_checklist",[])] or ["- No access is requested in this run; see Escalations and holds."])
    L += ["","## Confidentiality and ethical-wall briefing"] + ([f"- May not access/discuss {i.get('type')}: {i.get('item')} - {i.get('restriction')}" for i in (p.get("wall_decision") or {}).get("may_not_access_discuss",[])] or ["- No wall restriction was found for the joiner, subject to human review of this draft."])
    L += ["","## First-week plan"] + [f"{n}. {x}" for n,x in enumerate(s.get("first_week_focus",[]),1)] + ["","## Escalations and holds"] + [f"- {x}" for x in p.get("escalations",[])] + [f"- HOLD {h.get('hold_id')}: {h.get('reason')} at {h.get('path')} ({h.get('citation')})" for h in p.get("holds",[])]
    return "\n".join(L[:5]+[x if x.startswith(("#","Status:")) or not x else safe(x) for x in L[5:]])+"\n"  # hold lines are screened too (#4.3)
def check_governed(p):
    need(isinstance(p,dict),f"governed input must be a JSON object, got {type(p).__name__}; fail closed")
    if p.get("contract_version")!=CONTRACT_VERSION: raise InputError(f"expected contract {CONTRACT_VERSION} in governed input")
    if not isinstance(p.get("wall_decision"),dict): raise InputError("governed input has no wall_decision object; run wall_check first; fail closed")
    check_contract(p,"governed","governed")  # whole stage schema, closed enums included (confidentiality-and-ethical-wall-rules.md #1.3)
    check_hold_evidence(p,"governed"); check_digest(p,"governed",p["wall_decision"]["status"])  # holds are cumulative (#1.4)
def _hkey(h): return (h.get("hold_id"),h.get("reason"),"" if h.get("hold_id")=="HOLD-MISSING-WALL-REGISTER" else h.get("path"))
def rederive(p,register,inventory,new=()):
    """The wall decision, workspace decisions and digest gating are re-derived from the raw wall register and
    workspace inventory by re-running wall_check's derivation, never taken from the governed file. A governed document
    whose decision state disagrees, or that lacks a hold the derivation raises, is refused (#1.4). The holds this
    engine raised itself while screening the governed document (new) are then merged and the decision re-derived once
    more, so a late screening hold gates knowledge and access exactly as an upstream hold would (#1.4, #2.1). Returns
    the effective wall_decision (held and name-withheld workspace lists are the union, most restrictive wins)."""
    r=govern(copy.deepcopy(p),register,inventory); W=p["wall_decision"]; R=r["wall_decision"]
    bad=[k for k in ("status","denied_workspace_ids","allowed_knowledge_ids","denied_knowledge_ids") if W.get(k)!=R.get(k)]
    bad+=[k for k in ("held_workspace_ids","name_withheld_workspace_ids") if not set(R.get(k,[]))<=set(W.get(k,[]))]
    have={_hkey(h) for h in p.get("holds",[])}; missing=sum(_hkey(h) not in have for h in r["holds"])
    if missing: bad.append(f"{missing} re-derived hold(s) missing")
    rk,sk=r["knowledge_digest"],p["knowledge_digest"]
    if rk.get("status")!=sk.get("status") or knowledge_ids(rk.get("items"))!=knowledge_ids(sk.get("items")): bad.append("knowledge_digest")
    need(not bad,f"governed decision state does not match the state re-derived from the wall register and workspace inventory ({', '.join(bad)}); the governed file was edited or is stale - re-run wall_check; fail closed (confidentiality-and-ethical-wall-rules.md #1.4)")
    for k in ("held_workspace_ids","name_withheld_workspace_ids"): R[k]=list(dict.fromkeys(list(W.get(k,[]))+R[k]))
    if new:
        q=copy.deepcopy(p); q["holds"]=dedup_holds(list(q.get("holds",[]))+list(new)); R2=govern(q,register,inventory)["wall_decision"]
        for k in ("held_workspace_ids","name_withheld_workspace_ids"): R2[k]=list(dict.fromkeys(R[k]+R2[k]))
        R=R2
    return R
def main():
    ap=ArgParser(); ap.add_argument("--governed",required=True); ap.add_argument("--wall-register",required=True); ap.add_argument("--workspace-inventory",required=True); ap.add_argument("--out",required=True); ap.add_argument("--pack-out",required=True); ap.add_argument("--generated-at",required=True); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    p=load_json(a.governed,"governed input"); check_governed(p); set_trusted_domains((p.get("engagement") or {}).get("trusted_domains"))
    # The governed document is untrusted input: its upstream holds and every content field are screened for embedded
    # instructions and for other clients named in the wall register, and flagged text withheld, before anything is
    # derived from it (confidentiality-and-ethical-wall-rules.md #3.3, #4.1, #4.3).
    terms=register_terms(a.wall_register,p.get("engagement") or {},own_words(p))
    p,gh=screen_upstream(p,"governed",ENGINE,terms); p,oh=screen_other(p,terms,ENGINE,"governed.")
    esc=p.setdefault("escalations",[])
    if gh: esc.append(f"{len(gh)} governed field(s) held for embedded instruction review (confidentiality-and-ethical-wall-rules.md #4.1-#4.5)")
    if oh: esc.append(other_escalation(len(oh)))
    fixed=[]; screened=[]
    def add_hold(hs,hid,path,why,cit): hs.append({"hold_id":hid,"path":path,"reason":why,"source":ENGINE,"confidence":.99,"citation":cit})
    # The workspace inventory is read and every cell screened (instructions and other clients) before anything is
    # gated: screening holds, like the governed document's own, are merged before the decision is re-derived, so they
    # hold the wall, the digest and knowledge-dependent or client-confidential access (#1.4, #2.1, #3.3; checklist B6).
    # Cells are screened from the rows AS READ, before an unusable header or a repeated ID empties the collection the
    # decisions use: an inventory that is not used is still screened and its flagged cells held (#1.3, #3.3, #4.3).
    rows=read_csv(a.workspace_inventory,False,"workspace inventory")
    if rows is None:
        add_hold(fixed,"HOLD-MISSING-WORKSPACE-INVENTORY",a.workspace_inventory,"missing workspace inventory; no access is requested","workspace-inventory-rules.md #1.2"); rows=[]
    else:
        dup=duplicate_rows(rows,"workspace_id")  # keyed by workspace_id: a repeat holds, never last-wins (#1.3)
        screened=scan_rows(rows,"raw/workspace-inventory.csv")+screen_csv_other(rows,"raw/workspace-inventory.csv",terms,ENGINE)
        if rows.duplicate_columns:
            add_hold(fixed,"HOLD-MALFORMED-WORKSPACE-INVENTORY","raw/workspace-inventory.csv header","workspace inventory "+DUPLICATE_HEADER_REASON+"; no access is requested","workspace-inventory-rules.md #1.3"); rows=[]
        elif missing_columns(rows,INVENTORY_COLUMNS):
            add_hold(fixed,"HOLD-MALFORMED-WORKSPACE-INVENTORY","raw/workspace-inventory.csv header",f"workspace inventory is missing required column(s): {', '.join(missing_columns(rows,INVENTORY_COLUMNS))}; no access is requested","workspace-inventory-rules.md #1.3"); rows=[]
        elif dup:
            add_hold(fixed,"HOLD-MALFORMED-WORKSPACE-INVENTORY","raw/workspace-inventory.csv rows "+", ".join(map(str,dup))+" workspace_id","workspace inventory workspace_id "+DUPLICATE_ID_REASON+"; no access is requested","workspace-inventory-rules.md #1.3"); rows=[]
    bad_rows=set(getattr(rows,"malformed",()))
    role=low((p.get("joiner") or {}).get("role")); allowed={canon_id(k):v for k,v in next((v for k,v in M.items() if low(k)==role),{}).items()}
    if not allowed: add_hold(fixed,"HOLD-ROLE-NOT-IN-MATRIX","scope.joiner.role",f"joiner role {role or '(none)'} is not in the role-access matrix; no access is requested","role-access-matrix.md #4.3")
    def build(wall):
        """The checklist for one effective wall decision; returns (items, the access holds it raises)."""
        denied=cset(wall.get("denied_workspace_ids")); held=cset(wall.get("held_workspace_ids")); hidden=cset(wall.get("name_withheld_workspace_ids")); wstat=wall.get("status"); out=[]; ah=[]
        for n,r in enumerate(rows,2):
            wid=(r.get("workspace_id") or "").strip(); wt=low(r.get("workspace_type")); req=low(r.get("requested_permission")) or low(r.get("default_permission")); default=low(r.get("default_permission")) or req; dep=depends_on_knowledge(r.get("depends_on_knowledge")); conf=client_confidential(r.get("data_classification")); maxp=allowed.get(canon_id(wt)); status="request"; reason="role matrix allows requested workspace access"; perm=req; cit=f"{r.get('citation') or 'raw/workspace-inventory.csv'}; role-access-matrix.md #2.1; workspace-inventory-rules.md #3.1"
            withheld=[c for c in DECISION_COLUMNS if is_withheld(r.get(c))]  # a withheld identifier or enum is never a decision key (#3.3, #4.3)
            invalid=[x for x,bad in (("workspace_id blank",not wid),("withheld field(s): "+", ".join(withheld),bool(withheld)),("row has more fields than the header",n in bad_rows),("no requested or default permission",not req),("unrecognised default_permission",default not in O),("unrecognised data_classification",canon_id(r.get("data_classification")) not in cset(KNOWN_CLASSIFICATIONS)),("unrecognised depends_on_knowledge",low(r.get("depends_on_knowledge")) not in TRUE_VALUES|FALSE_VALUES)) if bad]
            if wid and canon_id(wid) in denied: status="denied_by_wall"; reason="workspace denied by wall_check"; perm="none"; cit+="; confidentiality-and-ethical-wall-rules.md #2.3"
            elif invalid:
                status="not_requested_invalid_row"; reason="invalid inventory row ("+"; ".join(invalid)+"); nothing requested"; perm="none"; cit+="; workspace-inventory-rules.md #1.3,#2.3"
                add_hold(ah,"HOLD-INVALID-WORKSPACE-ROW",f"raw/workspace-inventory.csv row {n}","invalid workspace inventory row: "+"; ".join(invalid),"workspace-inventory-rules.md #1.3,#2.3")
            elif canon_id(wid) in held or (wstat in {"hold","denied"} and (dep or conf)): status="hold_pending_wall_review"; reason="prior-knowledge dependent access held until wall status is clear" if dep else "client-confidential workspace held pending wall review"; perm="none"; cit+="; workspace-inventory-rules.md #2.1"
            elif not maxp: status="not_requested_role_not_allowed"; reason="role matrix does not allow this workspace type"; perm="none"; cit+="; role-access-matrix.md #1"
            elif req not in O or O[req]>=O["admin"]: status="not_requested_exceeds_role"; reason=f"requested {req} exceeds role ceiling {maxp}; admin rights are never requested" if req in O else f"unrecognised requested permission exceeds role ceiling {maxp}"; perm="none"; cit+="; role-access-matrix.md #2.1,#2.2; workspace-inventory-rules.md #3.2"
            elif O[req]>min(O[default],O[maxp]):
                # Request = min(requested, workspace default, role ceiling); anything wider is clamped and held, never granted (#2.3).
                perm=NAMES[min(O[req],O[default],O[maxp])]; reason=f"requested {req} clamped to {perm} (workspace default {default}, role ceiling {maxp}); held for engagement manager review"; cit+="; role-access-matrix.md #2.3"
                add_hold(ah,"HOLD-PERMISSION-CLAMPED",f"raw/workspace-inventory.csv row {n}.requested_permission",f"requested {req} is wider than min(workspace default {default}, role ceiling {maxp}); request clamped to {perm}","role-access-matrix.md #2.3")
                if perm=="none": status="not_requested_exceeds_role"
            name=r.get("name") if (r.get("name") or "").strip() else wid
            if not (name or "").strip() or canon_id(wid) in hidden or hits(name) or is_withheld(name): name=wid or "(blank workspace_id)"  # never rendered blank (#1.3)
            out.append({"workspace_id":wid,"workspace_name":name,"workspace_type":r["workspace_type"] if is_withheld(r.get("workspace_type")) else wt,"status":status,"requested_permission":perm,"reason":reason,"source":ENGINE,"confidence":.96,"citation":cit})
        return out,ah
    # Access-decision holds (missing or unusable inventory, role not in the matrix, and below an invalid row or a
    # clamped permission) govern their checklist rows and the pack status, not the wall (role-access-matrix.md #2.3).
    wall=rederive(p,a.wall_register,a.workspace_inventory,gh+oh+screened); out,ah=build(wall)
    p["wall_decision"]=wall; wstat=wall.get("status"); need(wstat in WALL_STATUSES,"re-derived wall status is not recognised; fail closed")
    if wstat in {"hold","denied"}:
        # No knowledge is released while the effective wall status is hold or denied, whatever the digest says (#2.2, #2.3).
        kd=p.get("knowledge_digest") or {}
        if kd.get("status") not in {"hold","denied_by_wall"}: kd["status"]="denied_by_wall" if wstat=="denied" else "hold"
        kd["items"]=[]; p["knowledge_digest"]=kd; wall["allowed_knowledge_ids"]=[]
    holds=list(p.get("holds",[]))+gh+oh+screened+fixed+ah
    holds=dedup_holds(holds); pend=sum(i["status"]=="hold_pending_wall_review" for i in out)
    reasons=(["open_holds"] if holds else [])+(["wall_status_hold"] if wstat=="hold" else [])+(["workspaces_pending_wall_review"] if pend else [])  # workspace-inventory-rules.md #3.3
    if pend: esc.append(f"{pend} workspace(s) held pending wall review; the pack stays on hold until Risk/Conflicts resolve the wall decision (workspace-inventory-rules.md #3.3)")
    p["access_checklist"]=out; p["holds"]=holds; p["mobilization_pack"]={"status":"on_hold_internal_only" if reasons else "draft_internal_only","hold_reasons":reasons,"label":"DRAFT - for internal review only. Do not send to the client or provision access.","sections":["client_context","scope","prior_knowledge","team_roster","access_checklist","wall_briefing","first_week_plan"],"source":ENGINE,"confidence":.94,"citation":"workspace-inventory-rules.md #3.1,#3.3; confidentiality-and-ethical-wall-rules.md #3.1"}; p.setdefault("provenance",{}).setdefault("engines",[]).append(f"access_checklist/{VERSION}"); p["provenance"]["generated_at"]=ts
    check_contract(p,"access","access"); write_atomic([(a.out,json_bytes(a.out,p,"access checklist output"),"access checklist output"),(a.pack_out,text_bytes(a.pack_out,pack(p),"pack output"),"pack output")])  # both serialised first, then written atomically together  # the document written is held to the contract (#1.3)
if __name__=="__main__": guard(main)
