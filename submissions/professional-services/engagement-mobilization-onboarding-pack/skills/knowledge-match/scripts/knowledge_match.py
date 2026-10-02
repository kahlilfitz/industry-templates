#!/usr/bin/env python3
import argparse, copy
from safety_text import *
ENGINE="engine:knowledge_match"; CLOSE="ps.engagement-closeout-knowledge-harvest.v1"  # knowledge-reuse-rules.md #1.1
STATES={"RELEASE_CANDIDATE_SANITISED","RELEASE_CANDIDATE_SANITIZED"}  # knowledge-reuse-rules.md #2.1
PERM="cleared_for_internal_engagement_reuse"  # knowledge-reuse-rules.md #2.2
def review_status(*xs):  # knowledge-reuse-rules.md #2.3: only an explicit false clears review
    return "pending_practice_review" if any(x.get("review_required") is not False for x in xs if isinstance(x,dict)) else "cleared_for_internal_reuse"
def check_asset(a,w,released=False):  # knowledge-reuse-rules.md #1.4
    for k in ("asset_id","title","description","category","confidentiality_permission","citation","engagement_id","client_name","matter_id")+(("clearance_state",) if released else ()): field(a,k,"str",w,nullable=True)
    field(a,"tags","strlist",w,nullable=True); field(a,"review_required","bool",w,nullable=True); field(a,"confidence","num01",w)
def check_lesson(l,w):
    for k in ("cluster_id","category","drafting_guidance","confidentiality_permission","citation","engagement_id","client_name","matter_id"): field(l,k,"str",w,nullable=True)
    for k in ("tags","evidence_citations"): field(l,k,"strlist",w,nullable=True)
    for k in ("rewrite_required","review_candidate"): field(l,k,"bool",w,nullable=True)
    field(l,"confidence","num01",w)
def adapt(p):
    x=load_json(p,"closeout input")
    if not isinstance(x,dict) or x.get("contract_version")!=CLOSE: raise InputError(f"closeout adapter expected a JSON object with contract_version {CLOSE} (supplied value not repeated); fail closed")
    kr=x.get("knowledge_record")
    if not kr or not isinstance(kr,dict): raise InputError("closeout adapter requires top-level knowledge_record object; fail closed")
    if not isinstance(x.get("released_assets",[]),list) or any(not isinstance(r,dict) for r in x.get("released_assets",[])): raise InputError("closeout adapter requires released_assets[] of objects; fail closed")
    ra=x.get("released_assets",[])
    for key in ("reusable_assets","lessons"):
        v=kr.get(key,[])
        if not isinstance(v,list) or any(not isinstance(r,dict) for r in v): raise InputError(f"closeout adapter requires knowledge_record.{key}[] of objects; fail closed")
    W="upstream/closeout"; check_timestamps(x,W)  # carried timestamps are format-checked (confidentiality-and-ethical-wall-rules.md #1.3)
    for i,r in enumerate(ra): check_asset(r,f"{W}.released_assets[{i}]",True)
    for i,r in enumerate(kr.get("reusable_assets",[])): check_asset(r,f"{W}.knowledge_record.reusable_assets[{i}]")
    for i,r in enumerate(kr.get("lessons",[])): check_lesson(r,f"{W}.knowledge_record.lessons[{i}]")
    # Records keyed by ID are never indexed last-wins: released assets by asset_id; reusable assets and lessons share
    # the knowledge_id space they are published under (confidentiality-and-ethical-wall-rules.md #1.3).
    dup=duplicate_ids([(ra,"asset_id","released_assets")],W)+duplicate_ids([(kr.get("reusable_assets",[]),"asset_id","knowledge_record.reusable_assets"),(kr.get("lessons",[]),"cluster_id","knowledge_record.lessons")],W)
    if dup: raise InputError("closeout records keyed by ID must be unique (values not repeated): "+"; ".join(dup)+"; fail closed")
    ce=field(x,"engagement","obj",W,nullable=True,default={})
    for k in ("engagement_id","client_name","matter_id","title"): field(ce,k,"str",W+".engagement",nullable=True)  # every field a reader uses (OWNER) is type-checked (#1.3)
    return {"knowledge_record":kr,"released_assets":ra,"engagement":ce,"provenance":x.get("provenance",x.get("run_metadata",{}))}
def check_scope(s):
    need(isinstance(s,dict),f"scope input must be a JSON object, got {type(s).__name__}; fail closed")
    if s.get("contract_version")!=CONTRACT_VERSION: raise InputError(f"expected contract {CONTRACT_VERSION} in scope input")
    field(s,"scope_summary","obj","scope",required=True); check_contract(s,"scope","scope")  # confidentiality-and-ethical-wall-rules.md #1.3
    check_hold_evidence(s,"scope")  # holds are cumulative: a placeholder, escalation or held status without its hold is refused (#1.4)
# A Closeout record belongs to the closed engagement, and a released-asset clearance to the reusable asset with its
# asset_id: both must state the same subject, compared canonically (confidentiality-and-ethical-wall-rules.md #1.5).
OWNER={"engagement_id":canon_id,"client_name":canon_person,"matter_id":canon_id}
ASSET=dict(OWNER,title=canon_text)
def nb(*vs):
    """The first non-blank string: a rendered display string is never blank (contract $defs/knowledge_item, #1.3)."""
    return next((v for v in vs if isinstance(v,str) and v.strip()),None)
def rel(scope,item):
    ss=scope["scope_summary"]
    over=sorted(toks(item.get("title") or "",item.get("description") or ""," ".join(item.get("tags") or []),item.get("category") or "") & toks((scope.get("joiner") or {}).get("role") or ""," ".join(ss.get("objectives",[]))," ".join(ss.get("in_scope",[]))," ".join(ss.get("deliverables",[]))))
    return (round(min(.99,.55+.08*len(over)),2) if over else .4),over
def main():
    ap=ArgParser(); ap.add_argument("--scope",required=True); ap.add_argument("--closeout",required=True); ap.add_argument("--wall-register",required=True); ap.add_argument("--out",required=True); ap.add_argument("--generated-at",required=True); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    s=load_json(a.scope,"scope input"); check_scope(s); reconcile_trusted(s,"scope")  # re-derived from the carried declaration lines, never the carried list (#1.4, #4.4)
    # Both upstream documents are screened whole (every string, holds included) and redacted before use (#4.1, #4.3).
    s,sh=screen_upstream(s,"scope",ENGINE)
    raw=adapt(a.closeout); ce=copy.deepcopy(raw["engagement"])  # the closed engagement's identity, harvested from the UNMODIFIED closeout before screening redacts it (#3.3)
    c,own_h=screen_upstream(raw,"upstream/closeout",ENGINE,raw=True); rels={canon_id(x.get("asset_id")):x for x in c["released_assets"] if x.get("clearance_state") in STATES and canon_id(x.get("asset_id")) and not is_withheld(x.get("asset_id"))}  # joined by canon_id (#1.3); a blank or withheld ID joins nothing (#4.3)
    inc=[]; exc=[]; kr=c["knowledge_record"]; ceng=c.get("engagement") or {}; lh=[]  # subjects compared on screened text only (#4.3)
    for i,asset in enumerate(kr.get("reusable_assets",[])):
        aid=asset.get("asset_id")
        if not canon_id(aid) or is_withheld(aid) or canon_id(aid) not in rels: exc.append({"asset_id":aid,"reason":"not_in_released_assets","citation":"knowledge-reuse-rules.md #2.1"}); continue
        if subjects_differ(asset,rels[canon_id(aid)],ASSET) or subjects_differ(asset,ceng,OWNER) or subjects_differ(rels[canon_id(aid)],ceng,OWNER):
            lh.append(link_hold(f"upstream/closeout.knowledge_record.reusable_assets[{i}]",ENGINE)); exc.append({"asset_id":aid,"reason":"linked_record_subject_mismatch","citation":LINK_CITATION}); continue
        perm=asset.get("confidentiality_permission",rels[canon_id(aid)].get("confidentiality_permission"))
        if perm is not None and perm!=PERM: exc.append({"asset_id":aid,"reason":"confidentiality_permission_not_internal_reuse","citation":"knowledge-reuse-rules.md #2.2"}); continue
        score,over=rel(s,asset)
        if score<.5: exc.append({"asset_id":aid,"reason":"below_relevance_floor","citation":"knowledge-reuse-rules.md #3.1"}); continue
        inc.append({"knowledge_id":aid,"title":nb(asset.get("title"),rels[canon_id(aid)].get("title"),f"Released knowledge asset {aid}"),"summary":nb(asset.get("description"),"Released Closeout knowledge candidate; use the title and citation only until practice review confirms."),"relevance_score":score,"matched_terms":over,"clearance_state":rels[canon_id(aid)].get("clearance_state"),"confidentiality_permission":perm or "release_candidate_state","review_status":review_status(asset,rels[canon_id(aid)]),"source":"adapter:closeout-governed.knowledge_record","confidence":min(asset.get("confidence",.9),rels[canon_id(aid)].get("confidence",.9)),"citations":[nb(asset.get("citation"),"knowledge_record.reusable_assets"),nb(rels[canon_id(aid)].get("citation"),"released_assets"),"knowledge-reuse-rules.md #1.3,#2.1,#2.2,#3.1"]})
    for i,lesson in enumerate(kr.get("lessons",[])):
        lp=lesson.get("confidentiality_permission")
        if not canon_id(lesson.get("cluster_id")) or is_withheld(lesson.get("cluster_id")): exc.append({"lesson_id":lesson.get("cluster_id"),"reason":"no_lesson_id","citation":"knowledge-reuse-rules.md #1.4"}); continue  # every knowledge item carries its identity (contract $defs/knowledge_item)
        if subjects_differ(lesson,ceng,OWNER): lh.append(link_hold(f"upstream/closeout.knowledge_record.lessons[{i}]",ENGINE)); exc.append({"lesson_id":lesson.get("cluster_id"),"reason":"linked_record_subject_mismatch","citation":LINK_CITATION}); continue
        if lp is not None and lp!=PERM: exc.append({"lesson_id":lesson.get("cluster_id"),"reason":"confidentiality_permission_not_internal_reuse","citation":"knowledge-reuse-rules.md #2.2"}); continue
        if lesson.get("rewrite_required") is not False: exc.append({"lesson_id":lesson.get("cluster_id"),"reason":"rewrite_required_or_unknown","citation":"knowledge-reuse-rules.md #2.4"}); continue
        score,over=rel(s,{"title":lesson.get("category") or "","description":lesson.get("drafting_guidance") or "","tags":lesson.get("tags") or []})
        if score>=.5: inc.append({"knowledge_id":lesson.get("cluster_id"),"title":f"Lesson: {nb(lesson.get('category'),'uncategorised')}","summary":nb(lesson.get("drafting_guidance"),"Closeout lesson; use the title and citation only until practice review confirms."),"relevance_score":score,"matched_terms":over,"clearance_state":"LESSON_FOR_INTERNAL_DRAFT","confidentiality_permission":lp or "closeout_governed_lesson","review_status":review_status({"review_required":lesson.get("review_candidate")}),"source":"adapter:closeout-governed.knowledge_record.lessons","confidence":lesson.get("confidence",.85),"citations":[x for x in (lesson.get("evidence_citations") or []) if nb(x)]+[nb(lesson.get("citation"),"knowledge_record.lessons"),"knowledge-reuse-rules.md #2.2,#2.4,#3.2"]})
    inc=redact(inc)  # flagged Closeout text never travels (confidentiality-and-ethical-wall-rules.md #4.3)
    # The closed engagement is usually another client: its name and IDs never reach this pack (#3.3).
    # Its identity comes from the raw closeout (ce): a client_name that also trips the wire still names the client,
    # and only the parts that are not this engagement's own become terms (identity_parts, #3.3).
    mine=s.get("engagement") or {}
    # The scope's engagement identity is carried state: a closed engagement for a different client is another
    # client's in full, so its engagement ID is screened even when it equals the carried one (#1.4, #3.3).
    cdiff=bool(other_parts(ce.get("client_name"),mine.get("client_name"),"client_name"))
    terms=client_terms([x for k_ in ("client_name","engagement_id") for x in (identity_parts(ce.get(k_)) if cdiff and k_=="engagement_id" else other_parts(ce.get(k_),mine.get(k_),k_,own_words(s)))],own_words(s))
    # Every other client named in the wall register is screened out here too, not only at wall_check (#3.3).
    terms+=[t for t in register_terms(a.wall_register,mine,own_words(s)) if t[0] not in {x[0] for x in terms}]
    # Upstream scope holds are supplied content: screened for other-client names and steering text (#3.3, #4.3).
    # A structured identity (Closeout engagement, register client_name/matter_id) that trips the wire and names no
    # usable identity holds anyway: the other-client screen cannot be confirmed (#3.3).
    ih=[other_hold(f"upstream/closeout.engagement.{k_}",ce.get(k_),ENGINE) for k_ in ("client_name","engagement_id") if identity_unreadable(ce.get(k_))]+register_identity_holds(a.wall_register,ENGINE)
    if ih: s.setdefault("escalations",[]).append(other_escalation(len(ih)))
    up,uh=screen_holds(s.get("holds",[]),terms,ENGINE,"scope.holds"); holds=dedup_holds(up+sh+own_h+uh+ih+lh)
    if lh: s.setdefault("escalations",[]).append(link_escalation(len(lh)))
    if sh or own_h: s.setdefault("escalations",[]).append(upstream_escalation(len(sh)+len(own_h)))
    if any(h["hold_id"].startswith("HOLD-OTHER-CLIENT-") for h in uh): s.setdefault("escalations",[]).append(other_escalation(sum(h["hold_id"].startswith("HOLD-OTHER-CLIENT-") for h in uh)))
    if terms:
        s["prior_knowledge_candidates"]=inc; s["excluded_items"]=exc; s,oh=screen_other(s,terms,ENGINE,"matched."); inc=s.pop("prior_knowledge_candidates"); exc=s.pop("excluded_items")
        if oh: holds=dedup_holds(holds+oh); s.setdefault("escalations",[]).append(other_escalation(len(oh)))
    status="ready" if inc and not holds else "hold" if holds else "empty"
    if not inc and not holds: s.setdefault("escalations",[]).append("No released, permissioned prior-knowledge records matched the engagement (knowledge-reuse-rules.md #2.1,#2.2,#3.1)")
    s["prior_knowledge_candidates"]=inc; s["knowledge_digest"]={"status":status,"items":inc,"excluded_items":exc,"source":ENGINE,"confidence":.92 if inc else .7,"citation":"knowledge-reuse-rules.md #1.1-#3.2"}; s["holds"]=holds; s.setdefault("provenance",{}).setdefault("engines",[]).append(f"knowledge_match/{VERSION}"); s["provenance"]["generated_at"]=ts
    s=bind_withheld(settle_trust(s),"matched",ENGINE); check_contract(s,"matched","matched"); dump_json(a.out,s,"matched output")  # the document written is held to the same contract (#1.3)
if __name__=="__main__": guard(main)
