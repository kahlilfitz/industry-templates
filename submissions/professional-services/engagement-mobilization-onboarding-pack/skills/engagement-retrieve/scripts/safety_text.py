import csv, hashlib, json, re, unicodedata
from datetime import datetime
CONTRACT_VERSION = "ps.engagement-mobilization-onboarding-pack.v1"
VERSION = "1.0.0"
class InputError(Exception): pass
def require_iso_z(v):
    try: datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as e: raise InputError("--generated-at must be ISO-8601 UTC like 2026-10-01T00:00:00Z") from e
    return v
def load_json(p):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError as e: raise InputError(f"missing required JSON file: {p}") from e
    except json.JSONDecodeError as e: raise InputError(f"malformed JSON in {p}: {e}") from e
def dump_json(p,o):
    with open(p,"w",encoding="utf-8",newline="\n") as f: json.dump(o,f,indent=2,ensure_ascii=False); f.write("\n")
def read_text(p):
    try:
        with open(p,encoding="utf-8") as f: return f.read()
    except FileNotFoundError as e: raise InputError(f"missing required file: {p}") from e
def write_text(p,t):
    with open(p,"w",encoding="utf-8",newline="\n") as f: f.write(t if t.endswith("\n") else t+"\n")
def read_csv(p, required=True):
    try:
        with open(p,encoding="utf-8",newline="") as f: return list(csv.DictReader(f))
    except FileNotFoundError as e:
        if required: raise InputError(f"missing required CSV file: {p}") from e
        return None
def strip_cf(s): return "".join(c for c in str(s) if unicodedata.category(c)!="Cf")
def norm(s):
    s=unicodedata.normalize("NFKC",strip_cf(s)).lower().replace("—","-").replace("–","-").replace("’","'")
    s=re.sub(r"[*_`]+","",s); return re.sub(r"\s+"," ",s).strip()
# SOWs, rosters and workspace inventories legitimately mention AI programmes, systems, access requests,
# URLs and e-mail addresses. These patterns target text that addresses the assistant or tries to steer
# THIS mobilization run (wall, holds, clearance, roster, access, briefing, exfiltration)
# (confidentiality-and-ethical-wall-rules.md #4.1,#4.2). Matched after Cf stripping and NFKC folding.
_AI=r"(?:ai|assistant|copilot|llm|chatbot|claude|gpt|bot)"
_ACT=r"(?:please|treat|mark|approve|clear|ignore|skip|include|add|grant|give|provision|remove|omit|drop|exclude|confirm|assign|share|send|forward|disregard|bypass|override|do not|don't|dont|you)"
_GUARD=r"(?:(?:the |any |all |these |this )?(?:ethical[- ])?walls?(?: register| check| review| status| restrictions?)?|conflicts? checks?|(?:engine|wall|embedded[- ]instruction|source) holds?|(?:the )?confidentiality (?:briefing|rules|terms)|(?:the )?(?:role|access) matrix|(?:wall |access |knowledge )?restrictions?)"
_CONTACT=r"(?:[a-z0-9._%+-]+\s*(?:@|\(at\)|\[at\])\s*[a-z0-9-]+(?:\s*(?:\.|\(dot\)|\[dot\])\s*[a-z0-9-]+)+|https?://|www\.)"
_PACK=r"(?:this|these|it|the (?:full |whole |complete )?(?:pack|draft|briefing|roster|checklist|knowledge|digest|deliverables?|materials?|documents?|files?|assets?|playbook))"
PATS=[
 ("assistant_addressed",re.compile(r"\b(?:note|message|instruction|instructions|reminder)s? (?:to|for) (?:the )?"+_AI+r"\b|\b(?:hey|hi|dear|attention|attn) (?:the )?"+_AI+r"\b|\b"+_AI+r"\s*[:,\]\)>]+\s*"+_ACT+r"\b|\b"+_AI+r" (?:should|must|needs to|is to|is instructed to) (?:not )?(?:treat|mark|approve|clear|ignore|skip|include|grant|provision|omit|drop|exclude|disregard|bypass|override)\b")),
 ("override_rules",re.compile(r"\b(?:ignore|disregard|override|bypass|skip|circumvent)\b.{0,30}\b(?:(?:previous|prior|above|earlier|all|your|these|the) instructions|"+_GUARD+r")\b")),
 ("suppress_control",re.compile(r"\b(?:do not|don't|dont|must not|should not|never)\s+(?:flag|hold|escalate|surface|block)\s+(?:this|these|it|the joiner|this joiner)\b|\b(?:do not|don't|dont|must not|should not|never|no need to)\s+(?:raise|flag|surface|escalate|apply|check|review|restrict|enforce)\s+(?:a |any |the )?(?:hold|holds|walls?|restrictions?|wall (?:check|review)|conflict checks?|briefing|knowledge|access)\b|\b(?:omit|remove|drop|leave out|suppress|hide|delete)\b.{0,20}\b(?:(?:the )?(?:confidentiality|ethical[- ]wall|wall) (?:briefing|section|restrictions?|warning)|(?:the |all |any )?(?:escalations?|(?:engine|wall|embedded[- ]instruction|source) holds?|holds? and escalations|holds section))\b")),
 ("approval_claim",re.compile(r"\b(?:wall[- ]cleared|pre[- ]?cleared|already (?:wall[- ])?cleared|cleared by (?:risk|compliance|the gc|general counsel|legal|conflicts)|no (?:wall|conflicts?) (?:review|check)s? (?:is |are )?(?:needed|required))\b|\b(?:ethical walls?|walls?|conflicts?|wall restrictions?)\s+(?:has |have |was |were |is |are )?(?:been )?(?:lifted|waived|suspended|no longer appl(?:y|ies)|not required|not applicable)\b|\bpre[- ]?approved\b.{0,30}\b(?:access|admin|knowledge|joiner|wall|exception|exemption)\b|\b(?:treat|mark|consider|record|classify|list)\s+(?:\S+\s+){0,4}?as\s+(?:(?:wall[- ])?cleared|unrestricted|exempt)\b|\bas (?:confirmed|assigned) (?:on|to|in) (?:the )?(?:roster|team|engagement)\b")),
 ("scope_escalation",re.compile(r"\b(?:include|add|surface|share|attach|use)\b.{0,40}\b(?:held|withheld|restricted|walled|uncleared|unreleased)\s+(?:assets?|knowledge|material|deliverables?|records?|workspaces?)\b|\bregardless of\s+(?:the\s+)?(?:clearance|walls?|restrictions?|holds?|permissions?|role matrix|confidentiality)\b|\b(?:grant|give|add|provision)\b.{0,30}\badmin(?:istrator)?\b.{0,40}\b(?:every|all|each)\b|\bshare everything\b|\b(?:add|move|promote)\b.{0,30}\bto the confirmed roster\b|\bassignment (?:is|has been) (?:approved|confirmed) (?:by|per)\b")),
 ("exfiltration",re.compile(r"\b(?:forward|send|e-?mail|share|upload|transmit|cc)\s+"+_PACK+r"\b.{0,60}"+_CONTACT)),
]
def hits(s): return [] if s is None else [n for n,p in PATS if p.search(norm(s))]
def hold(path,text,hit):
    d=hashlib.sha256(strip_cf(text or "").encode()).hexdigest()[:12]
    return {"hold_id":f"HOLD-{d}","path":path,"reason":f"embedded_instruction:{hit}","source":"engine:safety_text","confidence":0.99,"citation":"confidentiality-and-ethical-wall-rules.md #4.1,#4.2"}
def scan(v,path="$"):
    out=[]
    if isinstance(v,dict):
        for k,x in v.items(): out+=scan(x,f"{path}.{k}")
    elif isinstance(v,list):
        for i,x in enumerate(v): out+=scan(x,f"{path}[{i}]")
    elif isinstance(v,str):
        for h in hits(v): out.append(hold(path,v,h))
    return out
def scan_rows(rows,label):
    out=[]
    for i,r in enumerate(rows or [],2):
        for k,v in r.items():
            for h in hits(v): out.append(hold(f"{label} row {i}.{k}",v,h))
    return out
def toks(*parts):
    stop={"the","and","for","with","from","into","client","engagement","team","work","draft","record"}
    return {x for p in parts for x in re.findall(r"[a-z0-9]+", norm(p or "")) if len(x)>2 and x not in stop}
def guard(fn):
    try: return fn()
    except InputError as e: raise SystemExit(f"InputError: {e}")
