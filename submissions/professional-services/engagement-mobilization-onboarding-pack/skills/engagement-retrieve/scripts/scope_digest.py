#!/usr/bin/env python3
import argparse, copy, os, re
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
    # One labelled line: [ \t] and [^\r\n], never \s, so a blank "Client:" reads blank instead of consuming the next line (#1.2).
    m=re.search(rf"^{re.escape(n)}:[ \t]*([^\r\n]*)$",t,re.I|re.M); return m.group(1).strip() if m else ""
def lst(v): return split_items(v)
DOMAIN_LABELS=("Client domains","Client domain","Firm domains","Firm domain")  # confidentiality-and-ethical-wall-rules.md #4.4
def declarations(docs):
    """([(doc index, line index, [well-formed trustable domains])] for the first line of each domain label in each
    document whose value does not trip the wire on its own, the count of malformed or untrustable domains)."""
    out=[]; bad=0
    for di,doc in enumerate(docs):
        ls=doc.splitlines()
        for lab in DOMAIN_LABELS:
            i=next((n for n,l in enumerate(ls) if re.match(rf"{re.escape(lab)}:",l,re.I)),None)
            if i is None: continue
            line=ls[i].split(":",1)[1].strip()
            if not line or hits(line): continue
            ds=[]
            for d in re.split(r"[;,\s]+",canon_text(line)):
                d=d.strip().lstrip("@.").rstrip(".")
                if not d: continue
                if domain_ok(d): ds.append(d)
                else: bad+=1
            out.append((di,i,ds))
    return out,bad
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
    if st.get("contract_version")!=STAFF: raise InputError(f"staffing adapter expected contract {STAFF} at upstream/staffing.contract_version (supplied value not repeated); fail closed")
    W="upstream/staffing"; check_timestamps(st,W)  # carried timestamps are format-checked (confidentiality-and-ethical-wall-rules.md #1.3)
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
def staffing_links(st):
    """Staffing records name a candidate by candidate_id in several places (bench, scored, ranked and governed slates,
    recommendations). A candidate_id whose records state different people (canonical names, #1.3) links one person's
    verdict or recommendation to another: every record with that ID is held and not used (#1.5).
    Returns (conflicted canonical IDs, holds)."""
    seen={}; first={}
    def add(path,c,nk):
        if not isinstance(c,dict) or not stated(c.get("candidate_id")) or not stated(c.get(nk)): return  # withheld text is already held (#4.3)
        k=canon_id(c["candidate_id"]); seen.setdefault(k,set()).add(canon_person(c[nk])); first.setdefault(k,[]).append(path)
    W="upstream/staffing"
    for i,c in enumerate(st.get("bench_candidates") or []): add(f"{W}.bench_candidates[{i}].name",c,"name")
    for sec,key in (("scored_roles","candidate_scores"),("ranked_roles","candidate_slate"),("governed_roles","candidate_slate"),("governed_roles","recommended_candidates")):
        for i,r in enumerate(st.get(sec) or []):
            if isinstance(r,dict) and isinstance(r.get(key),list):
                for j,c in enumerate(r[key]): add(f"{W}.{sec}[{i}].{key}[{j}].candidate_name",c,"candidate_name")
    bad={k for k,v in seen.items() if len(v)>1}
    return bad,[link_hold(first[k][1],ENGINE) for k in sorted(bad)]
def statuses(st,bad=frozenset()):
    s={}; p=[]
    for r in st["governed_roles"]:
        rt=r.get("role_title") if (r.get("role_title") or "").strip() else "role"
        for c in r.get("candidate_slate",[]):
            if not (c.get("candidate_name") or "").strip(): continue
            el=c.get("eligibility") or {}; v=el.get("verdict")
            v=canon_text(v) if isinstance(v,str) else None
            if v not in VERDICTS: v="unrecognised"  # blank, null or unknown verdicts fail closed (#3.4)
            if canon_id(c.get("candidate_id")) in bad: v="unrecognised"  # a candidate_id naming two people is not evidence (#1.5)
            if is_withheld(c["candidate_name"]): continue  # a withheld name joins no roster row (confidentiality-and-ethical-wall-rules.md #4.3)
            s.setdefault(canon_person(c["candidate_name"]),[]).append({"role_title":rt,"verdict":v,"blocking_rule":el.get("blocking_rule"),"confidence":c.get("confidence",.9),"citation":el.get("citation") or c.get("citation") or "staffing"})
        for c in r.get("recommended_candidates",[]):
            if canon_id(c.get("candidate_id")) in bad: continue  # never propose through an ID that names another person (#1.5)
            if (c.get("candidate_name") or "").strip(): p.append({"candidate_name":c["candidate_name"],"role_title":rt,"fit_score":c.get("fit_score"),"assignment_status":"proposed_not_assigned","source":"adapter:staffing-slate","confidence":c.get("confidence",.9),"citation":c.get("citation") or "staffing recommended_candidates"})
    return s,p
def verdict_for(entries,role):
    # Prefer the Scenario 02 verdict for the confirmed role; otherwise the most restrictive verdict across roles.
    same=[x for x in entries if canon_text(x.get("role_title"))==canon_text(role)] or entries
    return max(same,key=lambda x:RANK.get(x.get("verdict"),2.5),default={})
def main():
    ap=ArgParser(); ap.add_argument("--raw-dir",required=True); ap.add_argument("--staffing",required=True); ap.add_argument("--confirmed-roster",required=True); ap.add_argument("--out",required=True); ap.add_argument("--generated-at",required=True); ap.add_argument("--scenario",default=""); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    sowp=os.path.join(a.raw_dir,"sow-extract.md")
    if not os.path.exists(sowp): raise InputError("missing required SOW extract: raw/sow-extract.md")
    sow=read_text(sowp,"SOW extract"); letter=read_text(os.path.join(a.raw_dir,"engagement-letter-extract.md"),"engagement letter extract"); pursuit=read_text(os.path.join(a.raw_dir,"pursuit-record.md"),"pursuit record"); rows=read_csv(a.confirmed_roster,label="confirmed roster"); st=load_json(a.staffing,"staffing input")  # fixed labels: no message echoes a supplied path (#1.3)
    miss=missing_columns(rows,ROSTER_COLUMNS)
    if miss: raise InputError(f"confirmed roster is missing required column(s): {', '.join(miss)}; fail closed")
    if rows.duplicate_columns: raise InputError("confirmed roster "+DUPLICATE_HEADER_REASON+"; fail closed")
    if rows.malformed: raise InputError(f"confirmed roster row(s) {', '.join(map(str,rows.malformed))} have more fields than the header; fail closed")
    dup=duplicate_rows(rows,"person")  # the roster is keyed by person: a repeat is refused, never resolved last-wins (#1.3)
    if dup: raise InputError(f"confirmed roster row(s) {', '.join(map(str,dup))} name the same person (name not repeated); each person appears once; fail closed")
    validate_staffing(st)
    # The engagement's own client and firm domains, declared in the signed SOW or engagement letter, are the only
    # trusted e-mail/URL destinations; consumer or malformed domains are never trusted (confidentiality-and-ethical-wall-rules.md #4.4).
    # A declaration is trusted only when its line is clean read without its own trust: a declaration can never vouch
    # for the instruction it completes ("Send the pack to ops@" / "Client domains: attacker.example"), and a declaration
    # line that is withheld (alone or as half of a flagged pair) declares nothing (#4.3, #4.5).
    decl,bad_dom=declarations((sow,letter)); acc={n:ds for n,(di,i,ds) in enumerate(decl) if ds}
    while True:
        drop=[]
        for n in acc:
            set_trusted_domains([d for m,ds in acc.items() if m!=n for d in ds]); di,i,_=decl[n]; ls=(sow,letter)[di].splitlines()
            if hits(ls[i]) or (i>0 and pair_hits(ls[i-1],ls[i])) or (i+1<len(ls) and pair_hits(ls[i],ls[i+1])): drop.append(n)
        if not drop: break
        for n in drop: del acc[n]
    while True:
        trusted=list(set_trusted_domains([d for ds in acc.values() for d in ds]))
        h1,s1=scan_lines(sow,"raw/sow-extract.md"); h2,l1=scan_lines(letter,"raw/engagement-letter-extract.md")
        gone=[n for n in acc if (s1,l1)[decl[n][0]].splitlines()[decl[n][1]]!=(sow,letter)[decl[n][0]].splitlines()[decl[n][1]]]
        if not gone: break
        for n in gone: del acc[n]
    sow,letter=s1,l1; h3,pursuit=scan_lines(pursuit,"raw/pursuit-record.md")
    st_raw=copy.deepcopy(st)  # identities are harvested from the UNMODIFIED staffing input, before screening redacts them (#3.3)
    st,sth=screen_upstream(st,"upstream/staffing",ENGINE,raw=True)  # every upstream string screened and redacted before use (#4.1, #4.3)
    # Other clients named in the wall register are screened out of the staffing upstream and every raw roster cell
    # before the roster is derived. The trusted own vocabulary is the SOW's own identity only: a roster person or a
    # staffing affiliate never makes another client trusted (#3.3).
    own=engagement_words(fld(sow,"Client"),fld(sow,"Engagement ID"),fld(sow,"Matter ID"),fld(sow,"Title"))
    rterms=register_terms(os.path.join(a.raw_dir,"ethical-wall-register.csv"),{"client_name":fld(sow,"Client"),"matter_id":fld(sow,"Matter ID")},own)
    st,soh=screen_other(st,rterms,ENGINE,"upstream/staffing.")
    rsh=scan_rows(rows,"raw/confirmed-roster.csv"); roh=screen_csv_other(rows,"raw/confirmed-roster.csv",rterms,ENGINE)
    # A register client_name/matter_id that trips the wire and names no usable identity holds anyway (#3.3).
    soh=soh+roh+register_identity_holds(os.path.join(a.raw_dir,"ethical-wall-register.csv"),ENGINE)
    holds=h1+h2+h3+rsh+sth+soh
    # Linked staffing records must name the same person: read from the screened staffing input only (#1.5, #4.3).
    badlinks,lh=staffing_links(st); holds+=lh
    smap,prop=statuses(st,badlinks); roster=[]; excl=[]; names=set(); joiner={}; unconfirmed=[]; joiners=[]; esc=[esc_text(e,"upstream/staffing.escalations") for e in st.get("escalations",[])]+([other_escalation(len(soh))] if soh else [])
    for i,r in enumerate(rows,2):
        name=(r.get("person") or "").strip()
        if not name: continue
        # Every rendered display string is non-blank (contract $defs/roster_member): a named roster row without a role is
        # malformed and refused, never rendered blank (confidentiality-and-ethical-wall-rules.md #1.3; role-access-matrix.md #1.1).
        if not (r.get("role") or "").strip(): raise InputError(f"raw/confirmed-roster.csv row {i}.role is blank; every named roster row needs a role (role-access-matrix.md #1.1); fail closed")
        # One canonical person key (#1.3). A withheld roster name joins no Scenario 02 verdict and fails closed as
        # unrecognised: a placeholder is not an identity (confidentiality-and-ethical-wall-rules.md #4.3).
        if is_withheld(name): ss={"verdict":"unrecognised"}
        else: names.add(canon_person(name)); ss=verdict_for(smap.get(canon_person(name),[]),r.get("role",""))
        if ss.get("verdict") in INELIGIBLE:
            excl.append({"person":name,"role":r.get("role",""),"reason":f"{ss.get('verdict')} in Scenario 02 for {ss.get('role_title')}; independence/conflict details stay in the staffing record (need-to-know)","blocking_rule":ss.get("blocking_rule"),"source":"adapter:staffing-slate","confidence":ss.get("confidence",.95),"citation":ss.get("citation","role-access-matrix.md #3.2")}); continue
        if canon_text(r.get("assignment_status"))!="confirmed": unconfirmed.append(name); continue  # role-access-matrix.md #4.1
        item={"person":name,"role":r.get("role",""),"responsibilities":lst(r.get("responsibilities","")),"point_of_contact":r.get("point_of_contact") if (r.get("point_of_contact") or "").strip() else "Engagement manager","onboarding_status":r.get("onboarding_status",""),"assignment_status":"confirmed","source":"raw:confirmed-roster.csv","confidence":.97,"citation":r.get("citation") or "raw/confirmed-roster.csv"}
        if ss.get("verdict")=="unrecognised":
            item["staffing_review"]={"verdict":"unrecognised","blocking_rule":None,"citation":"role-access-matrix.md #3.4"}
            holds.append({"hold_id":"HOLD-UNRECOGNISED-STAFFING-VERDICT","path":f"raw/confirmed-roster.csv row {i}.person" if is_withheld(name) else f"upstream/staffing candidate_slate[{name}].eligibility.verdict","reason":"blank, null or unrecognised Scenario 02 verdict for a confirmed roster member","source":ENGINE,"confidence":.99,"citation":"role-access-matrix.md #3.4"})
            esc.append(f"Confirmed roster row {name} has a blank or unrecognised Scenario 02 verdict; held for the engagement manager (role-access-matrix.md #3.4)")
        elif ss.get("verdict") not in (None,"eligible"): item["staffing_review"]={"verdict":ss.get("verdict"),"blocking_rule":ss.get("blocking_rule"),"citation":ss.get("citation")}; esc.append(f"Confirmed roster row {name} is {ss.get('verdict')} in Scenario 02 for {ss.get('role_title')}; confirm with the engagement manager before onboarding ({ss.get('citation')}; role-access-matrix.md #3.3)")
        onb=canon_text(item["onboarding_status"])
        if onb not in ONBOARDING:
            holds.append({"hold_id":"HOLD-UNKNOWN-ONBOARDING-STATUS","path":f"raw/confirmed-roster.csv row {i}.onboarding_status","reason":"blank or unrecognised onboarding_status; joiner status cannot be determined","source":ENGINE,"confidence":.99,"citation":"role-access-matrix.md #4.4"})
            esc.append(f"Roster row {i} has a blank or unrecognised onboarding_status; held until the engagement manager confirms whether {name} is joining (role-access-matrix.md #4.4)")
        roster.append(item)
        if onb in JOINING:
            joiners.append(name)
            if not joiner: joiner=dict(item)
    prop=[p for p in prop if canon_person(p["candidate_name"]) not in names]
    exclusions=items(fld(sow,"Exclusions")); pt=canon_text(pursuit)
    for e in exclusions:
        if e!=WITHHELD and canon_text(e).split(" - ")[0] in pt and re.search(r"\b(?:include|included|request|requested|add|added|reuse)\b",pt): esc.append(f"SOW exclusion controls over pursuit conflict: '{e}' (confidentiality-and-ethical-wall-rules.md #1.2)"); break
    for n in unconfirmed: esc.append(f"Roster row for {n} has no confirmed assignment_status; treated as not assigned (role-access-matrix.md #4.1)")
    if not joiners: esc.append("No joining team member found in the confirmed roster; wall check and access checklist will hold (confidentiality-and-ethical-wall-rules.md #2.2)")
    elif len(joiners)>1: esc.append(f"Multiple joiners found ({', '.join(joiners)}); this pack covers {joiners[0]} only - run again per joiner (role-access-matrix.md #4.1)")
    for x in excl: esc.append(f"Confirmed roster row excluded: {x['person']} is ineligible/conflicted in Scenario 02 ({x['citation']})")
    if bad_dom:
        holds.append({"hold_id":"HOLD-DOMAIN-NOT-TRUSTED","path":"raw/sow-extract.md or raw/engagement-letter-extract.md domain declaration","reason":f"{bad_dom} declared client/firm domain(s) are malformed or consumer/file-sharing domains and are not trusted (not repeated)","source":ENGINE,"confidence":.97,"citation":"confidentiality-and-ethical-wall-rules.md #4.4"})
        esc.append("A declared client/firm domain is malformed or a consumer/file-sharing domain; confirm the engagement's domains with the engagement manager (confidentiality-and-ethical-wall-rules.md #4.4)")
    holds=dedup_holds(holds)
    eng=st.get("engagement") or {}; reng=st_raw.get("engagement") or {}; sow_client=fld(sow,"Client"); sow_eid=fld(sow,"Engagement ID")
    # The SOW alone declares the engagement's identity (#1.2): a blank SOW Client or Engagement ID is never filled
    # from the staffing file, and the run holds.
    blank=[n for n,v in (("Client",sow_client),("Engagement ID",sow_eid)) if not v]  # a withheld line already holds (#4.3)
    if blank:
        holds.append({"hold_id":"HOLD-SOW-IDENTITY-MISSING","path":"raw/sow-extract.md "+"/".join(blank),"reason":"the SOW does not declare the engagement's client or engagement ID; the engagement identity cannot be confirmed","source":ENGINE,"confidence":.99,"citation":"confidentiality-and-ethical-wall-rules.md #1.2"})
        esc.append("The SOW does not declare the engagement's client or engagement ID; confirm the engagement identity with the engagement manager (confidentiality-and-ethical-wall-rules.md #1.2)")
    # A staffing file for another client or engagement is another client's data: hold it and screen its identity out
    # of every output (confidentiality-and-ethical-wall-rules.md #3.3). Its identity is read from the raw staffing
    # input (identity_parts: a client_name that also trips the wire still names the client), compared canonically
    # with the SOW; a value the SOW does not declare is unconfirmed and differs (#1.2, #1.3).
    own=engagement_words(sow_client,sow_eid,fld(sow,"Matter ID"),fld(sow,"Title"))
    other={k_:other_parts(reng.get(k_),unwithheld(mine),k_,own) for k_,mine in (("client_name",sow_client),("engagement_id",sow_eid))}
    # A staffing identity that trips the wire and names no usable identity cannot be confirmed: a mismatch (#1.2, #3.3).
    mism=[k_ for k_ in ("client_name","engagement_id") if other[k_] or identity_unreadable(reng.get(k_))]
    if lh: esc.append(link_escalation(len(lh)))
    if mism:
        holds.append({"hold_id":"HOLD-STAFFING-ENGAGEMENT-MISMATCH","path":"upstream/staffing.engagement."+"/".join(mism),"reason":"staffing input names a different client or engagement than the SOW (name not repeated); staffing evidence not trusted","source":ENGINE,"confidence":.99,"citation":"confidentiality-and-ethical-wall-rules.md #3.3; role-access-matrix.md #3.1"})
        esc.append("Staffing input is for a different client or engagement than the SOW; staffing evidence held for the engagement manager (confidentiality-and-ethical-wall-rules.md #3.3)")
    affiliates=[x for x in (eng.get("affiliates") or []) if x.strip()] if not mism else []
    if any(h.get("source")=="engine:safety_text" for h in holds): esc.append(f"{sum(h.get('source')=='engine:safety_text' for h in holds)} source field(s) held for embedded instruction review (confidentiality-and-ethical-wall-rules.md #4.1-#4.5)")
    body={"engagement":{"engagement_id":one(sow_eid),"matter_id":one(fld(sow,"Matter ID")),"title":one(fld(sow,"Title")),"client_name":one(sow_client),"affiliates":affiliates,"sector":one(fld(pursuit,"Sector")),"region":one(fld(pursuit,"Region")),"source":ENGINE,"confidence":.95,"citation":"raw/sow-extract.md header; raw/pursuit-record.md context",**({"trusted_domains":trusted} if trusted else {})},"joiner":joiner,"scope_summary":{"objectives":items(fld(sow,"Objectives")),"in_scope":items(fld(sow,"In scope")),"exclusions":exclusions,"deliverables":items(fld(sow,"Deliverables")),"key_dates":items(fld(sow,"Key dates")),"systems":items(fld(sow,"Systems")),"first_week_focus":items(fld(sow,"First-week")),"source":ENGINE,"confidence":.94,"citation":"raw/sow-extract.md; confidentiality-and-ethical-wall-rules.md #1.2"},"engagement_terms":{"confidentiality_terms":items(fld(letter,"Confidentiality")),"ethical_wall_terms":items(fld(letter,"Ethical walls")),"source":"raw:engagement-letter-extract.md","confidence":.93,"citation":"raw/engagement-letter-extract.md"},"team_roster":roster,"proposed_staffing":prop,"staffing_exclusions":excl,"escalations":esc}
    body=redact(body)
    # Other clients named in the wall register never reach scope.json either: the same identities and own words every
    # later engine uses, whatever the register's validity for the wall decision (#2.1, #3.3).
    body,rh=screen_other(body,register_terms(os.path.join(a.raw_dir,"ethical-wall-register.csv"),body["engagement"],own_words(body)),ENGINE,"scope.")
    if rh: holds=dedup_holds(holds+rh); body["escalations"].append(other_escalation(len(rh)))
    if mism:
        body,oh=screen_other(body,client_terms([x for k_ in mism for x in other[k_]],own),ENGINE,"scope.")  # only the identity that differs, from the raw input
        if oh: holds=dedup_holds(holds+oh); body["escalations"].append(other_escalation(len(oh)))
    out={"contract_version":CONTRACT_VERSION,"run_metadata":{"generated_at":ts,"demo_scenario":a.scenario},**body,"holds":holds,"provenance":{"engines":[f"scope_digest/{VERSION}"],"generated_at":ts,"sources":["raw/sow-extract.md","raw/engagement-letter-extract.md","raw/pursuit-record.md","raw/confirmed-roster.csv","upstream/staffing"]}}
    check_contract(out,"scope","scope"); dump_json(a.out,out,"scope output")  # the document written is held to the contract (#1.3)
if __name__=="__main__": guard(main)
