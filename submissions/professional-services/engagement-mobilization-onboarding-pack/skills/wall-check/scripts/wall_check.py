#!/usr/bin/env python3
import argparse
from safety_text import *
ENGINE="engine:wall_check"; CLEAR={"clear","cleared"}  # confidentiality-and-ethical-wall-rules.md #2.2
RESTRICT={"restricted","walled","conflicted","deny"}  # confidentiality-and-ethical-wall-rules.md #2.3
MISSING_REGISTER_HOLDS=True  # confidentiality-and-ethical-wall-rules.md #2.1
UNKNOWN_STATUS_HOLDS=True  # confidentiality-and-ethical-wall-rules.md #2.2
CLEAR_NEEDS_NAMED_PERSON=True  # confidentiality-and-ethical-wall-rules.md #2.2
FREE_TEXT_NOT_BRIEFED=True  # confidentiality-and-ethical-wall-rules.md #3.1
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
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--matched",required=True); ap.add_argument("--wall-register",required=True); ap.add_argument("--workspace-inventory",required=True); ap.add_argument("--out",required=True); ap.add_argument("--generated-at",required=True); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    p=load_json(a.matched)
    if p.get("contract_version")!=CONTRACT_VERSION: raise InputError(f"expected contract {CONTRACT_VERSION} in matched input")
    rows=read_csv(a.wall_register,False); ws=read_csv(a.workspace_inventory,False); holds=list(p.get("holds",[])); deniedk=[]; deniedw=[]; heldw=[]; may=[]; j=p.get("joiner") or {}; e=p.get("engagement",{})
    status="clear"; reason="wall register marks joiner clear for this client/matter"; cit="confidentiality-and-ethical-wall-rules.md #2.2"
    def hold_status(hid,path,why,rule):
        holds.append({"hold_id":hid,"path":path,"reason":why,"source":ENGINE,"confidence":.99,"citation":f"confidentiality-and-ethical-wall-rules.md {rule}"}); return "hold",why,f"confidentiality-and-ethical-wall-rules.md {rule}"
    if not k(j.get("person")):
        status,reason,cit=hold_status("HOLD-NO-JOINER","scope.joiner","no joiner identified; wall status cannot be determined","#2.2")
    elif rows is None:
        status,reason,cit=hold_status("HOLD-MISSING-WALL-REGISTER",a.wall_register,"missing ethical-wall register","#2.1")
    else:
        holds+=scan_rows(rows,"raw/ethical-wall-register.csv"); matches=[r for r in rows if applies(r,e,j)]
        restricted=[r for r in matches if k(r.get("status")) in RESTRICT]
        unknown=[r for r in matches if k(r.get("status")) not in RESTRICT|CLEAR]
        named_clear=[r for r in matches if k(r.get("status")) in CLEAR and k(r.get("person"))]
        if restricted:
            status="denied"; reason="joiner restricted by ethical-wall register; restriction details are held by Risk/Conflicts (need-to-know)"; cit="; ".join(row_cite(r) for r in restricted)
            deniedk=[x.get("knowledge_id") for x in p.get("prior_knowledge_candidates",[])]
            for r in restricted:
                for w in (r.get("restricted_workspaces") or "").split(";"):
                    if w.strip() and w.strip() not in deniedw: deniedw.append(w.strip())
            briefed=[t for r in restricted for t in topics(r)]
            may.append({"item":e.get("client_name") or e.get("matter_id"),"type":"client_or_matter","restriction":("may not access or discuss: "+"; ".join(briefed)) if briefed else "restricted subject matter - confirm specifics with Risk/Conflicts before starting work","citation":f"{cit}; confidentiality-and-ethical-wall-rules.md #2.3,#3.1"})
        elif unknown:
            vals=sorted({k(r.get("status")) or "blank" for r in unknown})
            status,reason,cit=hold_status("HOLD-UNKNOWN-WALL-STATUS","raw/ethical-wall-register.csv.status",f"unknown wall status value: {', '.join(vals)}","#2.2")
        elif not named_clear:
            status,reason,cit=hold_status("HOLD-UNKNOWN-WALL-STATUS","raw/ethical-wall-register.csv","no wall register row clears this joiner for this client or matter","#2.2")
        else: cit="; ".join(row_cite(r) for r in named_clear)
    if ws is not None:
        holds+=scan_rows(ws,"raw/workspace-inventory.csv")
    seen=set(); holds=[h for h in holds if (h.get("hold_id"),h.get("path"),h.get("reason")) not in seen and not seen.add((h.get("hold_id"),h.get("path"),h.get("reason")))]
    if holds and status=="clear": status="hold"; reason="source holds require review before knowledge/access release"; cit="confidentiality-and-ethical-wall-rules.md #4.1"
    for w in ws or []:
        wid=w.get("workspace_id"); conf=k(w.get("data_classification"))=="client_confidential"; dep=k(w.get("depends_on_knowledge")) in {"true","yes","1"}
        if status=="denied" and wid in deniedw:
            may.append({"item":w.get("name") or wid,"type":"workspace","restriction":"workspace restricted by ethical-wall register","citation":f"{w.get('citation') or 'raw/workspace-inventory.csv'}; confidentiality-and-ethical-wall-rules.md #2.3; workspace-inventory-rules.md #2.2"})
        elif status in {"denied","hold"} and (conf or dep) and wid not in heldw: heldw.append(wid)
    allowed=[] if status in {"denied","hold"} else p.get("prior_knowledge_candidates",[])
    p["wall_decision"]={"status":status,"reason":reason,"allowed_knowledge_ids":[x.get("knowledge_id") for x in allowed],"denied_knowledge_ids":deniedk,"denied_workspace_ids":deniedw,"held_workspace_ids":heldw,"may_not_access_discuss":may,"source":ENGINE,"confidence":.98 if status!="hold" else .8,"citation":cit}
    kd=p.get("knowledge_digest",{})
    if status=="clear": kd["items"]=allowed
    elif status=="denied": kd.update({"status":"denied_by_wall","items":[],"denied_items":deniedk})
    else: kd.update({"status":"hold","items":[]})
    p["knowledge_digest"]=kd; p["holds"]=holds; p.setdefault("provenance",{}).setdefault("engines",[]).append(f"wall_check/{VERSION}"); p["provenance"]["generated_at"]=ts; dump_json(a.out,p)
if __name__=="__main__": guard(main)