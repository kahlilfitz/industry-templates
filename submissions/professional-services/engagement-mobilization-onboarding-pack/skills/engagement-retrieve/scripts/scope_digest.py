#!/usr/bin/env python3
import argparse, os, re
from safety_text import *
ENGINE="engine:scope_digest"; STAFF="ps.engagement-staffing-bench-match.v1"  # role-access-matrix.md #3.1
SOW_CONTROLS_CONFLICTS=True  # confidentiality-and-ethical-wall-rules.md #1.2
CONFIRMED_ROSTER_CONTROLS=True  # role-access-matrix.md #4.1
INELIGIBLE_STAFFING_EXCLUDED=True  # role-access-matrix.md #3.2
VERDICTS={"eligible","ineligible","conflicted","blocked","needs_review"}  # role-access-matrix.md #3.2-#3.4
INELIGIBLE={"ineligible","conflicted","blocked"}  # role-access-matrix.md #3.2
RANK={"eligible":0,"needs_review":2,"unrecognised":2.5,"ineligible":3,"conflicted":3,"blocked":3}
ONBOARDING={"active","joining","mid-engagement joiner","new_joiner"}; JOINING={"joining","mid-engagement joiner","new_joiner"}  # role-access-matrix.md #4.2,#4.4
ROSTER_COLUMNS=("person","role","onboarding_status","assignment_status")
def fld(t,n):
    m=re.search(rf"^{re.escape(n)}:\s*(.*)$",t,re.I|re.M); return m.group(1).strip() if m else ""
def lst(v): return split_items(v)
def one(v): return WITHHELD if hits(v) else v
def items(line):
    # Flagged SOW/letter text never travels (#4.3): withhold each flagged item; if the line only trips the wire as a
    # whole, withhold every item from it.
    xs=lst(line)
    if not hits(line): return xs
    out=[WITHHELD if hits(x) else x for x in xs]
    return out if WITHHELD in out else [WITHHELD]
def validate_staffing(st):
    need(isinstance(st,dict),f"staffing adapter expected a JSON object, got {type(st).__name__}; fail closed")
    if st.get("contract_version")!=STAFF: raise InputError(f"staffing adapter expected contract {STAFF}, got {st.get('contract_version')!r}")
    W="upstream/staffing"
    field(st,"governed_roles","objlist",W,required=True)
    eng=field(st,"engagement","obj",W,default={})
    for k in ("engagement_id","client_name"): field(eng,k,"str",W+".engagement",nullable=True)
    field(eng,"affiliates","strlist",W+".engagement",nullable=True)
    for e in field(st,"escalations","list",W,default=[]): esc_text(e,W+".escalations")
    for i,r in enumerate(st["governed_roles"]):
        w=f"{W}.governed_roles[{i}]"; field(r,"role_title","str",w,nullable=True)
        for key in ("candidate_slate","recommended_candidates"):
            for j,c in enumerate(field(r,key,"objlist",w,default=[])):
                cw=f"{w}.{key}[{j}]"; field(c,"candidate_name","str",cw,nullable=True); field(c,"confidence","num01",cw); field(c,"fit_score","num",cw,nullable=True); field(c,"citation","str",cw,nullable=True)
                el=field(c,"eligibility","obj",cw,nullable=True)
                if el: field(el,"blocking_rule","str",cw+".eligibility",nullable=True); field(el,"citation","str",cw+".eligibility",nullable=True)
def statuses(st):
    s={}; p=[]
    for r in st["governed_roles"]:
        rt=r.get("role_title") or "role"
        for c in r.get("candidate_slate",[]):
            if not c.get("candidate_name"): continue
            el=c.get("eligibility") or {}; v=el.get("verdict")
            v=v.strip().lower() if isinstance(v,str) else None
            if v not in VERDICTS: v="unrecognised"  # blank, null or unknown verdicts fail closed (#3.4)
            s.setdefault(c["candidate_name"].lower(),[]).append({"role_title":rt,"verdict":v,"blocking_rule":el.get("blocking_rule"),"confidence":c.get("confidence",.9),"citation":el.get("citation") or c.get("citation") or "staffing"})
        for c in r.get("recommended_candidates",[]):
            if c.get("candidate_name"): p.append({"candidate_name":c["candidate_name"],"role_title":rt,"fit_score":c.get("fit_score"),"assignment_status":"proposed_not_assigned","source":"adapter:staffing-slate","confidence":c.get("confidence",.9),"citation":c.get("citation") or "staffing recommended_candidates"})
    return s,p
def verdict_for(entries,role):
    # Prefer the Scenario 02 verdict for the confirmed role; otherwise the most restrictive verdict across roles.
    same=[x for x in entries if (x.get("role_title") or "").strip().lower()==(role or "").strip().lower()] or entries
    return max(same,key=lambda x:RANK.get(x.get("verdict"),2.5),default={})
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--raw-dir",required=True); ap.add_argument("--staffing",required=True); ap.add_argument("--confirmed-roster",required=True); ap.add_argument("--out",required=True); ap.add_argument("--generated-at",required=True); ap.add_argument("--scenario",default=""); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    sowp=os.path.join(a.raw_dir,"sow-extract.md")
    if not os.path.exists(sowp): raise InputError("missing required SOW extract: raw/sow-extract.md")
    sow=read_text(sowp); letter=read_text(os.path.join(a.raw_dir,"engagement-letter-extract.md")); pursuit=read_text(os.path.join(a.raw_dir,"pursuit-record.md")); rows=read_csv(a.confirmed_roster); st=load_json(a.staffing)
    miss=missing_columns(rows,ROSTER_COLUMNS)
    if miss: raise InputError(f"confirmed roster is missing required column(s): {', '.join(miss)}; fail closed")
    if rows.malformed: raise InputError(f"confirmed roster row(s) {', '.join(map(str,rows.malformed))} have more fields than the header; fail closed")
    validate_staffing(st)
    h1,sow=scan_lines(sow,"raw/sow-extract.md"); h2,letter=scan_lines(letter,"raw/engagement-letter-extract.md"); h3,pursuit=scan_lines(pursuit,"raw/pursuit-record.md")
    holds=h1+h2+h3+scan_rows(rows,"raw/confirmed-roster.csv")+scan(st,"upstream/staffing")
    smap,prop=statuses(st); roster=[]; excl=[]; names=set(); joiner={}; unconfirmed=[]; joiners=[]; esc=[esc_text(e,"upstream/staffing.escalations") for e in st.get("escalations",[])]
    for i,r in enumerate(rows,2):
        name=(r.get("person") or "").strip()
        if not name: continue
        names.add(name.lower()); ss=verdict_for(smap.get(name.lower(),[]),r.get("role",""))
        if ss.get("verdict") in INELIGIBLE:
            excl.append({"person":name,"role":r.get("role",""),"reason":f"{ss.get('verdict')} in Scenario 02 for {ss.get('role_title')}; independence/conflict details stay in the staffing record (need-to-know)","blocking_rule":ss.get("blocking_rule"),"source":"adapter:staffing-slate","confidence":ss.get("confidence",.95),"citation":ss.get("citation","role-access-matrix.md #3.2")}); continue
        if (r.get("assignment_status") or "").strip().lower()!="confirmed": unconfirmed.append(name); continue  # role-access-matrix.md #4.1
        item={"person":name,"role":r.get("role",""),"responsibilities":lst(r.get("responsibilities","")),"point_of_contact":r.get("point_of_contact","Engagement manager"),"onboarding_status":r.get("onboarding_status",""),"assignment_status":"confirmed","source":"raw:confirmed-roster.csv","confidence":.97,"citation":r.get("citation") or "raw/confirmed-roster.csv"}
        if ss.get("verdict")=="unrecognised":
            item["staffing_review"]={"verdict":"unrecognised","blocking_rule":None,"citation":"role-access-matrix.md #3.4"}
            holds.append({"hold_id":"HOLD-UNRECOGNISED-STAFFING-VERDICT","path":f"upstream/staffing candidate_slate[{name}].eligibility.verdict","reason":"blank, null or unrecognised Scenario 02 verdict for a confirmed roster member","source":ENGINE,"confidence":.99,"citation":"role-access-matrix.md #3.4"})
            esc.append(f"Confirmed roster row {name} has a blank or unrecognised Scenario 02 verdict; held for the engagement manager (role-access-matrix.md #3.4)")
        elif ss.get("verdict") not in (None,"eligible"): item["staffing_review"]={"verdict":ss.get("verdict"),"blocking_rule":ss.get("blocking_rule"),"citation":ss.get("citation")}; esc.append(f"Confirmed roster row {name} is {ss.get('verdict')} in Scenario 02 for {ss.get('role_title')}; confirm with the engagement manager before onboarding ({ss.get('citation')}; role-access-matrix.md #3.3)")
        onb=(item["onboarding_status"] or "").strip().lower()
        if onb not in ONBOARDING:
            holds.append({"hold_id":"HOLD-UNKNOWN-ONBOARDING-STATUS","path":f"raw/confirmed-roster.csv row {i}.onboarding_status","reason":"blank or unrecognised onboarding_status; joiner status cannot be determined","source":ENGINE,"confidence":.99,"citation":"role-access-matrix.md #4.4"})
            esc.append(f"Roster row {i} has a blank or unrecognised onboarding_status; held until the engagement manager confirms whether {name} is joining (role-access-matrix.md #4.4)")
        roster.append(item)
        if onb in JOINING:
            joiners.append(name)
            if not joiner: joiner=dict(item)
    prop=[p for p in prop if p["candidate_name"].lower() not in names]
    exclusions=items(fld(sow,"Exclusions")); pt=pursuit.lower()
    for e in exclusions:
        if e!=WITHHELD and e.lower().split(" - ")[0] in pt and re.search(r"\b(?:include|included|request|requested|add|added|reuse)\b",pt): esc.append(f"SOW exclusion controls over pursuit conflict: '{e}' (confidentiality-and-ethical-wall-rules.md #1.2)"); break
    for n in unconfirmed: esc.append(f"Roster row for {n} has no confirmed assignment_status; treated as not assigned (role-access-matrix.md #4.1)")
    if not joiners: esc.append("No joining team member found in the confirmed roster; wall check and access checklist will hold (confidentiality-and-ethical-wall-rules.md #2.2)")
    elif len(joiners)>1: esc.append(f"Multiple joiners found ({', '.join(joiners)}); this pack covers {joiners[0]} only - run again per joiner (role-access-matrix.md #4.1)")
    for x in excl: esc.append(f"Confirmed roster row excluded: {x['person']} is ineligible/conflicted in Scenario 02 ({x['citation']})")
    holds=dedup_holds(holds)
    eng=st.get("engagement") or {}; sow_client=fld(sow,"Client"); sow_eid=fld(sow,"Engagement ID")
    # A staffing file for another client or engagement is another client's data: hold it and screen its identity out
    # of every output (confidentiality-and-ethical-wall-rules.md #3.3).
    mism=[k_ for k_,mine in (("client_name",sow_client),("engagement_id",sow_eid)) if eng.get(k_) and mine and norm(eng[k_])!=norm(mine)]
    if mism:
        holds.append({"hold_id":"HOLD-STAFFING-ENGAGEMENT-MISMATCH","path":"upstream/staffing.engagement."+"/".join(mism),"reason":"staffing input names a different client or engagement than the SOW (name not repeated); staffing evidence not trusted","source":ENGINE,"confidence":.99,"citation":"confidentiality-and-ethical-wall-rules.md #3.3; role-access-matrix.md #3.1"})
        esc.append("Staffing input is for a different client or engagement than the SOW; staffing evidence held for the engagement manager (confidentiality-and-ethical-wall-rules.md #3.3)")
    affiliates=[x for x in (eng.get("affiliates") or []) if x.strip()] if not mism else []
    if any(h["reason"].startswith("embedded_instruction") for h in holds): esc.append(f"{sum(h['reason'].startswith('embedded_instruction') for h in holds)} source field(s) held for embedded instruction review (confidentiality-and-ethical-wall-rules.md #4.1-#4.5)")
    body={"engagement":{"engagement_id":one(fld(sow,"Engagement ID")) or eng.get("engagement_id") or "","matter_id":one(fld(sow,"Matter ID")),"title":one(fld(sow,"Title")),"client_name":one(sow_client) or ("" if mism else eng.get("client_name")) or "","affiliates":affiliates,"sector":one(fld(pursuit,"Sector")),"region":one(fld(pursuit,"Region")),"source":ENGINE,"confidence":.95,"citation":"raw/sow-extract.md header; raw/pursuit-record.md context"},"joiner":joiner,"scope_summary":{"objectives":items(fld(sow,"Objectives")),"in_scope":items(fld(sow,"In scope")),"exclusions":exclusions,"deliverables":items(fld(sow,"Deliverables")),"key_dates":items(fld(sow,"Key dates")),"systems":items(fld(sow,"Systems")),"first_week_focus":items(fld(sow,"First-week")),"source":ENGINE,"confidence":.94,"citation":"raw/sow-extract.md; confidentiality-and-ethical-wall-rules.md #1.2"},"engagement_terms":{"confidentiality_terms":items(fld(letter,"Confidentiality")),"ethical_wall_terms":items(fld(letter,"Ethical walls")),"source":"raw:engagement-letter-extract.md","confidence":.93,"citation":"raw/engagement-letter-extract.md"},"team_roster":roster,"proposed_staffing":prop,"staffing_exclusions":excl,"escalations":esc}
    body=redact(body)
    if mism:
        own=words(sow_client,sow_eid,fld(sow,"Matter ID"),fld(sow,"Title"))
        body,oh=screen_other(body,client_terms([eng.get("client_name"),eng.get("engagement_id")],own),ENGINE,"scope.")
        if oh: holds=dedup_holds(holds+oh); body["escalations"].append(other_escalation(len(oh)))
    out={"contract_version":CONTRACT_VERSION,"run_metadata":{"generated_at":ts,"demo_scenario":a.scenario},**body,"holds":holds,"provenance":{"engines":[f"scope_digest/{VERSION}"],"generated_at":ts,"sources":["raw/sow-extract.md","raw/engagement-letter-extract.md","raw/pursuit-record.md","raw/confirmed-roster.csv","upstream/staffing"]}}
    dump_json(a.out,out)
if __name__=="__main__": guard(main)
