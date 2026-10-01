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
# Look-alike letters folded to Latin after Cf stripping and NFKC. Used for identifier matching (other-client names and
# matter IDs, #3.3; register rows); steering detection does its own folding inside steering_guard (#4.2).
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
_PUNCT = (("’", "'"), ("‘", "'"), ("‛", "'"), ("‐", "-"), ("‑", "-"), ("‒", "-"), ("–", "-"), ("—", "-"), ("―", "-"), ("“", '"'), ("”", '"'))
def strip_cf(s): return "".join(c for c in str(s) if unicodedata.category(c) != "Cf")
def norm(s):
    s = strip_cf(unicodedata.normalize("NFKC", strip_cf(s))).translate(CONFUSABLES).lower().translate(CONFUSABLES)
    for a, b in _PUNCT: s = s.replace(a, b)
    s = re.sub(r"[*`~]+", "", s).replace("_", " "); return re.sub(r"\s+", " ", s).strip()
def id_spaced(n):
    """Filenames and IDs read as words: separators between letters/digits become spaces (wall.lifted.docx)."""
    return re.sub(r"(?<=[a-z0-9])[._-]+(?=[a-z0-9])", " ", n)
# ---------------------------------------------------------------- embedded-instruction tripwire
# Steering detection is the shared, family-based steering_guard module (vendored byte-identically; never edited
# here). Plugin vocabulary reaches it only through its hooks. Families: addressee, verdict, suppression,
# rule_override, authority, scope, exfiltration, mixed_script, split, oversize
# (confidentiality-and-ethical-wall-rules.md #4.1-#4.5).
import steering_guard as sg
HOOKS = {"extra_verdict_words": ("wall cleared", "unrestricted", "access approved"),
         "extra_rule_nouns": ("clearance", "role matrix", "ethical wall", "conflict check")}
# The engagement's own client and firm domains (declared in the signed SOW or engagement letter) are the only
# trusted destinations; a send/share verb next to any other e-mail address or URL holds (#4.4).
_TRUSTED = ()
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
UNTRUSTABLE_DOMAINS = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com", "yahoo.com", "ymail.com", "aol.com", "icloud.com", "me.com", "mac.com", "proton.me", "protonmail.com", "pm.me", "gmx.com", "gmx.net", "mail.com", "zoho.com", "yandex.com", "tutanota.com", "dropbox.com", "wetransfer.com", "box.com", "google.com", "drive.google.com", "onedrive.live.com", "1drv.ms", "sharepoint.com", "onmicrosoft.com", "github.com", "pastebin.com", "example.com", "example.net", "example.org"}
def domain_ok(d): return isinstance(d, str) and bool(DOMAIN_RE.match(d)) and d not in UNTRUSTABLE_DOMAINS
def set_trusted_domains(domains):
    """Trust only well-formed, non-consumer domains; anything else is ignored (trusting less only holds more)."""
    global _TRUSTED
    _TRUSTED = tuple(sorted({d.strip().lower().lstrip("@.") for d in (domains or []) if isinstance(d, str) and domain_ok(d.strip().lower().lstrip("@."))}))
    return _TRUSTED
def hooks(): return dict(HOOKS, trusted_domains=_TRUSTED)
OVERSIZE_REASON = "oversize: too long to screen for embedded instructions; not scanned, held for human review"
WITHHELD = "[withheld - source text held for embedded-instruction review, see Escalations and holds]"  # #4.3
def _families(found):
    out = []
    for h in found:
        if h.family not in out: out.append(h.family)
    return ["oversize"] if "oversize" in out else out
# hits() is the single detector entry point: scan, pair_hits, scan_lines, scan_rows and every engine call site go
# through it (and through record_hits for multi-field records).
def hits(s):
    if s is None: return []
    return _families(sg.scan(s if isinstance(s, str) else str(s), **hooks()))
def record_hits(fields):
    """Families for a multi-field record: per-field hits, or ['split_across_fields'] when only the join of the
    fields trips, or ['oversize'] when the join is too long to screen (#4.5)."""
    fields = {k: v for k, v in fields.items() if isinstance(v, str)}
    fam = _families(sg.scan_fields(fields, **hooks()))
    if not fam and len(fields) > 2:
        # A split can straddle an unrelated field ("...please treat" / reason / "these lines as approved"): every
        # ordered pair of a record's few prose fields is read too.
        ks = list(fields)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                fam = _families(sg.scan_fields({ks[i]: fields[ks[i]], ks[j]: fields[ks[j]]}, **hooks()))
                if fam: break
            if fam: break
    return ["split_across_fields" if f == "split" else f for f in fam]
def hold(path, text, hit):
    d = hashlib.sha256(strip_cf(text or "").encode()).hexdigest()[:12]
    why = ",".join(hit) if isinstance(hit, (list, tuple)) else hit
    reason = OVERSIZE_REASON if "oversize" in (hit if isinstance(hit, (list, tuple)) else [hit]) else f"embedded_instruction:{why}"
    return {"hold_id": f"HOLD-{d}", "path": path, "reason": reason, "source": "engine:safety_text", "confidence": 0.99, "citation": "confidentiality-and-ethical-wall-rules.md #4.1-#4.5"}
def scan(v, path="$"):
    """One hold per flagged string value (all matching families in one reason)."""
    out = []
    if isinstance(v, dict):
        for k, x in v.items(): out += scan(x, f"{path}.{k}")
        if not out:
            h = record_hits(free_text(v))
            if h: out.append(hold(f"{path} (fields joined)", json.dumps(free_text(v), sort_keys=True, ensure_ascii=False), h))
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
STRUCTURED_KEYS = {"citation", "citations", "system", "platform", "depends_on_knowledge", "verdict", "blocking_rule"}
def prose_key(k):
    """Identifiers, enums, permissions, classifications, sources and citations are scanned cell by cell but are not
    prose: joining them ("clear" + "row 5") manufactures sentences no one wrote, so they never join a record or pair."""
    k = str(k)
    return k not in SCREEN_SKIP and k not in STRUCTURED_KEYS and not k.endswith(("_id", "_ids", "_status", "_permission", "_classification", "_type"))
def free_text(d):
    """The free-text string fields of a record (see prose_key)."""
    return {k: v for k, v in d.items() if isinstance(v, str) and v.strip() and v not in (WITHHELD, OTHER_WITHHELD) and prose_key(k)}
def pair_hits(a, b):
    """Adjacent lines, items or cells read together (labels removed by steering_guard.scan_fields). Fires only when
    the pair trips and neither half does on its own; the last item of a and the first item of b are also paired."""
    if not (a or "").strip() or not (b or "").strip() or hits(a) or hits(b): return []
    ua, ub = unlabel(a), unlabel(b)
    if not ua or not ub: return []
    cands = [(ua, ub)]; ia, ib = split_items(ua), split_items(ub)
    if ia and ib and (ia[-1], ib[0]) != (ua, ub): cands.append((ia[-1], ib[0]))
    for x, y in cands:
        h = record_hits({"a": x, "b": y})
        if h: return h if "oversize" in h else ["split_across_fields"]
    return []
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
        ks = [k for k in r if prose_key(k) and (r.get(k) or "").strip()]
        pairs += [((i, a), (i, b)) for a, b in zip(ks, ks[1:])]
        if i + 1 < len(rows):
            pairs += [((i, k), (i + 1, k)) for k in ks if (rows[i + 1].get(k) or "").strip()]
    bad = []
    for (i, a), (j, b) in pairs:
        h = pair_hits(rows[i][a], rows[j][b])
        if h:
            where = f"{label} row {i + 2}.{a}+{b}" if i == j else f"{label} rows {i + 2}-{j + 2}.{a}"
            out.append(hold(where, rows[i][a] + "\n" + rows[j][b], h)); bad += [(i, a), (j, b)]
    # A row is one record: when only the join of all its cells trips, every cell is withheld and the row held (#4.5).
    hit_rows = {i for i, _ in bad} | {i - 2 for i, r in enumerate(rows, 2) for v in r.values() if hits(v)}
    for i, r in enumerate(rows):
        if i in hit_rows: continue
        ft = free_text(r); h = record_hits(ft) if len(ft) > 1 else []
        if h:
            out.append(hold(f"{label} row {i + 2} (fields joined)", "\n".join(ft.values()), h))
            bad += [(i, k) for k in ft]
    for i, k in bad: rows[i][k] = WITHHELD
    return out
def redact(v):
    """Replace every flagged string with the neutral placeholder; flagged text never travels to any output (#4.3)."""
    if isinstance(v, dict):
        r = {k: redact(x) for k, x in v.items()}; ft = free_text(r)
        if ft and record_hits(ft): r.update({k: WITHHELD for k in ft})
        return r
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
