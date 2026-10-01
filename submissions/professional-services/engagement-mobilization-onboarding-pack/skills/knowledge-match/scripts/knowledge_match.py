#!/usr/bin/env python3
import argparse
from safety_text import *
ENGINE="engine:knowledge_match"; CLOSE="ps.engagement-closeout-knowledge-harvest.v1"  # knowledge-reuse-rules.md #1.1
STATES={"RELEASE_CANDIDATE_SANITISED","RELEASE_CANDIDATE_SANITIZED"}  # knowledge-reuse-rules.md #2.1
PERM="cleared_for_internal_engagement_reuse"  # knowledge-reuse-rules.md #2.2
def review_status(*xs):  # knowledge-reuse-rules.md #2.3
    return "pending_practice_review" if any(x.get("review_required",True) for x in xs if isinstance(x,dict)) else "cleared_for_internal_reuse"
def adapt(p):
    x=load_json(p)
    if not isinstance(x,dict) or x.get("contract_version")!=CLOSE: raise InputError(f"closeout adapter expected contract {CLOSE}, got {(x.get('contract_version') if isinstance(x,dict) else type(x).__name__)!r}")
    kr=x.get("knowledge_record"); ra=x.get("released_assets",[])
    if not kr or not isinstance(kr,dict): raise InputError("closeout adapter requires top-level knowledge_record object; fail closed")
    if not isinstance(ra,list) or any(not isinstance(r,dict) for r in ra): raise InputError("closeout adapter requires released_assets[] of objects; fail closed")
    for key in ("reusable_assets","lessons"):
        v=kr.get(key,[])
        if not isinstance(v,list) or any(not isinstance(r,dict) for r in v): raise InputError(f"closeout adapter requires knowledge_record.{key}[] of objects; fail closed")
    return {"knowledge_record":kr,"released_assets":ra,"provenance":x.get("provenance",x.get("run_metadata",{}))}
def rel(scope,item):
    over=sorted(toks(item.get("title",""),item.get("description","")," ".join(item.get("tags",[])),item.get("category","")) & toks(scope.get("joiner",{}).get("role","")," ".join(scope.get("scope_summary",{}).get("objectives",[]))," ".join(scope.get("scope_summary",{}).get("in_scope",[]))," ".join(scope.get("scope_summary",{}).get("deliverables",[]))))
    return (round(min(.99,.55+.08*len(over)),2) if over else .4),over
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--scope",required=True); ap.add_argument("--closeout",required=True); ap.add_argument("--out",required=True); ap.add_argument("--generated-at",required=True); a=ap.parse_args(); ts=require_iso_z(a.generated_at)
    s=load_json(a.scope)
    if s.get("contract_version")!=CONTRACT_VERSION: raise InputError(f"expected contract {CONTRACT_VERSION} in scope input")
    c=adapt(a.closeout); holds=list(s.get("holds",[]))+scan(c["knowledge_record"],"upstream/closeout.knowledge_record"); rels={x.get("asset_id"):x for x in c["released_assets"] if x.get("clearance_state") in STATES}
    inc=[]; exc=[]; kr=c["knowledge_record"]
    for asset in kr.get("reusable_assets",[]):
        aid=asset.get("asset_id")
        if aid not in rels: exc.append({"asset_id":aid,"reason":"not_in_released_assets","citation":"knowledge-reuse-rules.md #2.1"}); continue
        perm=asset.get("confidentiality_permission",rels[aid].get("confidentiality_permission"))
        if perm is not None and perm!=PERM: exc.append({"asset_id":aid,"reason":"confidentiality_permission_not_internal_reuse","citation":"knowledge-reuse-rules.md #2.2"}); continue
        score,over=rel(s,asset)
        if score<.5: exc.append({"asset_id":aid,"reason":"below_relevance_floor","citation":"knowledge-reuse-rules.md #3.1"}); continue
        inc.append({"knowledge_id":aid,"title":asset.get("title"),"summary":asset.get("description") or "Released Closeout knowledge candidate; use the title and citation only until practice review confirms.","relevance_score":score,"matched_terms":over,"clearance_state":rels[aid].get("clearance_state"),"confidentiality_permission":perm or "release_candidate_state","review_status":review_status(asset,rels[aid]),"source":"adapter:closeout-governed.knowledge_record","confidence":min(asset.get("confidence",.9),rels[aid].get("confidence",.9)),"citations":[asset.get("citation","knowledge_record.reusable_assets"),rels[aid].get("citation","released_assets"),"knowledge-reuse-rules.md #1.3,#2.1,#2.2,#3.1"]})
    for lesson in kr.get("lessons",[]):
        lp=lesson.get("confidentiality_permission")
        if lp is not None and lp!=PERM: exc.append({"lesson_id":lesson.get("cluster_id"),"reason":"confidentiality_permission_not_internal_reuse","citation":"knowledge-reuse-rules.md #2.2"}); continue
        if lesson.get("rewrite_required") is not False: exc.append({"lesson_id":lesson.get("cluster_id"),"reason":"rewrite_required_or_unknown","citation":"knowledge-reuse-rules.md #2.4"}); continue
        score,over=rel(s,{"title":lesson.get("category",""),"description":lesson.get("drafting_guidance",""),"tags":lesson.get("tags",[])})
        if score>=.5: inc.append({"knowledge_id":lesson.get("cluster_id"),"title":f"Lesson: {lesson.get('category')}","summary":lesson.get("drafting_guidance"),"relevance_score":score,"matched_terms":over,"clearance_state":"LESSON_FOR_INTERNAL_DRAFT","confidentiality_permission":lp or "closeout_governed_lesson","review_status":review_status({"review_required":lesson.get("review_candidate",True)}),"source":"adapter:closeout-governed.knowledge_record.lessons","confidence":lesson.get("confidence",.85),"citations":lesson.get("evidence_citations",[])+[lesson.get("citation","knowledge_record.lessons"),"knowledge-reuse-rules.md #2.2,#2.4,#3.2"]})
    status="ready" if inc and not holds else "hold" if holds else "empty"
    if not inc and not holds: s.setdefault("escalations",[]).append("No released, permissioned prior-knowledge records matched the engagement (knowledge-reuse-rules.md #2.1,#2.2,#3.1)")
    s["prior_knowledge_candidates"]=inc; s["knowledge_digest"]={"status":status,"items":inc,"excluded_items":exc,"source":ENGINE,"confidence":.92 if inc else .7,"citation":"knowledge-reuse-rules.md #1.1-#3.2"}; s["holds"]=holds; s.setdefault("provenance",{}).setdefault("engines",[]).append(f"knowledge_match/{VERSION}"); s["provenance"]["generated_at"]=ts; dump_json(a.out,s)
if __name__=="__main__": guard(main)
