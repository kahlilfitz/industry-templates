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
REGISTER_COLUMNS=("person","client_name","matter_id","status")  # confidentiality-and-ethical-wall-rules.md #2.1
KNOWN_CLASSIFICATIONS={"client_confidential","confidential","restricted","internal","public"}  # workspace-inventory-rules.md #2.3
TOPIC_WITHHELD="[briefing topic withheld - it names another client or matter, Risk/Conflicts brief the joiner directly]"  # #3.2
OTHER_CLIENTS_SCREENED=True  # confidentiality-and-ethical-wall-rules.md #3.3
ALLOW_CAPS={"sharepoint","teams","planner","sow","gdpr","pci","pii","hipaa","api","it","risk","conflicts","knowledge","repository","channel","engagement","delivery","client","q1","q2","q3","q4","i"}
def k(v): return (v or "").strip().lower()
def applies(r,e,j):
    # Every populated field must match; blank person = engagement-wide row; a row must name this client or matter.
    p,c,m=k(r.get("person")),k(r.get("client_name")),k(r.get("matter_id"))
    if p and p!=k(j.get("person")): return False
    if c and c!=k(e.get("client_name")): return False
    if m and m!=k(e.get("matter_id")): return False
    return bool(c or m)
def row_cite(r): return r.get("citation") or "raw/ethical-wall-register.csv"
def topics(r): return [x.strip() for x in (r.get("briefing_topics") or "").split(";") if x.strip()]
def cap_runs(text):
    for m in re.finditer(r"[A-Z][A-Za-z0-9&'.-]*(?:\s+(?:&\s+)?[A-Z][A-Za-z0-9&'.-]*)*",text or ""):
        start=m.start()==0 or bool(re.search(r"[.;:!?]\s*$",text[:m.start()])); yield m.group(0).strip(" .'-"),start
def other_names(rows,e,own):
    """Every other client's identity in the register: other rows' client_name/matter_id and proper-noun runs in
    restriction free text (confidentiality-and-ethical-wall-rules.md #3.2,#3.3)."""
    names=[]
    for r in rows:
        if r.get("client_name") and k(r.get("client_name"))!=k(e.get("client_name")): names.append(r["client_name"].strip())
        if r.get("matter_id") and k(r.get("matter_id"))!=k(e.get("matter_id")): names.append(r["matter_id"].strip())
        for run,start in cap_runs(r.get("restriction") or ""):
            ws=words(run)
            if not ws or ws<=own|GENERIC|ALLOW_CAPS or (start and len(run.split())==1): continue
            names.append(run)
    return names
def names_other(text,terms,own,own_ids):
    """Briefing topics get the strictest screen: known identities, any other matter-like ID and any capitalised name
    that is not this engagement's own (#3.2)."""
    if names_client(text,terms): return True
    if any(x.lower() not in own_ids for x in re.findall(r"\b[A-Za-z]{2,}(?:-[A-Za-z0-9]+)*-\d{2,}[A-Za-z0-9-]*\b",text or "")): return True
    for run,start in cap_runs(text):
        ws=words(run)
        if not ws or ws<=own|ALLOW_CAPS or (start and len(run.split())==1): continue
        return True
    return False
def check_matched(p):
    need(isinstance(p,dict),f"matched input must be a JSON object, got {type(p).__name__}; fail closed")
    if p.get("contract_version")!=CONTRACT_VERSION: raise InputError(f"expected contract {CONTRACT_VERSION} in matched input")
    if "prior_knowledge_candidates" not in p or "knowledge_digest" not in p: raise InputError("matched input has no prior_knowledge_candidates/knowledge_digest; run knowledge_match first; fail closed")
    field(p,"knowledge_digest","obj","matched",required=True); check_contract(p,"matched")  # confidentiality-and-ethical-wall-rules.md #1.3
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--matched",required=True); ap.add_argument("--wall-register",required=True); ap.add_argument("--workspace-inventory",required=True); ap.add_argument("--out",required=True); ap.add_argument("--generated-at",required=True); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    p=load_json(a.matched); check_matched(p)
    rows=read_csv(a.wall_register,False); ws=read_csv(a.workspace_inventory,False); holds=list(p.get("holds",[])); deniedk=[]; deniedw=[]; heldw=[]; may=[]; withheld_names=[]; j=p.get("joiner") or {}; e=p.get("engagement") or {}; esc=p.setdefault("escalations",[])
    status="clear"; reason="wall register marks joiner clear for this client/matter"; cit="confidentiality-and-ethical-wall-rules.md #2.2"
    own=words(e.get("client_name"),e.get("matter_id"),e.get("engagement_id"),e.get("title"),*(e.get("affiliates") or []),j.get("person"),*[r.get("person") for r in p.get("team_roster",[])],*(p.get("scope_summary") or {}).get("systems",[])); own_ids={k(e.get("matter_id")),k(e.get("engagement_id"))}-{""}
    def hold_status(hid,path,why,rule):
        holds.append({"hold_id":hid,"path":path,"reason":why,"source":ENGINE,"confidence":.99,"citation":f"confidentiality-and-ethical-wall-rules.md {rule}"}); return "hold",why,f"confidentiality-and-ethical-wall-rules.md {rule}"
    terms=[]
    if not k(j.get("person")):
        status,reason,cit=hold_status("HOLD-NO-JOINER","scope.joiner","no joiner identified; wall status cannot be determined","#2.2")
    elif rows is None:
        status,reason,cit=hold_status("HOLD-MISSING-WALL-REGISTER",a.wall_register,"missing ethical-wall register","#2.1")
    elif missing_columns(rows,REGISTER_COLUMNS):
        status,reason,cit=hold_status("HOLD-MALFORMED-WALL-REGISTER","raw/ethical-wall-register.csv header",f"ethical-wall register is missing required column(s): {', '.join(missing_columns(rows,REGISTER_COLUMNS))}","#2.1")
    else:
        if rows.malformed: hold_status("HOLD-MALFORMED-WALL-REGISTER","raw/ethical-wall-register.csv rows "+", ".join(map(str,rows.malformed)),"ethical-wall register row(s) carry more fields than the header","#2.1")
        holds+=scan_rows(rows,"raw/ethical-wall-register.csv"); terms=client_terms(other_names(rows,e,own),own)
        p,oh=screen_other(p,terms,ENGINE,"matched.")  # every text field, not only the briefing (#3.3)
        if oh: holds+=oh; esc=p.setdefault("escalations",[]); esc.append(other_escalation(len(oh)))
        j=p.get("joiner") or {}; e=p.get("engagement") or {}
        matches=[(i,r) for i,r in enumerate(rows,2) if applies(r,e,j)]
        restricted=[(i,r) for i,r in matches if k(r.get("status")) in RESTRICT]
        unknown=[r for i,r in matches if k(r.get("status")) not in RESTRICT|CLEAR]
        named_clear=[r for i,r in matches if k(r.get("status")) in CLEAR and k(r.get("person"))]
        if restricted:
            status="denied"; reason="joiner restricted by ethical-wall register; restriction details are held by Risk/Conflicts (need-to-know)"; cit="; ".join(row_cite(r) for i,r in restricted)
            deniedk=[x.get("knowledge_id") for x in p.get("prior_knowledge_candidates",[])]
            for i,r in restricted:
                for w in (r.get("restricted_workspaces") or "").split(";"):
                    if w.strip() and w.strip() not in deniedw: deniedw.append(w.strip())
            briefed=[]; screened=0
            for i,r in restricted:
                for t in topics(r):
                    if hits(t): briefed.append(WITHHELD); screened+=1; continue  # tripwire hold already raised by scan_rows (#4.3)
                    if names_other(t,terms,own,own_ids):
                        briefed.append(TOPIC_WITHHELD); screened+=1
                        holds.append({"hold_id":"HOLD-BRIEFING-TOPIC-"+hashlib.sha256(strip_cf(t).encode()).hexdigest()[:12],"path":f"raw/ethical-wall-register.csv row {i}.briefing_topics","reason":"briefing topic names another client, matter or identifying detail; withheld from the pack","source":ENGINE,"confidence":.97,"citation":"confidentiality-and-ethical-wall-rules.md #3.1,#3.2"}); continue
                    briefed.append(t)
            if screened: esc.append(f"{screened} wall briefing topic(s) withheld from the pack; Risk/Conflicts brief the joiner directly (confidentiality-and-ethical-wall-rules.md #3.2)")
            may.append({"item":e.get("client_name") or e.get("matter_id"),"type":"client_or_matter","restriction":("may not access or discuss: "+"; ".join(dict.fromkeys(briefed))) if briefed else "restricted subject matter - confirm specifics with Risk/Conflicts before starting work","citation":f"{cit}; confidentiality-and-ethical-wall-rules.md #2.3,#3.1,#3.2"})
        elif unknown:
            vals=sorted({k(r.get("status")) or "blank" for r in unknown})
            status,reason,cit=hold_status("HOLD-UNKNOWN-WALL-STATUS","raw/ethical-wall-register.csv.status",f"unknown wall status value: {', '.join(vals)}","#2.2")
        elif not named_clear:
            status,reason,cit=hold_status("HOLD-UNKNOWN-WALL-STATUS","raw/ethical-wall-register.csv","no wall register row clears this joiner for this client or matter","#2.2")
        else: cit="; ".join(row_cite(r) for r in named_clear)
    if ws is not None:
        holds+=scan_rows(ws,"raw/workspace-inventory.csv")
        for i,w in enumerate(ws,2):
            nm=w.get("name") or ""
            if names_client(nm,terms): holds.append(other_hold(f"raw/workspace-inventory.csv row {i}.name",nm,ENGINE))
            if (hits(nm) or nm==WITHHELD or names_client(nm,terms)) and w.get("workspace_id") and w["workspace_id"] not in withheld_names: withheld_names.append(w["workspace_id"])
    holds=dedup_holds(holds)
    if holds and status=="clear": status="hold"; reason="source holds require review before knowledge/access release"; cit="confidentiality-and-ethical-wall-rules.md #4.1"
    odd=[]
    for i,w in enumerate(ws or [],2):
        wid=w.get("workspace_id"); conf=client_confidential(w.get("data_classification")); dep=depends_on_knowledge(w.get("depends_on_knowledge"))  # blank/unknown fail closed (workspace-inventory-rules.md #2.3)
        if k(w.get("data_classification")) not in KNOWN_CLASSIFICATIONS or k(w.get("depends_on_knowledge")) not in TRUE_VALUES|FALSE_VALUES: odd.append(str(i))
        if status=="denied" and wid in deniedw:
            name=wid if wid in withheld_names else (w.get("name") or wid)
            may.append({"item":name,"type":"workspace","restriction":"workspace restricted by ethical-wall register","citation":f"{w.get('citation') or 'raw/workspace-inventory.csv'}; confidentiality-and-ethical-wall-rules.md #2.3; workspace-inventory-rules.md #2.2"})
        elif status in {"denied","hold"} and (conf or dep) and wid not in heldw: heldw.append(wid)
    if odd: esc.append(f"Workspace inventory row(s) {', '.join(odd)} have a blank or unrecognised data_classification/depends_on_knowledge; treated as client-confidential and knowledge-dependent (workspace-inventory-rules.md #2.3)")
    allowed=[] if status in {"denied","hold"} else p.get("prior_knowledge_candidates",[])
    p["wall_decision"]={"status":status,"reason":reason,"allowed_knowledge_ids":[x.get("knowledge_id") for x in allowed],"denied_knowledge_ids":deniedk,"denied_workspace_ids":deniedw,"held_workspace_ids":heldw,"name_withheld_workspace_ids":withheld_names,"may_not_access_discuss":may,"source":ENGINE,"confidence":.98 if status!="hold" else .8,"citation":cit}
    kd=p.get("knowledge_digest",{})
    if status=="clear": kd["items"]=allowed
    elif status=="denied": kd.update({"status":"denied_by_wall","items":[],"denied_items":deniedk})
    else: kd.update({"status":"hold","items":[]})
    p["knowledge_digest"]=kd; p["holds"]=holds; p.setdefault("provenance",{}).setdefault("engines",[]).append(f"wall_check/{VERSION}"); p["provenance"]["generated_at"]=ts; dump_json(a.out,p)
if __name__=="__main__": guard(main)
