#!/usr/bin/env python3
"""Every skill carries byte-identical copies of the shared contract, references, helpers and engines it runs.

Runner contract (MOS3, 1.0.3): `python tests/check_shared_copies.py --plugin-root <dir>` (or the PLUGIN_ROOT
environment variable). The plugin root is an extracted MOS3 ZIP or the submission folder; with neither, it defaults
to <repo>/submissions/<industry>/<slug>, where this file sits in test-data/<industry>/<slug>/<version>/tests/.
engagement-retrieve holds the canonical contract and references: the plugin root no longer carries contracts/ or
references/, because a MOS3 package ships only skills/.
"""
import argparse, glob, hashlib, os, sys
DATA_ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The one place the vendored shared detector is pinned. On a byte-identical re-copy of a new steering_guard.py
# release into every skill, update this constant and nothing else.
STEERING_GUARD_SHA256="d8120dac2c728f04bfe08c3ffcc67d042c7e43a60e2dc099f7611a401b64e701"
CANONICAL_SKILL="engagement-retrieve"
def default_plugin_root():
    slug_dir=os.path.dirname(DATA_ROOT); industry_dir=os.path.dirname(slug_dir); repo=os.path.dirname(os.path.dirname(industry_dir))
    return os.path.join(repo,"submissions",os.path.basename(industry_dir),os.path.basename(slug_dir))
def d(p):
    with open(p,"rb") as f: return hashlib.sha256(f.read()).hexdigest()
def pairs_for(root):
    """(source, copy) pairs that must be byte-identical, sources in the canonical skill or the owning skill."""
    skills=sorted(x for x in glob.glob(os.path.join(root,"skills","*")) if os.path.isdir(x)); canon=os.path.join(root,"skills",CANONICAL_SKILL); pairs=[]
    for sub,pat in (("contracts","*.json"),("references","*.md")):
        for src in sorted(glob.glob(os.path.join(canon,sub,pat))): pairs += [(src,os.path.join(s,sub,os.path.basename(src))) for s in skills]
    for name in ("safety_text.py","contract_validate.py"):
        helper=os.path.join(canon,"scripts",name); pairs += [(helper,os.path.join(s,"scripts",name)) for s in skills]
    guard=os.path.join(canon,"scripts","steering_guard.py"); pairs += [(guard,os.path.join(s,"scripts","steering_guard.py")) for s in skills]
    # Each downstream stage re-runs the upstream engines on the raw inputs (#1.4), so it carries their exact copies.
    # pack-draft and roster-pull re-run them before the model renders from a supplied file (verify_render.py, A23).
    for skill,name,users in (("engagement-retrieve","scope_digest.py",("knowledge-match","wall-check","pack-draft","roster-pull")),("knowledge-match","knowledge_match.py",("wall-check","pack-draft")),
                             ("wall-check","wall_check.py",("pack-draft",)),("wall-check","access_checklist.py",("pack-draft",)),("pack-draft","verify_render.py",("roster-pull",))):
        src=os.path.join(root,"skills",skill,"scripts",name); pairs += [(src,os.path.join(root,"skills",u,"scripts",name)) for u in users]
    return pairs
def check(root):
    """Problems as printable lines (empty when every copy matches) and the number of pairs checked."""
    guard=os.path.join(root,"skills",CANONICAL_SKILL,"scripts","steering_guard.py"); pairs=pairs_for(root); bad=[]
    if not os.path.exists(guard) or d(guard)!=STEERING_GUARD_SHA256: bad.append("PIN     steering_guard.py does not match STEERING_GUARD_SHA256")
    for sub in ("contracts","references"):
        if not glob.glob(os.path.join(root,"skills",CANONICAL_SKILL,sub,"*")): bad.append(f"MISSING skills/{CANONICAL_SKILL}/{sub}/ (canonical copies)")
    for src,cp in pairs:
        if not os.path.exists(src): bad.append("MISSING "+os.path.relpath(src,root))
        elif not os.path.exists(cp): bad.append("MISSING "+os.path.relpath(cp,root))
        elif d(src)!=d(cp): bad.append("DRIFT   "+os.path.relpath(cp,root))
    return bad,len(pairs)
def main(argv=None):
    ap=argparse.ArgumentParser(description="Mobilization shared-copy check.",allow_abbrev=False)
    ap.add_argument("--plugin-root",metavar="DIR",help="extracted MOS3 ZIP or submission folder holding skills/ (default: PLUGIN_ROOT, else the repository submission)")
    args=ap.parse_args(argv)
    root=os.path.abspath(args.plugin_root or os.environ.get("PLUGIN_ROOT") or default_plugin_root())
    safe=lambda x: x.encode("ascii","backslashreplace").decode("ascii")
    print(safe("plugin root: "+root)); print(safe("data root: "+DATA_ROOT))
    if not os.path.isdir(os.path.join(root,"skills")): print(safe("plugin root has no skills/ folder: "+root),file=sys.stderr); return 2
    bad,n=check(root)
    for b in bad: print(safe(b))
    drift=sum(1 for b in bad if not b.startswith(("PIN","MISSING skills/"+CANONICAL_SKILL+"/contracts","MISSING skills/"+CANONICAL_SKILL+"/references")))
    print(f"{n-drift}/{n} shared copies identical to their source (steering_guard.py pinned)"); return 1 if bad else 0
if __name__=="__main__": sys.exit(main())
