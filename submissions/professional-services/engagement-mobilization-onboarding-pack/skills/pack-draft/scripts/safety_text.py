import csv, hashlib, json, re, unicodedata
from datetime import datetime
CONTRACT_VERSION = "ps.engagement-mobilization-onboarding-pack.v1"
VERSION = "1.0.1"
class InputError(Exception): pass

# ---------------------------------------------------------------- I/O
def require_iso_z(v):
    try: datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError) as e: raise InputError("--generated-at must be ISO-8601 UTC like 2026-10-01T00:00:00Z") from e
    return v
def load_json(p):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError as e: raise InputError(f"missing required JSON file: {p}") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e: raise InputError(f"malformed JSON in {p} (must be UTF-8 JSON): {e}") from e
    except OSError as e: raise InputError(f"cannot read JSON file {p}: {type(e).__name__}") from e
def dump_json(p, o):
    with open(p, "w", encoding="utf-8", newline="\n") as f: json.dump(o, f, indent=2, ensure_ascii=False); f.write("\n")
def read_text(p):
    try:
        with open(p, encoding="utf-8") as f: return f.read()
    except FileNotFoundError as e: raise InputError(f"missing required file: {p}") from e
    except UnicodeDecodeError as e: raise InputError(f"file is not UTF-8 text: {p} ({e.reason} at byte {e.start})") from e
    except OSError as e: raise InputError(f"cannot read file {p}: {type(e).__name__}") from e
def write_text(p, t):
    with open(p, "w", encoding="utf-8", newline="\n") as f: f.write(t if t.endswith("\n") else t + "\n")
class Rows(list):
    """CSV rows with lower-cased, stripped header keys. `columns` lists the header; `malformed` lists data rows
    (1-based file row numbers) that carry more fields than the header."""
    columns = ()
    malformed = ()
def read_csv(p, required=True):
    try:
        with open(p, encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f); out = Rows(); bad = []
            for i, r in enumerate(rd, 2):
                if None in r: bad.append(i)
                out.append({(k or "").strip().lower(): ("" if v is None else v) for k, v in r.items() if k is not None})
            out.columns = tuple((c or "").strip().lower() for c in (rd.fieldnames or ())); out.malformed = tuple(bad)
            return out
    except FileNotFoundError as e:
        if required: raise InputError(f"missing required CSV file: {p}") from e
        return None
    except (csv.Error, UnicodeDecodeError) as e: raise InputError(f"malformed CSV in {p} (must be UTF-8 CSV): {e}") from e
    except OSError as e: raise InputError(f"cannot read CSV file {p}: {type(e).__name__}") from e
def missing_columns(rows, cols): return [c for c in cols if c not in rows.columns]

# ---------------------------------------------------------------- type / enum validation (fail closed)
def need(ok, msg):
    if not ok: raise InputError(msg)
def is_num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
_KINDS = {"obj": (dict, "an object"), "list": (list, "an array"), "str": (str, "a string"), "bool": (bool, "true or false")}
def field(d, key, kind, where, required=False, nullable=False, default=None):
    """Type-check d[key]. Absent -> default (or InputError when required); present-but-null is an error unless
    nullable. Wrong JSON types are a clean InputError, never a coercion."""
    if key not in d:
        need(not required, f"{where}.{key} is required; fail closed"); return default
    v = d[key]
    if v is None and nullable: return default
    if kind == "num01": ok, desc = is_num(v) and 0 <= v <= 1, "a number between 0 and 1"
    elif kind == "num": ok, desc = is_num(v), "a number"
    elif kind == "strlist": ok, desc = isinstance(v, list) and all(isinstance(x, str) for x in v), "an array of strings"
    elif kind == "objlist": ok, desc = isinstance(v, list) and all(isinstance(x, dict) for x in v), "an array of objects"
    else: t, desc = _KINDS[kind]; ok = isinstance(v, t)
    need(ok, f"{where}.{key} must be {desc}, got {type(v).__name__}; fail closed")
    return v
def esc_text(e, where):
    """Upstream escalations may be strings or objects; both survive as one string."""
    if isinstance(e, str): return e
    need(isinstance(e, dict), f"{where} entries must be strings or objects, got {type(e).__name__}; fail closed")
    head = next((e[k] for k in ("id", "escalation_id", "rule", "code") if isinstance(e.get(k), str) and e[k]), "")
    body = next((e[k] for k in ("message", "reason", "text", "summary", "detail") if isinstance(e.get(k), str) and e[k]), "")
    body = body or json.dumps(e, sort_keys=True, ensure_ascii=False)
    return f"{head}: {body}" if head else body
TRUE_VALUES = {"true", "yes", "1", "y"}; FALSE_VALUES = {"false", "no", "0", "n"}
NON_CONFIDENTIAL = {"internal", "public"}  # workspace-inventory-rules.md #2.3
def depends_on_knowledge(v):
    """Only an explicit false/no/0 is independent of prior knowledge; blank or unknown is dependent (#2.3)."""
    return (v or "").strip().lower() not in FALSE_VALUES
def client_confidential(v):
    """Only internal/public are non-confidential; blank or unknown classifications are treated as confidential."""
    return (v or "").strip().lower() not in NON_CONFIDENTIAL

# ---------------------------------------------------------------- normalisation
# Cyrillic/Greek letters that render like Latin letters. Folded after Cf stripping and NFKC so look-alike spellings
# of steering text still match (confidentiality-and-ethical-wall-rules.md #4.2).
CONFUSABLES = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "І": "I", "Ј": "J", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "Х": "X", "У": "Y", "Ѕ": "S", "Ԁ": "D", "Ԛ": "Q", "Ԝ": "W",
    "а": "a", "в": "b", "е": "e", "і": "i", "ј": "j", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p",
    "с": "c", "т": "t", "х": "x", "у": "y", "ѕ": "s", "ԁ": "d", "һ": "h", "ӏ": "l", "ԛ": "q", "ԝ": "w",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "Ϲ": "C",
    "α": "a", "β": "b", "ε": "e", "η": "n", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t",
    "υ": "u", "χ": "x", "ω": "w", "ϲ": "c", "ϳ": "j",
    # Armenian
    "\u0555": "O", "\u0585": "o", "\u054d": "U", "\u057d": "u", "\u0578": "n", "\u0570": "h", "\u0581": "g", "\u0566": "q",
    "\u0584": "p", "\u0561": "w", "\u053c": "L",
    # Cherokee (capitals; small forms are added below)
    "\u13aa": "A", "\u13f4": "B", "\u13df": "C", "\u13a0": "D", "\u13ac": "E", "\u13c0": "G", "\u13bb": "H", "\u13a5": "i",
    "\u13ab": "J", "\u13e6": "K", "\u13de": "L", "\u13b7": "M", "\u13e2": "P", "\u13d2": "R", "\u13da": "S", "\u13a2": "T",
    "\u13d9": "V", "\u13b3": "W", "\u13c3": "Z",
})
CONFUSABLES.update({ord(chr(k).lower()): v.lower() for k, v in list(CONFUSABLES.items()) if 0x13A0 <= k <= 0x13F5})
CONFUSABLE_CHARS = frozenset(chr(c) for c in CONFUSABLES)
# Scripts that never belong inside an otherwise-Latin word; fullwidth and mathematical letters fold to Latin under
# NFKC, so a token mixing them with plain Latin is flagged before folding (#4.2).
_ODD_SCRIPTS = ("CYRILLIC", "GREEK", "ARMENIAN", "CHEROKEE", "FULLWIDTH", "MATHEMATICAL")
_PUNCT = (("’", "'"), ("‘", "'"), ("‛", "'"), ("‐", "-"), ("‑", "-"), ("‒", "-"), ("–", "-"), ("—", "-"), ("―", "-"), ("“", '"'), ("”", '"'))
def strip_cf(s): return "".join(c for c in str(s) if unicodedata.category(c) != "Cf")
def norm(s):
    s = strip_cf(unicodedata.normalize("NFKC", strip_cf(s))).translate(CONFUSABLES).lower().translate(CONFUSABLES)
    for a, b in _PUNCT: s = s.replace(a, b)
    s = re.sub(r"[*`~]+", "", s).replace("_", " "); return re.sub(r"\s+", " ", s).strip()
def id_spaced(n):
    """Filenames and IDs read as words: separators between letters/digits become spaces (wall.lifted.docx)."""
    return re.sub(r"(?<=[a-z0-9])[._-]+(?=[a-z0-9])", " ", n)
def _script(c):
    if not c.isalpha(): return None
    n = unicodedata.name(c, "")
    if c in CONFUSABLE_CHARS: return "odd"
    if n.startswith("LATIN"): return "latin"
    return "odd" if n.startswith(_ODD_SCRIPTS) else None
def mixed_script(s):
    """True when one word mixes plain Latin letters with look-alike letters from another script or with fullwidth or
    mathematical letters (e.g. 'wаll' with Cyrillic 'а', 'wＡll', 'w𝐚ll')."""
    for tok in re.findall(r"\w+", strip_cf(s)):
        kinds = {_script(c) for c in tok}
        if "latin" in kinds and "odd" in kinds: return True
    return False

# ---------------------------------------------------------------- embedded-instruction tripwire
# SOWs, rosters and inventories legitimately mention AI programmes, systems, access requests, approvals, URLs and
# e-mail addresses. The families below look for intent, not one phrasing: text that addresses the assistant or
# reviewer, claims a wall/conflict status change, claims an exception or waiver, grants elevated rights or a roster
# place, suppresses a control, or moves material to an address (confidentiality-and-ethical-wall-rules.md #4.1-#4.5).
# A bare approval word ("pre-approved by the board", "conflicts check completed") is not a hit.
_AI = r"(?:ai|a\.i\.|assistant|copilot|llm|chatbot|claude|gpt|chatgpt|bot|onboarding bot)"
_AIR = r"(?:ai|a\.i\.|assistant|copilot|llm|chatbot|claude|gpt|chatgpt|bot|onboarding bot|reviewers?|review agent|pack reviewer)"
_ACT = r"(?:please|treat|mark|approve|clear|ignore|skip|include|add|grant|give|provision|remove|omit|drop|exclude|confirm|assign|share|send|forward|disregard|bypass|override|do not|don't|dont|you|leave|let|no need|move on|list|show|state|note|record|keep)"
_GUARD = r"(?:(?:the |any |all |these |this )?(?:ethical[- ])?walls?(?: register| check| review| status| restrictions?)?|conflicts? checks?|(?:engine|wall|embedded[- ]instruction|source) holds?|(?:the )?confidentiality (?:briefing|rules|terms)|(?:the )?(?:role|access) matrix|(?:wall |access |knowledge )?restrictions?|(?:the )?register)"
_NEG = r"(?<!not )(?<!never )(?<!n't )(?<!dont )(?<!no )"
_CONTACT = (r"(?:[a-z0-9._%+-]+\s*(?:@|\(at\)|\[at\]|\{at\}|<at>)\s*[a-z0-9-]+(?:\s*(?:\.|\(dot\)|\[dot\]|\{dot\}|<dot>|\s+dot\s+)\s*[a-z0-9-]+)+"
            r"|[a-z0-9._%+-]+\s+at\s+[a-z0-9-]+(?:\s+dot\s+[a-z0-9-]+)+|https?://|www\.|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|me|co|uk|biz|info|app|dev|cloud)/)")
_OBJ_FOLLOW = r"(?=\s+(?:this|these|it|them|the|a|all|everything|over|out|to|copies|copy))"
_SEND = (_NEG + r"\b(?:send|sends|sent|sending|re-?send|forward|forwards|forwarded|forwarding|fwd|e-?mail" + _OBJ_FOLLOW + r"|mail" + _OBJ_FOLLOW +
         r"|share|shares|sharing|copy|copies|copied|copying|cc|bcc|upload|uploads|uploaded|uploading|transmit|transfer|post(?!-)|sync|push|export"
         r"|airdrop|beam|deliver" + _OBJ_FOLLOW + r")\b")
_EXT = (r"(?:(?:personal|private|home|external|outside|non-firm|non-company|alternate|backup)\s+(?:e-?mail|mail|mailbox|inbox|address|account|drive|device|laptop|phone|cloud|storage|folder)"
        r"|outside (?:the )?(?:firm|company|engagement|tenant|organi[sz]ation)|\b(?:gmail|googlemail|hotmail|yahoo|outlook\.com|live\.com|proton(?:mail)?|icloud|dropbox|wetransfer|google drive|box\.com|usb(?: stick| drive| key)?|thumb drive)\b)")
_WALL = (r"(?:ethical[- ]?walls?\b|chinese walls?\b|information barriers?\b|ethical screens?\b|conflicts?[- ]screens?\b|(?:his|her|their|[a-z]+'s)\s+screen\b"
         r"|(?<![\w-])walls?\b(?![- ]?(?:chart|planner|calendar|board|display|poster|clock|mount|socket|paper|art|space|map)s?\b)"
         r"|conflicts?[- ](?:of[- ]interest|checks?|flags?|holds?|restrictions?|blocks?|bars?)\b|conflict of interest\b"
         r"|(?:wall|knowledge|access|conflicts?|matter|competitor|his|her|their)\s+restrictions?\b|[a-z]+'s\s+(?:wall\s+|conflict\s+|knowledge\s+|access\s+)?restrictions?\b"
         r"|restrictions?\s+(?:for|on|against)\s+(?:the\s+)?(?:joiner|new (?:joiner|analyst|starter|hire|team member)|analyst|consultant|him|her|them)\b"
         r"|(?:wall|conflicts?)\s+(?:register|status|blocks?|bars?|holds?|entry|entries|flags?)\b)")
_PRED = (r"(?:(?:has|have|had|was|were|is|are|got|gets|been|being|now|already|officially|formally|just|since|effectively|fully|finally|today|yesterday|recently)\s+)*"
         r"(?:lifted|waived|removed|cleared|resolved|closed|rescinded|revoked|withdrawn|expired|ended|dropped|signed[- ]?off|released|stood down|taken down|came down|come down|coming down"
         r"|disabled|switched off|turned off|suspended|retired|dissolved|gone|void(?:ed)?|cancell?ed|deleted|lapsed|overridden|bypassed|exempted|downgraded"
         r"|no longer\s+(?:in (?:force|effect|place)|appl(?:y|ies|icable)|relevant|needed|required|necessary|an issue|active|valid|exists?|binding|enforced)"
         r"|not\s+(?:required|needed|applicable|relevant|an issue|active|in (?:force|effect|place)|binding|enforced)"
         r"|n/a|out of date|outdated|stale|obsolete|historical(?: only)?|inactive|irrelevant|a formality)\b")
_REV = r"(?:lift|lifts|lifted|lifting|waive|waives|waived|remove|removes|removed|rescind|rescinded|revoke|revoked|drop|drops|dropped|took down|take down|taken down|disable|disabled|dissolve|dissolved|suspend|suspended|cleared|override|overrode|overridden)"
_JOINERISH = r"(?:joiner|analyst|new (?:joiner|analyst|starter|hire|team member)|consultant|he|she|they)"
_EXC = r"(?<!no )(?<!without )(?:exceptions?|exemptions?|waivers?|dispensations?|carve[- ]?outs?|special (?:permission|approval|dispensation|access)|one[- ]off (?:permission|approval|access))\b"
_WCTX = r"(?:walls?\b|ethical[- ]walls?\b|conflicts?\b|restrictions?\b|information barriers?\b|(?:wall|conflicts?) registers?\b|joiner\b|new (?:joiner|analyst|starter|hire|team member)\b|clearance\b)"
_ELEV = r"(?:owner|owners|ownership|co-?owner|admin|admins|administrator|administrators|full[- ]control|full access|elevated|super ?user|site[- ]collection(?: admin(?:istrator)?)?|global admin|tenant admin|edit(?:or)? rights|write)"
_RIGHTS = r"(?:rights|access|permissions?|privileges?|role|roles|level|control)\b"
_GRANTV = (_NEG + r"\b(?:grant|grants|granted|granting|give|gives|given|giving|provision|provisioned|assign|assigned|request|requests|requested|requesting|upgrade|upgraded"
           r"|elevate|elevated|promote|promoted|add|added|set up|enable|enabled|receive|receives|get|gets|need|needs|require|requires|to have)\b")
_PACKN = r"(?:(?:the|this)\s+(?:onboarding\s+|mobili[sz]ation\s+|joiner\s+)?(?:pack|briefing)|(?:onboarding|mobili[sz]ation|joiner)\s+(?:pack|briefing))"
_PACK = r"(?:this|these|it|the (?:full |whole |complete |finished |final )?(?:onboarding |mobili[sz]ation )?(?:pack|draft|briefing|roster|checklist|knowledge|digest|deliverables?|materials?|documents?|files?|assets?|playbook))"
PATS = [
 ("assistant_addressed", re.compile(
    r"\b(?:note|message|instruction|instructions|reminder|comment)s? (?:to|for) (?:the |any |all )?" + _AIR + r"\b"
    r"|\b(?:hey|hi|hello|dear|attention|attn) (?:the )?" + _AIR + r"\b|\bheads[- ]up (?:for|to) (?:the )?" + _AIR + r"\b"
    r"|\b" + _AIR + r"\s*[:,\]\)>]+\s*" + _ACT + r"\b"
    r"|(?:^|[.;!?:]\s*|\b(?:hey|hi|hello|dear|ok|okay|so|now)\s+)(?:the\s+)?" + _AIR + r"\s*,\s*(?!(?:[\w-]+,?\s+){1,3}(?:and|or|&)\s)(?=[a-z])"
    r"|\b" + _AIR + r"\s+(?:please|kindly)\b"
    r"|\b" + _AI + r" (?:should|must|needs to|is to|is instructed to|can|may) (?:safely |just )?(?:not )?(?:treat|mark|approve|clear|ignore|skip|include|grant|provision|omit|drop|exclude|disregard|bypass|override|leave|list|show)\b"
    r"|\b(?:whoever|anyone|anybody|the person|the colleague)\s+(?:who\s+)?(?:is\s+)?(?:draft|build|assembl|prepar|compil|generat|review|writ|put|pull|creat)\w*\s+(?:together\s+)?(?:this|the)\s+(?:onboarding\s+|mobili[sz]ation\s+|joiner\s+|draft\s+)?(?:pack|briefing|digest|plan|checklist|document|draft)\b"
    r"|\bwhen\s+(?:you|the assistant|the tool|copilot|the ai|the bot|the model|the system)\s+(?:draft|build|assembl|prepar|generat|writ|compil|creat|run)\w*"
    r"|\b" + _PACKN + r"\s+(?:should|must|needs? to|is to|can|may|will)\s+(?:say|state|show|list|record|note|describe|present|mark|treat|read|indicate|confirm)\b[^.;!?]{0,50}?\b(?:clear(?:ed)?|unrestricted|no (?:wall|restrictions?|conflicts?|holds?)|approved|exempt|confirmed|assigned|lifted|waived)\b"
    r"|\b" + _PACKN + r"\s+(?:should|must|needs? to|is to|can|may|will)\s+(?:omit|exclude|leave out|skip|drop|remove|hide|not (?:mention|include|show|list|contain))\b")),
 ("override_rules", re.compile(r"\b(?:ignore|disregard|override|bypass|skip|circumvent)\b.{0,30}\b(?:(?:previous|prior|above|earlier|all|your|these|the) instructions|" + _GUARD + r")\b"
    r"|\b(?:ignore|disregard)\s+(?:what|whatever)\s+(?:the\s+)?(?:wall\s+|conflicts?\s+)?(?:register|risk|conflicts?|compliance)\s+says\b")),
 ("suppress_control", re.compile(
    r"\b(?:do not|don't|dont|must not|should not|never)\s+(?:flag|hold|escalate|surface|block)\s+(?:this|these|it|the joiner|this joiner)\b"
    r"|\b(?:do not|don't|dont|must not|should not|never|no need to)\s+(?:raise|flag|surface|escalate|apply|check|review|restrict|enforce)\s+(?:a |any |the )?(?:hold|holds|walls?|restrictions?|wall (?:check|review)|conflict checks?|briefing|knowledge|access)\b"
    r"|\b(?:omit|remove|drop|leave out|suppress|hide|delete)\b.{0,20}\b(?:(?:the )?(?:confidentiality|ethical[- ]wall|wall) (?:briefing|section|restrictions?|warning)|(?:the |all |any )?(?:escalations?|(?:engine|wall|embedded[- ]instruction|source) holds?|holds? and escalations|holds section))\b"
    r"|\b(?:no need|not necessary|unnecessary|needn't|need not|don't bother|do not bother|no point|not worth)\s+(?:to\s+|in\s+)?(?:check|checking|consult|consulting|run|running|look(?:ing)? at|apply|applying|use|using|refer(?:ring)? to|review|reviewing|re-?check|verify|verifying|screen|screening|include|including|add|adding|raise|raising|brief|briefing|mention|mentioning|wait(?:ing)? for)\s+(?:against\s+|with\s+|on\s+|for\s+)?(?:the\s+|any\s+|a\s+|its\s+|their\s+)?(?:ethical[- ])?(?:walls?|registers?|wall registers?|conflicts?(?: checks?| registers?| team)?|restrictions?|briefing|confidentiality (?:briefing|section|rules)|holds?|risk(?: team)?|compliance|screening|clearance)\b"
    r"|\b(?:skip|leave out|drop|omit|bypass|ignore|cut|delete|remove)\s+(?:the\s+|any\s+|all\s+)?(?:ethical[- ])?(?:wall|walls|restrictions?|confidentiality|conflicts?)\s*(?:section|briefing|part|step|check|review|register|paragraph|notes?|warning)?\b"
    r"|\b(?:leave|keep)\s+(?:the\s+|this\s+)?(?:wall|restrictions?|confidentiality|holds?|escalations?)\s+(?:section\s+|briefing\s+|list\s+)?(?:blank|empty|out|off)\b"
    r"|\b(?:do not|don't|dont|never|no need to)\s+(?:brief|tell|inform|warn|mention)\b[^.;!?]{0,40}?\b(?:walls?|restrictions?|conflicts?|register|confidentiality)\b"
    r"|\b(?:restrictions?|walls?|register|wall briefing|confidentiality briefing)\b[^.;!?]{0,40}?\b(?:can|may|should|could)\s+(?:safely\s+|just\s+)?be\s+(?:ignored|disregarded|skipped|bypassed|overlooked|waived|dropped|removed|omitted|left out)\b")),
 ("approval_claim", re.compile(r"\b(?:wall[- ]cleared|pre[- ]?cleared|already (?:wall[- ])?cleared|cleared by (?:risk|compliance|the gc|general counsel|legal|conflicts)|no (?:wall|conflicts?) (?:review|check)s? (?:is |are )?(?:needed|required))\b|\b(?:ethical walls?|walls?|conflicts?|wall restrictions?)\s+(?:has |have |was |were |is |are )?(?:been )?(?:lifted|waived|suspended|no longer appl(?:y|ies)|not required|not applicable)\b|\bpre[- ]?approved\b.{0,30}\b(?:access|admin|knowledge|joiner|wall|exception|exemption)\b|\b(?:treat|mark|consider|record|classify|list)\s+(?:\S+\s+){0,4}?as\s+(?:(?:wall[- ])?cleared|unrestricted|exempt)\b|\b(?:consider|deem)\s+(?:this|that|it|the|these|our)\b(?:\s+\S+){0,3}?\s+(?:already\s+|fully\s+)?(?:approved|cleared|signed[- ]?off|exempt|unrestricted|conflict[- ]free|wall[- ]free)(?=\s*(?:[.!,;:]|$)|\s+(?:and|for|by|now|already|too)\b)|\b(?:treat|consider|regard|deem|handle|process)\s+(?:\S+\s+){0,4}?as\s+(?:already\s+|fully\s+|pre-?)?(?:approved|clear|cleared|signed[- ]?off|green|resolved|allowed|permitted|ok|okay|exempt|unrestricted|not restricted|no conflict|conflict[- ]free|wall[- ]free|low[- ]risk)\b"
    r"|\bno need for (?:a |an |any |the )?(?:ethical[- ])?(?:wall|conflicts?|clearance|risk|independence) (?:review|check|clearance|sign[- ]?off|screening)s?\b"
    r"|\bno (?:ethical[- ])?(?:wall|conflicts?|clearance|independence) (?:review|check|clearance|sign[- ]?off|screening)s? (?:is |are |was |were )?(?:needed|required|necessary|due|applicable)\b"
    r"|\b(?:ethical[- ])?(?:wall|conflicts?) (?:review|check|clearance|screening)s? (?:(?:is|are|was|were) (?:not|no longer|never)|isn't|aren't|wasn't|weren't|not|no longer) (?:needed|required|necessary|applicable)\b"
    r"|\bas (?:confirmed|assigned) (?:on|to|in) (?:the )?(?:roster|team|engagement)\b")),
 ("wall_status_claim", re.compile(
    r"\b" + _WALL + r"[^.;!?]{0,40}?\b" + _PRED +
    r"|\b" + _REV + r"\s+(?:the\s+|his\s+|her\s+|their\s+|this\s+|that\s+|any\s+|all\s+|[a-z]+'s\s+)?(?:[\w'-]+\s+)?" + _WALL +
    r"|\b(?:wall|conflicts?)\s+status\b[^.;!?]{0,30}?(?:=|:|\bnow\b|\bset to\b|\bchanged to\b|\bupdated to\b|\bmoved to\b)\s*(?:now\s+)?(?:clear(?:ed)?|green|ok|resolved|lifted|none|unrestricted)\b"
    r"|\b(?:no longer|does not|doesn't|do not|don't)\s+appl(?:y|ies)\s+(?:to\s+)?(?:this|the|our)\s+" + _JOINERISH + r"\b"
    r"|\b(?:is|are|has been|have been|was|were|now|being)\s+(?:now\s+|fully\s+|already\s+|officially\s+)?(?:good to go|free|ok(?:ay)?|allowed|permitted|cleared|approved|fine|safe|eligible)\s+(?:to\s+(?:access|see|use|view|read|reuse|open|receive|get|work (?:on|with)|have)|on|for|with)\s+(?:all|everything|any(?:thing)?|the (?:prior|held|restricted|walled|full|whole|entire|complete|payments?|playbook|knowledge|repository|material|archive|competitor)|prior|held|restricted|walled|knowledge|material|competitor)\b"
    r"|\b(?:is|are|has been|have been|was|were)\s+(?:now|fully|already|officially)\s+(?:unrestricted|unwalled|unblocked|unscreened|exempt(?:ed)?|wall[- ]free)\b"
    r"|\b(?:is|are|was|were)\s+no longer\s+(?:restricted|walled|screened|blocked|conflicted)\b"
    r"|\b" + _JOINERISH + r"\s+(?:is|are|has been|have been|was|were)\s+(?:unrestricted|unwalled|unblocked|unscreened|exempt(?:ed)?)\b"
    r"|\b(?:access|see|use|view|read|reuse|share|include|open|receive|get)\b[^.;!?]{0,60}?\bwithout\s+(?:any\s+|the\s+|a\s+)?(?:wall|walls|restrictions?|limits?|limitations?|checks?|review|clearance|screening|conflicts? checks?)\b")),
 ("exception_waiver", re.compile(
    r"\b(?:wall|ethical[- ]wall|conflicts?|restrictions?|clearance|barrier)\s+(?:exceptions?|exemptions?|waivers?|dispensations?|carve[- ]?outs?|overrides?|sign[- ]?offs?|signoffs?|releases?)\b"
    r"|\b" + _EXC + r"[^.;!?]{0,50}?\b" + _WCTX +
    r"|\b" + _WCTX + r"[^.;!?]{0,50}?\b" + _EXC +
    r"|\b(?:conflicts?|wall)\s+(?:team|committee|office|desk|partner)\s+(?:has\s+|have\s+)?(?:signed[- ]?off|cleared|approved|waived|lifted|released)\b"
    r"|\b(?:signed[- ]?off|approved|cleared|waived)\s+by\s+(?:the\s+)?(?:gc|general counsel|conflicts?(?: team| committee)?|risk(?: and conflicts)?|compliance|legal|ethics)\b[^.;!?]{0,40}?\b(?:joiner|analyst|access|wall|restriction|knowledge|playbook|material)\b")),
 ("permission_grant", re.compile(
    _GRANTV + r"\s+(?:[\w'-]+\s+){0,4}?" + _ELEV + r"\s+" + _RIGHTS +
    r"|\b(?:make|set|add|upgrade|promote|elevate|appoint|nominate)\s+(?:[\w'-]+\s+){0,3}?(?:as|to)\s+(?:an?\s+|the\s+)?(?:(?:site|workspace|team|channel|planner|sharepoint|repository|global|tenant|site[- ]collection)\s+)?(?:owner|co-?owner|admin|administrator)s?\b"
    r"|\bmake\s+(?:[\w'-]+\s+){0,2}?(?:an?|the)\s+(?:(?:site|workspace|team|channel|planner)\s+)?(?:owner|co-?owner|admin|administrator)\b"
    r"|\b(?:full[- ]control|owner|admin(?:istrator)?)\s+(?:on|over|of|to)\s+(?:all|every|each|the (?:engagement|client|team|knowledge|delivery))\b"
    r"|\b(?:add|move|put|list|promote|include|record|mark)\b[^.;!?]{0,40}?\b(?:roster|team(?: list)?|staffing list)\b[^.;!?]{0,20}?\bas (?:a |an )?(?:confirmed|assigned)\b"
    r"|\b(?:treat|mark|list|record|show)\s+(?:[\w'-]+\s+){1,3}?as\s+(?:a\s+)?(?:confirmed|assigned)\s+(?:team member|member|joiner|analyst|consultant|on the roster)\b")),
 ("scope_escalation", re.compile(r"\b(?:include|add|surface|share|attach|use)\b.{0,40}\b(?:held|withheld|restricted|walled|uncleared|unreleased)\s+(?:assets?|knowledge|material|deliverables?|records?|workspaces?)\b|\bregardless of\s+(?:the\s+)?(?:clearance|walls?|restrictions?|holds?|permissions?|role matrix|confidentiality|register)\b|\b(?:grant|give|add|provision)\b.{0,30}\badmin(?:istrator)?\b.{0,40}\b(?:every|all|each)\b|\bshare everything\b|\b(?:proceed|go ahead|continue|carry on|start)\s+with\s+(?:full|all|complete|unrestricted|open|everything)\s+(?:[\w-]+\s+)?(?:access|visibility)\b(?!\s+(?:requests?|forms?|reviews?|checklists?|process|procedure))|\b(?:add|move|promote)\b.{0,30}\bto the confirmed roster\b|\bassignment (?:is|has been) (?:approved|confirmed) (?:by|per)\b")),
 ("send_to_address", re.compile(_SEND + r".*?" + _CONTACT + r"|" + _CONTACT + r".*?" + _SEND)),
 ("external_destination", re.compile(_SEND + r"[^.;!?]{0,80}?" + _EXT + r"|\b(?:forward|send|e-?mail|share|upload|transmit|cc)\s+" + _PACK + r"\b.{0,60}" + _CONTACT)),
]
WITHHELD = "[withheld - source text held for embedded-instruction review, see Escalations and holds]"  # #4.3
# hits() is the single detector entry point: scan, pair_hits, scan_lines, scan_rows and every engine call site go through
# it, so a shared family-based detector can replace its body without touching the per-line, pair or per-field scanning.
def hits(s):
    if s is None: return []
    s = s if isinstance(s, str) else str(s)
    n = norm(s); variants = (n, id_spaced(n)) if id_spaced(n) != n else (n,)
    out = [name for name, p in PATS if any(p.search(v) for v in variants)]
    if mixed_script(s): out.append("confusable_mixed_script")
    return out
def hold(path, text, hit):
    d = hashlib.sha256(strip_cf(text or "").encode()).hexdigest()[:12]
    why = ",".join(hit) if isinstance(hit, (list, tuple)) else hit
    return {"hold_id": f"HOLD-{d}", "path": path, "reason": f"embedded_instruction:{why}", "source": "engine:safety_text", "confidence": 0.99, "citation": "confidentiality-and-ethical-wall-rules.md #4.1-#4.5"}
def scan(v, path="$"):
    """One hold per flagged string value (all matching families in one reason)."""
    out = []
    if isinstance(v, dict):
        for k, x in v.items(): out += scan(x, f"{path}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v): out += scan(x, f"{path}[{i}]")
    elif isinstance(v, str):
        h = hits(v)
        if h: out.append(hold(path, v, h))
    return out
# A claim can be split across two labelled lines or two adjacent fields ("...the ethical wall has been" /
# "Key dates: lifted for Taylor Reed"). Pairs are read without their field labels; when a pair trips the wire and
# neither half does on its own, both halves are withheld (confidentiality-and-ethical-wall-rules.md #4.5).
LABEL_RE = re.compile(r"^\s*(?:[-*>]\s*)?(?:\*\*)?[A-Za-z][A-Za-z0-9 /&()'-]{0,40}?(?:\*\*)?\s*:\s+")
def unlabel(s): return LABEL_RE.sub("", s or "", count=1).strip()
def split_items(v):
    if (v or "").strip() == WITHHELD: return [WITHHELD]
    return [x.strip(" -") for x in re.split(r";|\n-", v or "") if x.strip(" -")]
def pair_hits(a, b):
    if not (a or "").strip() or not (b or "").strip() or hits(a) or hits(b): return []
    ua, ub = unlabel(a), unlabel(b)
    if not ua or not ub: return []
    cands = [ua + " " + ub]; ia, ib = split_items(ua), split_items(ub)
    if ia and ib: cands.append(ia[-1] + " " + ib[0])
    out = []
    for c in cands:
        for h in hits(c):
            if h not in out: out.append(h)
    return out + ["split_across_fields"] if out else []
def scan_lines(text, path):
    """Scan a free-text source line by line and pair by pair. Returns (holds, text with pair-flagged lines replaced
    by their label and the neutral placeholder)."""
    lines = (text or "").splitlines(); out = []; bad = set()
    for n, line in enumerate(lines, 1):
        h = hits(line)
        if h: out.append(hold(f"{path} line {n}", line, h))
    for n in range(len(lines) - 1):
        h = pair_hits(lines[n], lines[n + 1])
        if h: out.append(hold(f"{path} lines {n + 1}-{n + 2}", lines[n] + "\n" + lines[n + 1], h)); bad |= {n, n + 1}
    safe = [((LABEL_RE.match(l).group(0) if LABEL_RE.match(l) else "") + WITHHELD) if i in bad else l for i, l in enumerate(lines)]
    return out, "\n".join(safe) + ("\n" if (text or "").endswith("\n") else "")
def scan_text(text, path): return scan_lines(text, path)[0]
def scan_rows(rows, label):
    """One hold per flagged cell, plus pair holds for claims split across adjacent cells in a row or the same column
    in adjacent rows. Pair-flagged cells are replaced in place by the placeholder so they never travel (#4.5)."""
    out = []; rows = rows or []
    for i, r in enumerate(rows, 2):
        for k, v in r.items():
            h = hits(v)
            if h: out.append(hold(f"{label} row {i}.{k}", v, h))
    pairs = []
    for i, r in enumerate(rows):
        ks = [k for k in r if (r.get(k) or "").strip()]
        pairs += [((i, a), (i, b)) for a, b in zip(ks, ks[1:])]
        if i + 1 < len(rows):
            pairs += [((i, k), (i + 1, k)) for k in r if (r.get(k) or "").strip() and (rows[i + 1].get(k) or "").strip()]
    bad = []
    for (i, a), (j, b) in pairs:
        h = pair_hits(rows[i][a], rows[j][b])
        if h:
            where = f"{label} row {i + 2}.{a}+{b}" if i == j else f"{label} rows {i + 2}-{j + 2}.{a}"
            out.append(hold(where, rows[i][a] + "\n" + rows[j][b], h)); bad += [(i, a), (j, b)]
    for i, k in bad: rows[i][k] = WITHHELD
    return out
def redact(v):
    """Replace every flagged string with the neutral placeholder; flagged text never travels to any output (#4.3)."""
    if isinstance(v, dict): return {k: redact(x) for k, x in v.items()}
    if isinstance(v, list): return [redact(x) for x in v]
    if isinstance(v, str) and hits(v): return WITHHELD
    return v

# ---------------------------------------------------------------- other-client screen
# Another client's name or matter ID never reaches any output, wherever it appears: SOW lines, roster
# responsibilities, workspace names, knowledge titles and descriptions, escalations or briefing topics. Identities
# come from the inputs themselves (other wall-register rows, a closeout record from another engagement, a staffing
# file for another client). Matches are withheld, held and escalated; the hold never repeats the name
# (confidentiality-and-ethical-wall-rules.md #3.3).
OTHER_WITHHELD = "[withheld - names another client or matter, see Escalations and holds]"
GENERIC = {"the", "and", "for", "of", "bank", "banks", "credit", "union", "partners", "capital", "group", "holdings", "inc", "llc", "ltd", "limited", "corp", "corporation", "company", "insurance", "assurance", "mutual", "health", "healthcare", "clinic", "clinics", "hospital", "financial", "finance", "trust", "llp", "plc", "retail", "services", "systems", "solutions", "national", "first", "global", "engagement", "matter", "migration", "payments", "payment", "modernization", "modernisation", "program", "programme", "project", "workstream", "material", "design", "prior", "walled", "competitor", "client", "previously", "staffed", "restricted", "restriction", "risk", "conflicts", "register", "knowledge", "repository", "sharepoint", "teams", "planner", "channel", "delivery", "may", "not", "access", "discuss", "wall", "ethical", "new", "north", "south", "east", "west", "american", "international", "digital", "data"}
SCREEN_SKIP = {"contract_version", "run_metadata", "provenance", "holds", "source", "confidence", "relevance_score", "fit_score", "status", "assignment_status", "review_status", "clearance_state", "requested_permission", "workspace_type", "type", "hold_reasons", "label", "sections"}
def words(*xs): return {w for x in xs for w in re.findall(r"[a-z0-9]+", id_spaced(norm(x or "")))}
def client_terms(names, own):
    """[(normalised full name or ID, distinctive words)] for every other-client identity. IDs (anything with a digit)
    match only in full; names also match on any distinctive word that is not shared with this engagement."""
    out = []; seen = set()
    for nm in names:
        if not isinstance(nm, str) or not nm.strip(): continue
        full = id_spaced(norm(nm))
        if full in seen or (words(nm) and words(nm) <= own): continue
        seen.add(full)
        dist = set() if re.search(r"\d", nm) else {w for w in words(nm) - own - GENERIC if len(w) >= 3}
        out.append((full, dist))
    return out
def names_client(text, terms):
    if not terms or not isinstance(text, str) or not text.strip(): return False
    t = id_spaced(norm(text)); tw = set(re.findall(r"[a-z0-9]+", t))
    for full, dist in terms:
        if re.search(r"(?<![a-z0-9])" + re.escape(full) + r"(?![a-z0-9])", t) or dist & tw: return True
    return False
def screen_other(doc, terms, engine, prefix=""):
    """Withhold every string in doc that names another client or matter. Returns (screened doc, holds)."""
    holds = []
    def walk(v, path):
        if isinstance(v, dict): return {k: (x if k in SCREEN_SKIP else walk(x, f"{path}.{k}" if path else k)) for k, x in v.items()}
        if isinstance(v, list): return [walk(x, f"{path}[{i}]") for i, x in enumerate(v)]
        if isinstance(v, str) and v not in (WITHHELD, OTHER_WITHHELD) and names_client(v, terms):
            holds.append(other_hold(f"{prefix}{path}", v, engine)); return OTHER_WITHHELD
        return v
    return (walk(doc, "") if terms else doc), holds
def other_hold(path, text, engine):
    return {"hold_id": "HOLD-OTHER-CLIENT-" + hashlib.sha256(strip_cf(text).encode()).hexdigest()[:12], "path": path, "reason": "text names another client or matter (name not repeated); withheld from every output", "source": engine, "confidence": 0.97, "citation": "confidentiality-and-ethical-wall-rules.md #3.3"}
def other_escalation(n): return f"{n} field(s) withheld because they name another client or matter; Risk/Conflicts review before the pack is shared (confidentiality-and-ethical-wall-rules.md #3.3)"

# ---------------------------------------------------------------- contract validation of pipeline inputs
# Every engine validates the intermediate document it reads against the shared contract: nested types, list
# element types, enums and ranges. A violation is a clean InputError, never a coercion
# (confidentiality-and-ethical-wall-rules.md #1.3).
_JT = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
def _contract():
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "contracts", CONTRACT_VERSION + ".json")
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError) as e: raise InputError(f"bundled contract schema unreadable ({p}); fail closed") from e
def _type_ok(v, t):
    if t == "number": return is_num(v)
    if t == "integer": return isinstance(v, int) and not isinstance(v, bool)
    return isinstance(v, _JT[t])
def _validate(v, s, path, root, lenient):
    if path in lenient: return
    if "$ref" in s: s = root["$defs"][s["$ref"].rsplit("/", 1)[1]]
    if "type" in s:
        ts = s["type"] if isinstance(s["type"], list) else [s["type"]]
        need(any(_type_ok(v, t) for t in ts), f"{path} must be {' or '.join(ts)}, got {type(v).__name__}; fail closed")
    if "const" in s: need(v == s["const"], f"{path} must be {s['const']!r}, got {v!r}; fail closed")
    if "enum" in s: need(v in s["enum"], f"{path} has unrecognised value {v!r}; expected one of {', '.join(map(str, s['enum']))}; fail closed")
    if is_num(v):
        if "minimum" in s: need(v >= s["minimum"], f"{path} must be >= {s['minimum']}; fail closed")
        if "maximum" in s: need(v <= s["maximum"], f"{path} must be <= {s['maximum']}; fail closed")
    if isinstance(v, dict):
        for k in s.get("required", []): need(k in v, f"{path}.{k} is required; fail closed")
        for k, sub in s.get("properties", {}).items():
            if k in v: _validate(v[k], sub, f"{path}.{k}", root, lenient)
    if isinstance(v, list) and "items" in s:
        for i, x in enumerate(v): _validate(x, s["items"], f"{path}[{i}]", root, lenient)
def check_contract(doc, where, lenient=()):
    c = _contract(); _validate(doc, c, where, c, {f"{where}.{x}" for x in lenient})
def dedup_holds(holds):
    seen = set(); out = []
    for h in holds:
        key = (h.get("hold_id"), h.get("path"), h.get("reason"))
        if key not in seen: seen.add(key); out.append(h)
    return out
def toks(*parts):
    stop = {"the", "and", "for", "with", "from", "into", "client", "engagement", "team", "work", "draft", "record"}
    return {x for p in parts for x in re.findall(r"[a-z0-9]+", norm(p or "")) if len(x) > 2 and x not in stop}
def guard(fn):
    try: return fn()
    except InputError as e: raise SystemExit(f"InputError: {e}")
    except (KeyError, TypeError, ValueError, AttributeError) as e: raise SystemExit(f"InputError: malformed input ({type(e).__name__}: {e}); fail closed")
