#!/usr/bin/env python3
import argparse, os, re
from safety_text import *
ENGINE="engine:scope_digest"; STAFF="ps.engagement-staffing-bench-match.v1"  # role-access-matrix.md #3.1
SOW_CONTROLS_CONFLICTS=True  # confidentiality-and-ethical-wall-rules.md #1.2
CONFIRMED_ROSTER_CONTROLS=True  # role-access-matrix.md #4.1
INELIGIBLE_STAFFING_EXCLUDED=True  # role-access-matrix.md #3.2
def fld(t,n):
    m=re.search(rf"^{re.escape(n)}:\s*(.*)$",t,re.I|re.M); return m.group(1).strip() if m else ""
def lst(v): return [x.strip(" -") for x in re.split(r";|\n-", v or "") if x.strip(" -")]
def statuses(st):
    s={}; p=[]
    for r in st.get("governed_roles",[]):
        rt=r.get("role_title","role")
        for c in r.get("candidate_slate",[]):
            if c.get("candidate_name"): s.setdefault(c["candidate_name"].lower(),[]).append({"role_title":rt,**(c.get("eligibility") or {}),"confidence":c.get("confidence",.9),"citation":(c.get("eligibility") or {}).get("citation") or c.get("citation","staffing")})
        for c in r.get("recommended_candidates",[]):
            if c.get("candidate_name"): p.append({"candidate_name":c["candidate_name"],"role_title":rt,"fit_score":c.get("fit_score"),"assignment_status":"proposed_not_assigned","source":"adapter:staffing-slate","confidence":c.get("confidence",.9),"citation":c.get("citation","staffing recommended_candidates")})
    return s,p
INELIGIBLE={"ineligible","conflicted","blocked"}  # role-access-matrix.md #3.2
RANK={"ineligible":3,"conflicted":3,"blocked":3,"needs_review":2}
def verdict_for(entries,role):
    # Prefer the Scenario 02 verdict for the confirmed role; otherwise the most restrictive verdict across roles.
    same=[x for x in entries if (x.get("role_title") or "").strip().lower()==(role or "").strip().lower()] or entries
    return max(same,key=lambda x:RANK.get(x.get("verdict"),1 if x.get("verdict")!="eligible" else 0),default={})
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--raw-dir",required=True); ap.add_argument("--staffing",required=True); ap.add_argument("--confirmed-roster",required=True); ap.add_argument("--out",required=True); ap.add_argument("--generated-at",required=True); ap.add_argument("--scenario",default=""); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    sowp=os.path.join(a.raw_dir,"sow-extract.md")
    if not os.path.exists(sowp): raise InputError("missing required SOW extract: raw/sow-extract.md")
    sow=read_text(sowp); letter=read_text(os.path.join(a.raw_dir,"engagement-letter-extract.md")); pursuit=read_text(os.path.join(a.raw_dir,"pursuit-record.md")); rows=read_csv(a.confirmed_roster); st=load_json(a.staffing)
    if not isinstance(st,dict) or st.get("contract_version")!=STAFF: raise InputError(f"staffing adapter expected contract {STAFF}, got {(st.get('contract_version') if isinstance(st,dict) else type(st).__name__)!r}")
    if not isinstance(st.get("governed_roles"),list) or any(not isinstance(r,dict) for r in st["governed_roles"]): raise InputError("staffing adapter requires governed_roles[] of objects; fail closed")
    holds=scan(sow,"raw/sow-extract.md")+scan(letter,"raw/engagement-letter-extract.md")+scan(pursuit,"raw/pursuit-record.md")+scan_rows(rows,"raw/confirmed-roster.csv")+scan(st,"upstream/staffing")
    smap,prop=statuses(st); roster=[]; excl=[]; names=set(); joiner={}; unconfirmed=[]; joiners=[]; esc=list(st.get("escalations",[]))
    for r in rows:
        name=(r.get("person") or "").strip()
        if not name: continue
        names.add(name.lower()); ss=verdict_for(smap.get(name.lower(),[]),r.get("role",""))
        if ss.get("verdict") in INELIGIBLE:
            excl.append({"person":name,"role":r.get("role",""),"reason":f"{ss.get('verdict')} in Scenario 02 for {ss.get('role_title')}; independence/conflict details stay in the staffing record (need-to-know)","blocking_rule":ss.get("blocking_rule"),"source":"adapter:staffing-slate","confidence":ss.get("confidence",.95),"citation":ss.get("citation","role-access-matrix.md #3.2")}); continue
        if (r.get("assignment_status") or "").strip().lower()!="confirmed": unconfirmed.append(name); continue  # role-access-matrix.md #4.1
        item={"person":name,"role":r.get("role",""),"responsibilities":lst(r.get("responsibilities","")),"point_of_contact":r.get("point_of_contact","Engagement manager"),"onboarding_status":r.get("onboarding_status","active"),"assignment_status":"confirmed","source":"raw:confirmed-roster.csv","confidence":.97,"citation":r.get("citation","raw/confirmed-roster.csv")}
        if ss.get("verdict") not in (None,"eligible"): item["staffing_review"]={"verdict":ss.get("verdict"),"blocking_rule":ss.get("blocking_rule"),"citation":ss.get("citation")}; esc.append(f"Confirmed roster row {name} is {ss.get('verdict')} in Scenario 02 for {ss.get('role_title')}; confirm with the engagement manager before onboarding ({ss.get('citation')}; role-access-matrix.md #3.3)")
        roster.append(item)
        if item["onboarding_status"].lower() in {"joining","mid-engagement joiner","new_joiner"}:
            joiners.append(name)
            if not joiner: joiner=dict(item)
    prop=[p for p in prop if p["candidate_name"].lower() not in names]
    exclusions=lst(fld(sow,"Exclusions")); pt=pursuit.lower()
    for e in exclusions:
        if e.lower().split(" - ")[0] in pt and re.search(r"\b(?:include|included|request|requested|add|added|reuse)\b",pt): esc.append(f"SOW exclusion controls over pursuit conflict: '{e}' (confidentiality-and-ethical-wall-rules.md #1.2)"); break
    for n in unconfirmed: esc.append(f"Roster row for {n} has no confirmed assignment_status; treated as not assigned (role-access-matrix.md #4.1)")
    if not joiners: esc.append("No joining team member found in the confirmed roster; wall check and access checklist will hold (confidentiality-and-ethical-wall-rules.md #2.2)")
    elif len(joiners)>1: esc.append(f"Multiple joiners found ({', '.join(joiners)}); this pack covers {joiners[0]} only - run again per joiner (role-access-matrix.md #4.1)")
    for x in excl: esc.append(f"Confirmed roster row excluded: {x['person']} is ineligible/conflicted in Scenario 02 ({x['citation']})")
    if holds: esc.append(f"{len(holds)} source field(s) held for embedded instruction review (confidentiality-and-ethical-wall-rules.md #4.1,#4.2)")
    out={"contract_version":CONTRACT_VERSION,"run_metadata":{"generated_at":ts,"demo_scenario":a.scenario},"engagement":{"engagement_id":fld(sow,"Engagement ID") or st.get("engagement",{}).get("engagement_id",""),"matter_id":fld(sow,"Matter ID"),"title":fld(sow,"Title"),"client_name":fld(sow,"Client") or st.get("engagement",{}).get("client_name",""),"sector":fld(pursuit,"Sector"),"region":fld(pursuit,"Region"),"source":ENGINE,"confidence":.95,"citation":"raw/sow-extract.md header; raw/pursuit-record.md context"},"joiner":joiner,"scope_summary":{"objectives":lst(fld(sow,"Objectives")),"in_scope":lst(fld(sow,"In scope")),"exclusions":exclusions,"deliverables":lst(fld(sow,"Deliverables")),"key_dates":lst(fld(sow,"Key dates")),"systems":lst(fld(sow,"Systems")),"first_week_focus":lst(fld(sow,"First-week")),"source":ENGINE,"confidence":.94,"citation":"raw/sow-extract.md; confidentiality-and-ethical-wall-rules.md #1.2"},"engagement_terms":{"confidentiality_terms":lst(fld(letter,"Confidentiality")),"ethical_wall_terms":lst(fld(letter,"Ethical walls")),"source":"raw:engagement-letter-extract.md","confidence":.93,"citation":"raw/engagement-letter-extract.md"},"team_roster":roster,"proposed_staffing":prop,"staffing_exclusions":excl,"escalations":esc,"holds":holds,"provenance":{"engines":[f"scope_digest/{VERSION}"],"generated_at":ts,"sources":["raw/sow-extract.md","raw/engagement-letter-extract.md","raw/pursuit-record.md","raw/confirmed-roster.csv","upstream/staffing"]}}
    dump_json(a.out,out)
if __name__=="__main__": guard(main)
