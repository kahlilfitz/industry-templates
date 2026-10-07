#!/usr/bin/env python3
import argparse, copy, re
from safety_text import *
import wall_check
from wall_check import govern
ENGINE="engine:access_checklist"
M={"delivery analyst":{"engagement-sharepoint":"viewer","delivery-planner":"viewer","client-teams-channel":"member","knowledge-repository":"viewer"},"delivery manager":{"engagement-sharepoint":"contributor","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"},"client delivery manager":{"engagement-sharepoint":"contributor","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"},"engagement coordinator":{"engagement-sharepoint":"viewer","delivery-planner":"contributor","client-teams-channel":"member","knowledge-repository":"viewer"}}  # role-access-matrix.md #1.1-#1.3
O={"none":0,"viewer":1,"member":2,"contributor":3,"admin":4,"owner":5}  # role-access-matrix.md #2.1-#2.3: every permission has its own rank
NAMES={v:k for k,v in O.items() if k!="owner"}
ADMIN_EXCLUDED=True  # workspace-inventory-rules.md #3.2
WALL_STATUSES={"clear","denied","hold"}  # confidentiality-and-ethical-wall-rules.md #2.2
INVENTORY_COLUMNS=wall_check.INVENTORY_COLUMNS  # workspace-inventory-rules.md #1.3 (one definition, checked by wall_check.inventory_problem)
KNOWN_CLASSIFICATIONS={"client_confidential","confidential","restricted","internal","public"}  # workspace-inventory-rules.md #2.3
def low(v): return canon_text(v)  # enums and roles: the one canonical comparison form (confidentiality-and-ethical-wall-rules.md #1.3)
def cset(xs): return {join_key(x) for x in xs or []}-{None}  # workspace IDs, types and classifications compare canonically; a blank key is in no set (#1.3)
def safe(x): return WITHHELD if hits(x) else x  # confidentiality-and-ethical-wall-rules.md #4.3
def strs(xs): return [x for x in (xs or []) if isinstance(x,str)]  # contract-valid arrays render without a TypeError (#1.3)
DECISION_COLUMNS=("workspace_id","workspace_type","default_permission","requested_permission","depends_on_knowledge","data_classification")  # workspace-inventory-rules.md #1.3
def _src(*xs): return rendered_values(*xs)
def _role_src(r): return () if low(r) in {low(k) for k in M} else _src(r)  # a matrix role is fixed vocabulary, not free text
def _hold_src(h):
    """The supplied text a hold line renders, in rendered order: its ID, reason, location and citation, each unless it
    is an engine template (#4.5)."""
    return _src(*(h.get(k) for k in ("hold_id","reason","path","citation") if not engine_text(k,h.get(k))))
def pack_rows(p):
    """[(line, the free-text values it renders)] for the pack, one entry per line, before line screening (#4.3, #4.5)."""
    e=p.get("engagement") or {}; s=p.get("scope_summary") or {}; j=p.get("joiner") or {}; kd=p.get("knowledge_digest") or {}; mp=p.get("mobilization_pack") or {}
    hc=len(p.get("holds",[])); pend=sum(i.get("status")=="hold_pending_wall_review" for i in p.get("access_checklist",[]))
    parts=([f"{hc} open hold(s)"] if hc else [])+([f"{pend} workspace(s) pending wall review"] if pend else [])+(["wall status on hold"] if "wall_status_hold" in mp.get("hold_reasons",[]) and not hc else [])
    E=lambda *xs:[(x,()) for x in xs]
    R=E("# Engagement Mobilization & Onboarding Pack","","**DRAFT - for internal review only. Do not send to the client or provision access.**","",f"Pack status: {mp.get('status','on_hold_internal_only')}"+(" - "+"; ".join(parts)+"; resolve before sharing with the joiner." if parts else ""),f"Generated at: {p.get('run_metadata',{}).get('generated_at',p.get('provenance',{}).get('generated_at',''))}")
    R+=[(f"Engagement: {e.get('title','')} ({e.get('engagement_id','')})",_src(e.get("title"),e.get("engagement_id"))),(f"Client: {e.get('client_name','')}",_src(e.get("client_name"))),(f"Joiner: {j.get('person','')} - {j.get('role','')}",_src(j.get("person"))+_role_src(j.get("role")))]
    R+=E("","## Client context and objectives")+[(f"- {x}",_src(x)) for x in s.get("objectives",[])]+E("","## SOW scope and exclusions","","### In scope")+[(f"- {x}",_src(x)) for x in s.get("in_scope",[])]+E("","### Exclusions")+[(f"- {x}",_src(x)) for x in s.get("exclusions",[])]+E("","## Deliverables and key dates")
    R+=[(f"- Deliverable: {x}",_src(x)) for x in s.get("deliverables",[])]+[(f"- Key date: {x}",_src(x)) for x in s.get("key_dates",[])]
    R+=E("","## Prior-knowledge digest",f"Status: {kd.get('status','unknown')}")
    R+=[(f"- {i.get('title')} ({i.get('knowledge_id')}) [{i.get('review_status','pending_practice_review')}] - {i.get('summary')} Source: {'; '.join(strs(i.get('citations')))}",_src(i.get("title"),i.get("knowledge_id"),i.get("summary"),*rendered_citations(strs(i.get("citations"))))) for i in kd.get("items",[])] or E("- No knowledge items are cleared for this joiner in this run.")
    R+=E("","## Team roster")+[(f"- {r.get('person')} - {r.get('role')} - {', '.join(strs(r.get('responsibilities')))} - POC: {r.get('point_of_contact')}",_src(r.get("person"),*strs(r.get("responsibilities")),r.get("point_of_contact"))+_role_src(r.get("role"))) for r in p.get("team_roster",[])]+[(f"- Proposed, not assigned: {r.get('candidate_name')} for {r.get('role_title')}",_src(r.get("candidate_name"),r.get("role_title"))) for r in p.get("proposed_staffing",[])]
    R+=E("","## Access-request checklist")+([(f"- {i.get('workspace_name')} ({i.get('workspace_id')}): {i.get('status')} - {i.get('requested_permission','none')} - {i.get('reason')}",_src(i.get("workspace_name") if i.get("workspace_name")!=i.get("workspace_id") else None,i.get("workspace_id"))) for i in p.get("access_checklist",[])] or E("- No access is requested in this run; see Escalations and holds."))
    R+=E("","## Confidentiality and ethical-wall briefing")+([(f"- May not access/discuss {i.get('type')}: {i.get('item')} - {i.get('restriction')}",_src(i.get("item"),i.get("restriction"))) for i in (p.get("wall_decision") or {}).get("may_not_access_discuss",[])] or E("- No wall restriction was found for the joiner, subject to human review of this draft."))
    R+=E("","## First-week plan")+[(f"{n}. {x}",_src(x)) for n,x in enumerate(s.get("first_week_focus",[]),1)]+E("","## Escalations and holds")+[(f"- {x}",_src(x)) for x in p.get("escalations",[])]+[(f"- HOLD {h.get('hold_id')}: {h.get('reason')} at {h.get('path')} ({h.get('citation')})",_hold_src(h)) for h in p.get("holds",[])]
    return R
# The only values a pack line renders that pack_rows does not hand to the rendered-order screen (#4.5): each is engine
# vocabulary no input supplies (a contract enum, the --generated-at run timestamp, or engine wording built from closed
# vocabularies), proved equal to the engines' re-derivation (same_document). Matrix roles and engine-template hold
# fields are screened unless they equal the fixed vocabulary (_role_src, _hold_src). tests/run_tests.py
# (qa101y_checks) fails if a pack line renders any other value that is not screened.
PACK_UNSCREENED={
    "mobilization_pack.status":"contract enum (draft_internal_only, on_hold_internal_only)",
    "run_metadata.generated_at":"--generated-at run timestamp, ISO-8601 UTC (stage_timestamp)",
    "provenance.generated_at":"--generated-at run timestamp, ISO-8601 UTC (stage_timestamp)",
    "knowledge_digest.status":"contract enum (ready, empty, hold, denied_by_wall)",
    "knowledge_digest.items[].review_status":"contract enum (knowledge-reuse-rules.md #2.3)",
    "access_checklist[].status":"contract enum (workspace-inventory-rules.md #2)",
    "access_checklist[].requested_permission":"contract enum (role-access-matrix.md #2)",
    "access_checklist[].reason":"engine wording from permission names and fixed column names (role-access-matrix.md #2.3)",
    "wall_decision.may_not_access_discuss[].type":"contract enum (client_or_matter, workspace)"}
def pack_lines(p,held_lines=()):
    """The mobilization pack, one entry per rendered line. Every line after the header is screened alone (#4.3); a
    line in a run the whole-pack screen held that carries no free-text value to withhold is withheld whole (#4.5)."""
    L=[x for x,_ in pack_rows(p)]
    return L[:5]+[(("- " if x.startswith("- ") else "")+WITHHELD) if x in held_lines else x if x.startswith(("#","Status:")) or not x else safe(x) for x in L[5:]]  # hold lines are screened too (#4.3)
def pack(p,held_lines=()): return "\n".join(pack_lines(p,held_lines))+"\n"
# The rendered pack is screened as a whole (#4.5): values from different fields, records and sources are placed on
# adjacent lines ("Client: ..." above "Joiner: ..."), so a claim split across them would compose only in the pack.
# The pack is read in its rendered order as scan_lines reads a source: each line's free-text values (joined as the
# line renders them), every pair of neighbouring lines, every run of 3 to RUN_MAX lines and the whole pack. Lines that
# render only engine text (headings, labels, statuses, reasons, hold lines) or are withheld are skipped and never break
# a run: the engine's fixed vocabulary ("pending wall review", "denied") is not source text and would compose with
# ordinary names ("Cleared Healthcare ..."). A hit holds the run, withholds every free-text value on its lines in the
# whole access checklist and the pack, holds the wall like any screening hold, and the pack is re-derived until it
# reads clean (derive). pack-draft's pre-render check (verify_render.py) refuses a pack that does not.
PACK_PASSES=8
PACK_RUN_PATH="mobilization-pack.md"
def pack_screen(p,entries=None):
    """One screening text per rendered pack entry: the free-text values it renders, in pack order ('' for an entry that
    renders only engine text or is withheld)."""
    rows=pack_rows(p); L=pack_lines(p) if entries is None else entries
    return ["" if not s or WITHHELD in x else rendered_text(s) for (_,s),x in zip(rows,L)]
def pack_runs(texts):
    """[(entry indices, families)] for every pack entry whose values trip together (joined, or side by side on the
    line: line_hits), and every pair or run of entries that trips only when read together (#4.5)."""
    return [([k],h) for k,x in enumerate(texts) if x for h in [line_hits(x)] if h]+rendered_runs(texts)
def pack_run_hold(entries,span,h):
    first=[0]
    for e in entries: first.append(first[-1]+e.count("\n")+1)
    a,b=first[span[0]]+1,first[span[-1]+1]
    return hold(f"{PACK_RUN_PATH} line {a}" if a==b else f"{PACK_RUN_PATH} lines {a}-{b}","\n".join(entries[k] for k in span),h)
def pack_escalation(n): return rendered_escalation("pack",n)
PACK_KEEP=RENDER_KEEP+("mobilization_pack",)
def check_governed(p):
    need(isinstance(p,dict),f"governed input must be a JSON object, got {type(p).__name__}; fail closed")
    if p.get("contract_version")!=CONTRACT_VERSION: raise InputError(f"expected contract {CONTRACT_VERSION} in governed input")
    if not isinstance(p.get("wall_decision"),dict): raise InputError("governed input has no wall_decision object; run wall_check first; fail closed")
    check_contract(p,"governed","governed")  # whole stage schema, closed enums included (confidentiality-and-ethical-wall-rules.md #1.3)
    check_hold_evidence(p,"governed")  # holds are cumulative (#1.4); every other field is proved equal to its re-derivation (same_document)
UNION=("held_workspace_ids","name_withheld_workspace_ids")  # merged canonically with late screening holds' re-derivation (most restrictive wins)
def effective_wall(p,register,inventory,closeout,staffing,new=()):
    """The effective wall decision for a governed document already proved equal to its re-derivation from the raw
    inputs (same_document, #1.4). wall_check's derivation is re-run on the screened document; the holds this engine
    raised itself while screening it (new) are then merged and the decision re-derived once more, so a late screening
    hold gates knowledge and access exactly as an upstream hold would (#1.4, #2.1). Held and name-withheld workspace
    IDs are merged canonically with the carried ones (most restrictive wins)."""
    W=p["wall_decision"]; R=govern(copy.deepcopy(p),register,inventory,closeout,staffing)["wall_decision"]
    for k in UNION: R[k]=canon_union(W.get(k),R[k])
    if new:
        q=copy.deepcopy(p); q["holds"]=dedup_holds(list(q.get("holds",[]))+list(new)); R2=govern(q,register,inventory,closeout,staffing)["wall_decision"]
        for k in UNION: R2[k]=canon_union(R[k],R2[k])
        R=R2
    return R
def main():
    ap=ArgParser()
    for k in ("--governed","--raw-dir","--staffing","--confirmed-roster","--closeout","--wall-register","--workspace-inventory","--out","--pack-out","--generated-at"): ap.add_argument(k,required=True)
    a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    p=load_json(a.governed,"governed input"); check_governed(p)
    g=wall_check.rederive(p,a.raw_dir,a.staffing,a.confirmed_roster,a.closeout,a.wall_register,a.workspace_inventory,stage_timestamp(p,"governed input"),"governed input")
    same_document(p,g,"governed input")  # every field equals the scope_digest + knowledge_match + wall_check re-derivation from the raw inputs (#1.4)
    d,txt=derive(p,a.wall_register,a.workspace_inventory,ts,a.closeout,a.staffing)
    write_atomic([(a.out,json_bytes(a.out,d,"access checklist output"),"access checklist output"),(a.pack_out,text_bytes(a.pack_out,txt,"pack output"),"pack output")])  # both serialised first, then written atomically together
def derive(p,register,inventory,ts,closeout,staffing):
    """(access checklist document, mobilization pack text) for a governed document already proved equal to its
    re-derivation from the raw inputs (#1.4). pack-draft's pre-render check (verify_render.py) re-runs this too."""
    d,entries=derive_entries(p,register,inventory,ts,closeout,staffing); return d,"\n".join(entries)+"\n"
def derive_entries(p,register,inventory,ts,closeout,staffing):
    """(access checklist document, rendered pack entries). The rendered pack is screened whole (pack_runs); each held
    run adds a hold and withholds its text, and the document is derived again until the pack reads clean (#4.5)."""
    ph=[]; blocked=set(); held=set()
    for _ in range(PACK_PASSES):
        d=_derive(copy.deepcopy(p),register,inventory,ts,closeout,staffing,ph,blocked); entries=pack_lines(d,held)
        found=pack_runs(pack_screen(d,entries))
        if not found: return d,entries
        rows=pack_rows(d); grew=False
        for span,h in found:
            x=pack_run_hold(entries,span,h)
            if hold_key(x) not in {hold_key(y) for y in ph}: ph.append(x); grew=True
            for k in span:
                src=[v for v in rows[k][1] if v not in blocked]
                if src: blocked.update(src); grew=True
                elif rows[k][0] not in held: held.add(rows[k][0]); grew=True
        if not grew: break
    raise InputError("the rendered mobilization pack still reads as an instruction across lines after its text was withheld (text not repeated); nothing written; fail closed (confidentiality-and-ethical-wall-rules.md #4.5)")
def _derive(p,register,inventory,ts,closeout,staffing,ph=(),blocked=()):
    """The access checklist document for the governed document p, with the whole-pack holds raised so far (ph) and
    the pack values they withhold (blocked)."""
    adopt_trust(p)  # from the declaration lines scope_digest accepted, never a carried list (#1.4, #4.4)
    # The governed document is untrusted input: its upstream holds and every content field are screened for embedded
    # instructions and for other clients named in the wall register, and flagged text withheld, before anything is
    # derived from it (confidentiality-and-ethical-wall-rules.md #3.3, #4.1, #4.3).
    terms,_=wall_check.knowledge_match.other_client_terms(p,closeout,register,staffing)  # the one identity set every stage uses (#3.3)
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
    rows=read_csv(inventory,False,"workspace inventory"); check_csv_ids(rows,"raw/workspace-inventory.csv",("workspace_id",)); check_csv_names(rows,"raw/workspace-inventory.csv",("name",))  # identifier shape (#1.3)
    as_read=[dict(r) for r in rows or []]  # the cells before screening rewrites them: a quarantined row's grammar is read from these (#1.3)
    bad=wall_check.inventory_problem(rows)  # the one missing/malformed check wall_check applies, on the rows as read (#1.2, #1.3)
    if bad: fixed.append(wall_check.inventory_hold(bad,ENGINE))
    if rows is not None:
        screened=scan_rows(rows,"raw/workspace-inventory.csv")+screen_csv_other(rows,"raw/workspace-inventory.csv",terms,ENGINE)
    if bad: rows=[]
    foreign=wall_check.foreign_rows(rows)  # another client's workspace: never requested or listed by its supplied ID or name (#3.3)
    bad_rows=set(getattr(rows,"malformed",()))
    role=low((p.get("joiner") or {}).get("role")); allowed={canon_id(k):v for k,v in next((v for k,v in M.items() if low(k)==role),{}).items()}
    if not allowed: add_hold(fixed,"HOLD-ROLE-NOT-IN-MATRIX","scope.joiner.role","joiner role (not repeated) is not in the role-access matrix; no access is requested","role-access-matrix.md #4.3")
    def row_problems(r,n):
        """The grammar problems of inventory row n, in fixed vocabulary that repeats no cell value (#1.3, #2.3)."""
        wid=(r.get("workspace_id") or "").strip(); req=low(r.get("requested_permission")) or low(r.get("default_permission")); default=low(r.get("default_permission")) or req
        withheld=[c for c in DECISION_COLUMNS if is_withheld(r.get(c))]  # a withheld identifier or enum is never a decision key (#3.3, #4.3)
        return [x for x,bad in (("workspace_id blank",not wid),("withheld field(s): "+", ".join(withheld),bool(withheld)),("row has more fields than the header",n in bad_rows),("no requested or default permission",not req),("unrecognised default_permission",default not in O),("unrecognised data_classification",canon_id(r.get("data_classification")) not in cset(KNOWN_CLASSIFICATIONS)),("unrecognised depends_on_knowledge",low(r.get("depends_on_knowledge")) not in TRUE_VALUES|FALSE_VALUES)) if bad]
    def invalid_hold(ah,n,invalid): add_hold(ah,"HOLD-INVALID-WORKSPACE-ROW",f"raw/workspace-inventory.csv row {n}","invalid workspace inventory row: "+"; ".join(invalid),"workspace-inventory-rules.md #1.3,#2.3")
    def build(wall):
        """The checklist for one effective wall decision; returns (items, the access holds it raises)."""
        denied=cset(wall.get("denied_workspace_ids")); held=cset(wall.get("held_workspace_ids")); hidden=cset(wall.get("name_withheld_workspace_ids")); wstat=wall.get("status"); out=[]; ah=[]
        for n,r in enumerate(rows,2):
            if n in foreign:
                # Another client's row is quarantined (never listed), but only after its grammar is checked, on its
                # cells as read: an invalid row holds by position instead of passing because it is excluded (#1.3, #3.3).
                bad_=row_problems(as_read[n-2],n)
                if bad_: invalid_hold(ah,n,bad_)
                continue
            wid=(r.get("workspace_id") or "").strip(); wt=low(r.get("workspace_type")); req=low(r.get("requested_permission")) or low(r.get("default_permission")); default=low(r.get("default_permission")) or req; dep=depends_on_knowledge(r.get("depends_on_knowledge")); conf=client_confidential(r.get("data_classification")); maxp=allowed.get(canon_id(wt)); status="request"; reason="role matrix allows requested workspace access"; perm=req; cit=f"{r.get('citation') or 'raw/workspace-inventory.csv'}; role-access-matrix.md #2.1; workspace-inventory-rules.md #3.1"
            invalid=row_problems(r,n)
            if join_key(wid) in denied:
                status="denied_by_wall"; reason="workspace denied by wall_check"; perm="none"; cit+="; confidentiality-and-ethical-wall-rules.md #2.3"
                if invalid: invalid_hold(ah,n,invalid)  # denied either way, but an invalid row still holds (#1.3)
            elif invalid:
                status="not_requested_invalid_row"; reason="invalid inventory row ("+"; ".join(invalid)+"); nothing requested"; perm="none"; cit+="; workspace-inventory-rules.md #1.3,#2.3"
                invalid_hold(ah,n,invalid)
            elif join_key(wid) in held or (wstat in {"hold","denied"} and (dep or conf)): status="hold_pending_wall_review"; reason="prior-knowledge dependent access held until wall status is clear" if dep else "client-confidential workspace held pending wall review"; perm="none"; cit+="; workspace-inventory-rules.md #2.1"
            elif not maxp: status="not_requested_role_not_allowed"; reason="role matrix does not allow this workspace type"; perm="none"; cit+="; role-access-matrix.md #1"
            elif req not in O or O[req]>=O["admin"]: status="not_requested_exceeds_role"; reason=f"requested {req} exceeds role ceiling {maxp}; admin rights are never requested" if req in O else f"unrecognised requested permission exceeds role ceiling {maxp}"; perm="none"; cit+="; role-access-matrix.md #2.1,#2.2; workspace-inventory-rules.md #3.2"
            elif O[req]>min(O[default],O[maxp]):
                # Request = min(requested, workspace default, role ceiling); anything wider is clamped and held, never granted (#2.3).
                perm=NAMES[min(O[req],O[default],O[maxp])]; reason=f"requested {req} clamped to {perm} (workspace default {default}, role ceiling {maxp}); held for engagement manager review"; cit+="; role-access-matrix.md #2.3"
                add_hold(ah,"HOLD-PERMISSION-CLAMPED",f"raw/workspace-inventory.csv row {n}.requested_permission",f"requested {req} is wider than min(workspace default {default}, role ceiling {maxp}); request clamped to {perm}","role-access-matrix.md #2.3")
                if perm=="none": status="not_requested_exceeds_role"
            name=r.get("name") if (r.get("name") or "").strip() else wid
            if not (name or "").strip() or join_key(wid) in hidden or hits(name) or is_withheld(name): name=wid or "(blank workspace_id)"  # never rendered blank (#1.3)
            out.append({"workspace_id":wid,"workspace_name":name,"workspace_type":r["workspace_type"] if is_withheld(r.get("workspace_type")) else wt,"status":status,"requested_permission":perm,"reason":reason,"source":ENGINE,"confidence":.96,"citation":cit})
        return out,ah
    # Access-decision holds (role not in the matrix, and below an invalid row or a clamped permission) govern their
    # checklist rows and the pack status, not the wall (role-access-matrix.md #2.3). A missing or malformed inventory
    # holds the wall too: wall_check raised the same hold, carried in the governed document (workspace-inventory-rules.md #1.2, #1.3).
    wall=effective_wall(p,register,inventory,closeout,staffing,gh+oh+screened+list(ph)); out,ah=build(wall)
    p["wall_decision"]=wall; wstat=wall.get("status"); need(wstat in WALL_STATUSES,"re-derived wall status is not recognised; fail closed")
    if wstat in {"hold","denied"}:
        # No knowledge is released while the effective wall status is hold or denied, whatever the digest says (#2.2, #2.3).
        kd=p.get("knowledge_digest") or {}
        if kd.get("status") not in {"hold","denied_by_wall"}: kd["status"]="denied_by_wall" if wstat=="denied" else "hold"
        kd["items"]=[]; p["knowledge_digest"]=kd; wall["allowed_knowledge_ids"]=[]
    holds=list(p.get("holds",[]))+gh+oh+screened+fixed+ah+list(ph)
    if ph: esc.append(pack_escalation(len(ph)))
    holds=dedup_holds(holds); pend=sum(i["status"]=="hold_pending_wall_review" for i in out)
    reasons=(["open_holds"] if holds else [])+(["wall_status_hold"] if wstat=="hold" else [])+(["workspaces_pending_wall_review"] if pend else [])  # workspace-inventory-rules.md #3.3
    if pend: esc.append(f"{pend} workspace(s) held pending wall review; the pack stays on hold until Risk/Conflicts resolve the wall decision (workspace-inventory-rules.md #3.3)")
    p["access_checklist"]=out; p["holds"]=holds; p["mobilization_pack"]={"status":"on_hold_internal_only" if reasons else "draft_internal_only","hold_reasons":reasons,"label":"DRAFT - for internal review only. Do not send to the client or provision access.","sections":["client_context","scope","prior_knowledge","team_roster","access_checklist","wall_briefing","first_week_plan"],"source":ENGINE,"confidence":.94,"citation":"workspace-inventory-rules.md #3.1,#3.3; confidentiality-and-ethical-wall-rules.md #3.1"}; p.setdefault("provenance",{}).setdefault("engines",[]).append(f"access_checklist/{VERSION}"); p["provenance"]["generated_at"]=ts
    p=withhold_values(p,blocked,PACK_KEEP)  # text on a held pack run is withheld everywhere it appears (#4.5)
    p=bind_withheld(settle_trust(p),"access",ENGINE); check_contract(p,"access","access")  # the document written is held to the contract (#1.3)
    return p
if __name__=="__main__": guard(main)
