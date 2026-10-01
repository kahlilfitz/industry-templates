#!/usr/bin/env python3
import glob, hashlib, os, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def d(p):
    with open(p,"rb") as f: return hashlib.sha256(f.read()).hexdigest()
def main():
    skills=sorted(x for x in glob.glob(os.path.join(ROOT,"skills","*")) if os.path.isdir(x)); pairs=[]
    for src in sorted(glob.glob(os.path.join(ROOT,"contracts","*.json"))): pairs += [(src,os.path.join(s,"contracts",os.path.basename(src))) for s in skills]
    for src in sorted(glob.glob(os.path.join(ROOT,"references","*.md"))): pairs += [(src,os.path.join(s,"references",os.path.basename(src))) for s in skills]
    helper=os.path.join(ROOT,"skills","engagement-retrieve","scripts","safety_text.py"); pairs += [(helper,os.path.join(s,"scripts","safety_text.py")) for s in skills]
    bad=0
    for src,cp in pairs:
        if not os.path.exists(cp): print("MISSING "+os.path.relpath(cp,ROOT)); bad+=1
        elif d(src)!=d(cp): print("DRIFT   "+os.path.relpath(cp,ROOT)); bad+=1
    print(f"{len(pairs)-bad}/{len(pairs)} shared copies identical to their source"); return 1 if bad else 0
if __name__=="__main__": sys.exit(main())
