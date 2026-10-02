#!/usr/bin/env python3
import argparse, hashlib, re
from safety_text import *
ENGINE="engine:wall_check"; CLEAR={"clear","cleared"}  # confidentiality-and-ethical-wall-rules.md #2.2
RESTRICT={"restricted","walled","conflicted","deny"}  # confidentiality-and-ethical-wall-rules.md #2.3
MISSING_REGISTER_HOLDS=True  # confidentiality-and-ethical-wall-rules.md #2.1
UNKNOWN_STATUS_HOLDS=True  # confidentiality-and-ethical-wall-rules.md #2.2
CLEAR_NEEDS_NAMED_PERSON=True  # confidentiality-and-ethical-wall-rules.md #2.2
FREE_TEXT_NOT_BRIEFED=True  # confidentiality-and-ethical-wall-rules.md #3.1
BRIEFING_TOPICS_SCREENED=True  # confidentiality-and-ethical-wall-rules.md #3.2
KNOWN_CLASSIFICATIONS={"client_confidential","confidential","restricted","internal","public"}  # workspace-inventory-rules.md #2.3
OTHER_CLIENTS_SCREENED=True  # confidentiality-and-ethical-wall-rules.md #3.3
def applies(r,e,j):
    # Every populated field must match; blank person = engagement-wide row; a row must name this client or matter.
    # One canonical comparison (canon_person / canon_id): `Taylor  Reed` and `taylor reed` are the same joiner (#1.3).
    # A withheld value on either side never matches: two different flagged names both read "[withheld ...]" (#4.3).
    for a,b in (("person","person"),("client_name","client_name"),("matter_id","matter_id")):
        if (r.get(a) or "").strip() and (is_withheld(r.get(a)) or is_withheld((j if a=="person" else e).get(b))): return False
    p,c,m=canon_person(r.get("person")),canon_person(r.get("client_name")),canon_id(r.get("matter_id"))
    if p and p!=canon_person(j.get("person")): return False
    if c and c!=canon_person(e.get("client_name")): return False
    if m and m!=canon_id(e.get("matter_id")): return False
    return bool(c or m)
def cin(v,xs): return canon_id(v) in {canon_id(x) for x in xs}  # ID membership by canonical form (#1.3)
def row_cite(r): return r.get("citation") or "raw/ethical-wall-register.csv"
def topics(r): return [x.strip() for x in (r.get("briefing_topics") or "").split(";") if x.strip()]
def names_other(text,terms,own,own_ids):
    """Briefing topics get the strictest screen: known identities, any other matter-like ID and any capitalised name
    that is not this engagement's own (#3.2)."""
    if names_client(text,terms): return True
    if any(canon_id(x) not in own_ids for x in re.findall(r"\b[A-Za-z]{2,}(?:-[A-Za-z0-9]+)*-\d{2,}[A-Za-z0-9-]*\b",text or "")): return True
    for run,start in cap_runs(text):
        ws=words(run)
        if not ws or ws<=own|ALLOW_CAPS or (start and len(run.split())==1): continue
        return True
    return False
def check_matched(p):
    need(isinstance(p,dict),f"matched input must be a JSON object, got {type(p).__name__}; fail closed")
    if p.get("contract_version")!=CONTRACT_VERSION: raise InputError(f"expected contract {CONTRACT_VERSION} in matched input")
    if "prior_knowledge_candidates" not in p or "knowledge_digest" not in p: raise InputError("matched input has no prior_knowledge_candidates/knowledge_digest; run knowledge_match first; fail closed")
    field(p,"knowledge_digest","obj","matched",required=True); check_contract(p,"matched","matched")  # confidentiality-and-ethical-wall-rules.md #1.3
    # Gating state is reconciled, never trusted: the digest must match its holds and candidates, and every placeholder,
    # escalation or held status from an earlier stage must still have its hold (#1.4).
    check_hold_evidence(p,"matched"); check_digest(p,"matched")
def govern(p,register,inventory):
    """Derive the wall decision, the workspace decisions and the digest gating for document p from the raw wall
    register and workspace inventory. access_checklist re-runs this on the governed document to re-derive, never
    trust, the decision state (confidentiality-and-ethical-wall-rules.md #1.4)."""
    p,mh=screen_upstream(p,"matched",ENGINE)  # every upstream string screened and redacted before use; any hit holds the wall (#4.1, #4.3)
    if mh: p.setdefault("escalations",[]).append(upstream_escalation(len(mh)))
    rows=read_csv(register,False,"wall register"); ws=read_csv(inventory,False,"workspace inventory"); up=list(p.get("holds",[])); holds=list(mh); deniedk=[]; deniedw=[]; heldw=[]; may=[]; withheld_names=[]; j=p.get("joiner") or {}; e=p.get("engagement") or {}; esc=p.setdefault("escalations",[])
    status="clear"; reason="wall register marks joiner clear for this client/matter"; cit="confidentiality-and-ethical-wall-rules.md #2.2"
    own=own_words(p); own_ids={canon_id(e.get("matter_id")),canon_id(e.get("engagement_id"))}-{""}
    def hold_status(hid,path,why,rule):
        holds.append({"hold_id":hid,"path":path,"reason":why,"source":ENGINE,"confidence":.99,"citation":f"confidentiality-and-ethical-wall-rules.md {rule}"}); return "hold",why,f"confidentiality-and-ethical-wall-rules.md {rule}"
    # Other-client identities are harvested whatever the register's validity for the decision: a register with a
    # missing or repeated column still names the clients it lists (every copy of a repeated column counts), so the
    # names are withheld everywhere while the decision holds (#2.1, #3.3). They are harvested from the register AS
    # READ, before scan_rows rewrites a flagged cell: a restriction that trips the wire still names its client (#3.3).
    terms=client_terms(other_names(rows,e,own),own) if rows is not None else []
    idh=unreadable_identity_holds(rows,REGISTER_LABEL,ENGINE) if rows is not None else []  # a tripped identity cell naming no one usable holds (#3.3)
    scr=(scan_rows(rows,REGISTER_LABEL) if rows is not None else [])+idh
    p,oh=screen_other(p,terms,ENGINE,"matched.")  # every text field, not only the briefing (#3.3)
    esc=p.setdefault("escalations",[])  # screen_other returns a new document: always rebind (#3.2)
    if oh: esc.append(other_escalation(len(oh)))
    if idh: esc.append(other_escalation(len(idh)))
    scr+=oh; j=p.get("joiner") or {}; e=p.get("engagement") or {}
    if not canon_person(j.get("person")):
        status,reason,cit=hold_status("HOLD-NO-JOINER","scope.joiner","no joiner identified; wall status cannot be determined","#2.2"); holds+=scr
    elif rows is None:
        status,reason,cit=hold_status("HOLD-MISSING-WALL-REGISTER",register,"missing ethical-wall register","#2.1"); holds+=scr
    elif missing_columns(rows,REGISTER_COLUMNS):
        status,reason,cit=hold_status("HOLD-MALFORMED-WALL-REGISTER","raw/ethical-wall-register.csv header",f"ethical-wall register is missing required column(s): {', '.join(missing_columns(rows,REGISTER_COLUMNS))}","#2.1"); holds+=scr
    elif rows.duplicate_columns:
        # A repeated column (status,status) is ambiguous: csv keeps only the last value (restricted,clear -> clear) (#2.1).
        status,reason,cit=hold_status("HOLD-MALFORMED-WALL-REGISTER","raw/ethical-wall-register.csv header","ethical-wall register "+DUPLICATE_HEADER_REASON,"#2.1"); holds+=scr
    else:
        if rows.malformed: hold_status("HOLD-MALFORMED-WALL-REGISTER","raw/ethical-wall-register.csv rows "+", ".join(map(str,rows.malformed)),"ethical-wall register row(s) carry more fields than the header","#2.1")
        holds+=scr
        matches=[(i,r) for i,r in enumerate(rows,2) if applies(r,e,j)]
        # Every cell of a row that applies to this engagement is screened before it is derived from: its citation and
        # restricted workspaces reach the decision and the briefing. Restriction text is never copied (#3.1) and is the
        # source of the identities; briefing topics have the stricter screen below (#3.2, #3.3).
        rh=screen_csv_other(rows,REGISTER_LABEL,terms,ENGINE,only={i for i,_ in matches},skip=("restriction","briefing_topics"))
        if rh: holds+=rh; esc.append(other_escalation(len(rh)))
        restricted=[(i,r) for i,r in matches if canon_text(r.get("status")) in RESTRICT]
        unknown=[r for i,r in matches if canon_text(r.get("status")) not in RESTRICT|CLEAR]
        named_clear=[r for i,r in matches if canon_text(r.get("status")) in CLEAR and canon_person(r.get("person"))]
        if restricted:
            status="denied"; reason="joiner restricted by ethical-wall register; restriction details are held by Risk/Conflicts (need-to-know)"; cit="; ".join(row_cite(r) for i,r in restricted)
            deniedk=[x.get("knowledge_id") for x in p.get("prior_knowledge_candidates",[])]
            for i,r in restricted:
                for w in (r.get("restricted_workspaces") or "").split(";"):
                    if w.strip() and not cin(w,deniedw) and not is_withheld(w): deniedw.append(w.strip())  # a withheld ID is held, never published (#3.3); the register's spelling is kept, compared canonically (#1.3)
            briefed=[]; screened=0
            for i,r in restricted:
                for t in topics(r):
                    if is_withheld(t) or hits(t): briefed.append(WITHHELD); screened+=1; continue  # tripwire hold already raised by scan_rows (#4.3)
                    if names_other(t,terms,own,own_ids):
                        briefed.append(TOPIC_WITHHELD); screened+=1
                        holds.append({"hold_id":"HOLD-BRIEFING-TOPIC-"+hashlib.sha256(strip_cf(t).encode()).hexdigest()[:12],"path":f"raw/ethical-wall-register.csv row {i}.briefing_topics","reason":"briefing topic names another client, matter or identifying detail; withheld from the pack","source":ENGINE,"confidence":.97,"citation":"confidentiality-and-ethical-wall-rules.md #3.1,#3.2"}); continue
                    briefed.append(t)
            if screened: esc.append(f"{screened} wall briefing topic(s) withheld from the pack; Risk/Conflicts brief the joiner directly (confidentiality-and-ethical-wall-rules.md #3.2)")
            may.append({"item":next((x for x in (e.get("client_name"),e.get("matter_id")) if (x or "").strip()),"this client or matter"),"type":"client_or_matter","restriction":("may not access or discuss: "+"; ".join(dict.fromkeys(briefed))) if briefed else "restricted subject matter - confirm specifics with Risk/Conflicts before starting work","citation":f"{cit}; confidentiality-and-ethical-wall-rules.md #2.3,#3.1,#3.2"})
        elif unknown:
            status,reason,cit=hold_status("HOLD-UNKNOWN-WALL-STATUS","raw/ethical-wall-register.csv.status","unknown wall status value (not repeated); treated as hold","#2.2")
        elif not named_clear:
            status,reason,cit=hold_status("HOLD-UNKNOWN-WALL-STATUS","raw/ethical-wall-register.csv","no wall register row clears this joiner for this client or matter","#2.2")
        else: cit="; ".join(row_cite(r) for r in named_clear)
    if ws is not None:
        dupw=[] if ws.duplicate_columns else duplicate_rows(ws,"workspace_id")  # keyed by workspace_id: a repeat holds, never last-wins (#1.3)
        if ws.duplicate_columns:
            holds.append({"hold_id":"HOLD-MALFORMED-WORKSPACE-INVENTORY","path":"raw/workspace-inventory.csv header","reason":"workspace inventory "+DUPLICATE_HEADER_REASON+"; no access is requested","source":ENGINE,"confidence":.99,"citation":"workspace-inventory-rules.md #1.3"})
        elif dupw:
            holds.append({"hold_id":"HOLD-MALFORMED-WORKSPACE-INVENTORY","path":"raw/workspace-inventory.csv rows "+", ".join(map(str,dupw))+" workspace_id","reason":"workspace inventory workspace_id "+DUPLICATE_ID_REASON+"; no access is requested","source":ENGINE,"confidence":.99,"citation":"workspace-inventory-rules.md #1.3"})
        # Every inventory cell is screened, for instructions and for other clients, from the rows AS READ - IDs,
        # types, permissions, classifications and citations as well as names - before any decision uses them, and
        # before an unusable header or a repeated ID empties the collection the decisions use: an inventory that
        # is not used is still screened and its flagged cells held. A withheld identifier is never a decision key (#1.3, #3.3, #4.3).
        holds+=scan_rows(ws,"raw/workspace-inventory.csv")
        ih=screen_csv_other(ws,"raw/workspace-inventory.csv",terms,ENGINE)
        if ih: holds+=ih; esc.append(other_escalation(len(ih)))
        if ws.duplicate_columns or dupw: ws=Rows()
        for i,w in enumerate(ws,2):
            nm=w.get("name") or ""; wid=w.get("workspace_id")
            if (hits(nm) or is_withheld(nm)) and wid and not is_withheld(wid) and not cin(wid,withheld_names): withheld_names.append(wid)
    # Upstream holds are supplied content: another client's name or steering text in them never travels (#3.3, #4.3).
    up,uh=screen_holds(up,terms,ENGINE,"matched.holds")
    if any(h["hold_id"].startswith("HOLD-OTHER-CLIENT-") for h in uh): esc.append(other_escalation(sum(h["hold_id"].startswith("HOLD-OTHER-CLIENT-") for h in uh)))
    holds=dedup_holds(up+holds+uh)
    if holds and status=="clear": status="hold"; reason="source holds require review before knowledge/access release"; cit="confidentiality-and-ethical-wall-rules.md #4.1"
    odd=[]
    for i,w in enumerate(ws or [],2):
        wid=w.get("workspace_id")
        if is_withheld(wid): continue  # never requested (access_checklist: invalid row) and never published
        conf=client_confidential(w.get("data_classification")); dep=depends_on_knowledge(w.get("depends_on_knowledge"))  # blank/unknown fail closed (workspace-inventory-rules.md #2.3)
        if not cin(w.get("data_classification"),KNOWN_CLASSIFICATIONS) or canon_text(w.get("depends_on_knowledge")) not in TRUE_VALUES|FALSE_VALUES: odd.append(str(i))
        if status=="denied" and cin(wid,deniedw):
            name=wid if cin(wid,withheld_names) or not (w.get("name") or "").strip() else w["name"]
            may.append({"item":name,"type":"workspace","restriction":"workspace restricted by ethical-wall register","citation":f"{w.get('citation') or 'raw/workspace-inventory.csv'}; confidentiality-and-ethical-wall-rules.md #2.3; workspace-inventory-rules.md #2.2"})
        elif status in {"denied","hold"} and (conf or dep) and not cin(wid,heldw): heldw.append(wid)
    if odd: esc.append(f"Workspace inventory row(s) {', '.join(odd)} have a blank or unrecognised data_classification/depends_on_knowledge; treated as client-confidential and knowledge-dependent (workspace-inventory-rules.md #2.3)")
    allowed=[] if status in {"denied","hold"} else p.get("prior_knowledge_candidates",[])
    p["wall_decision"]={"status":status,"reason":reason,"allowed_knowledge_ids":[x.get("knowledge_id") for x in allowed],"denied_knowledge_ids":deniedk,"denied_workspace_ids":deniedw,"held_workspace_ids":heldw,"name_withheld_workspace_ids":withheld_names,"may_not_access_discuss":may,"source":ENGINE,"confidence":.98 if status!="hold" else .8,"citation":cit}
    kd=p.get("knowledge_digest",{})
    if status=="clear": kd["items"]=allowed
    elif status=="denied": kd.update({"status":"denied_by_wall","items":[],"denied_items":deniedk})
    else: kd.update({"status":"hold","items":[]})
    p["knowledge_digest"]=kd; p["holds"]=holds; return p
def main():
    ap=ArgParser(); ap.add_argument("--matched",required=True); ap.add_argument("--wall-register",required=True); ap.add_argument("--workspace-inventory",required=True); ap.add_argument("--out",required=True); ap.add_argument("--generated-at",required=True); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    p=load_json(a.matched,"matched input"); check_matched(p); set_trusted_domains((p.get("engagement") or {}).get("trusted_domains"))
    p=govern(p,a.wall_register,a.workspace_inventory)
    p.setdefault("provenance",{}).setdefault("engines",[]).append(f"wall_check/{VERSION}"); p["provenance"]["generated_at"]=ts
    check_contract(p,"governed","governed"); dump_json(a.out,p,"governed output")  # the document written is held to the same contract (#1.3)
if __name__=="__main__": guard(main)
