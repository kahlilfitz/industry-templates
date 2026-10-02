#!/usr/bin/env python3
import glob, hashlib, os, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The one place the vendored shared detector is pinned. On a byte-identical re-copy of a new steering_guard.py
# release into every skill, update this constant and nothing else.
STEERING_GUARD_SHA256="825d0550190150e78fd3a66fc3b8c8b6e5f4867e6620e47ed7381b0d796f4123"
STEERING_GUARD=os.path.join(ROOT,"skills","engagement-retrieve","scripts","steering_guard.py")
def d(p):
    with open(p,"rb") as f: return hashlib.sha256(f.read()).hexdigest()
def main():
    skills=sorted(x for x in glob.glob(os.path.join(ROOT,"skills","*")) if os.path.isdir(x)); pairs=[]
    for src in sorted(glob.glob(os.path.join(ROOT,"contracts","*.json"))): pairs += [(src,os.path.join(s,"contracts",os.path.basename(src))) for s in skills]
    for src in sorted(glob.glob(os.path.join(ROOT,"references","*.md"))): pairs += [(src,os.path.join(s,"references",os.path.basename(src))) for s in skills]
    helper=os.path.join(ROOT,"skills","engagement-retrieve","scripts","safety_text.py"); pairs += [(helper,os.path.join(s,"scripts","safety_text.py")) for s in skills]
    pairs += [(STEERING_GUARD,os.path.join(s,"scripts","steering_guard.py")) for s in skills]
    bad=0
    if not os.path.exists(STEERING_GUARD) or d(STEERING_GUARD)!=STEERING_GUARD_SHA256: print("PIN     steering_guard.py does not match STEERING_GUARD_SHA256"); bad+=1
    for src,cp in pairs:
        if not os.path.exists(cp): print("MISSING "+os.path.relpath(cp,ROOT)); bad+=1
        elif d(src)!=d(cp): print("DRIFT   "+os.path.relpath(cp,ROOT)); bad+=1
    print(f"{len(pairs)-bad}/{len(pairs)} shared copies identical to their source (steering_guard.py pinned)"); return 1 if bad else 0
if __name__=="__main__": sys.exit(main())
