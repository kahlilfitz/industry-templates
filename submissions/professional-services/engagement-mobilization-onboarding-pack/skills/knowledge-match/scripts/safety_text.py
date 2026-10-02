import csv, functools, hashlib, json, math, os, re, tempfile, unicodedata
import contract_validate as _cv
from datetime import datetime
CONTRACT_VERSION = "ps.engagement-mobilization-onboarding-pack.v1"
VERSION = "1.0.1"
class InputError(Exception): pass

# ---------------------------------------------------------------- I/O
def require_iso_z(v):
    try: datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError) as e: raise InputError("--generated-at must be ISO-8601 UTC like 2026-10-01T00:00:00Z") from e
    return v
def _no_constant(c): raise InputError(f"non-finite number {c} is not valid JSON; fail closed")
def _finite_float(s):
    v = float(s)
    if not math.isfinite(v): raise InputError(f"number {s[:24]} overflows to a non-finite value; fail closed")
    return v
def load_json(p):
    """NaN, Infinity, -Infinity and overflowing literals (1e999) are rejected at parse time, never passed on (#1.3)."""
    try:
        with open(p, encoding="utf-8-sig") as f: return json.load(f, parse_constant=_no_constant, parse_float=_finite_float)  # a BOM never hides the first key (#1.3)
    except InputError as e: raise InputError(f"{e} ({p})") from e
    except FileNotFoundError as e: raise InputError(f"missing required JSON file: {p}") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e: raise InputError(f"malformed JSON in {p} (must be UTF-8 JSON): {e}") from e
    except OSError as e: raise InputError(f"cannot read JSON file {p}: {type(e).__name__}") from e
_UMASK = os.umask(0o022); os.umask(_UMASK)
def _encode(text, p):
    try: return text.encode("utf-8")
    except UnicodeEncodeError as e: raise InputError(f"output {os.path.basename(p)} contains text that is not valid Unicode (e.g. a lone surrogate from an input); nothing written; fail closed") from e
def json_bytes(p, o):
    try: t = json.dumps(o, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    except ValueError as e: raise InputError(f"output {os.path.basename(p)} contains a non-finite number; nothing written; fail closed") from e
    return _encode(t, p)
def text_bytes(p, t): return _encode(t if t.endswith("\n") else t + "\n", p)
def write_atomic(items):
    """Write [(path, bytes)] outputs serialised in full beforehand: each goes to a temp file in its own folder and all
    are moved into place with os.replace only after every temp file is written, so on any error no output path is
    created or truncated and no temp file is left behind (#1.3)."""
    tmps = []
    try:
        for p, b in items:
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(p)), prefix="." + os.path.basename(p) + ".", suffix=".tmp"); tmps.append(tmp)
            with os.fdopen(fd, "wb") as f: f.write(b)
            os.chmod(tmp, 0o666 & ~_UMASK)
        for (p, _), tmp in zip(items, tmps): os.replace(tmp, p)
    except OSError as e: raise InputError(f"cannot write output ({type(e).__name__}); nothing written; fail closed") from e
    finally:
        for tmp in tmps:
            if os.path.exists(tmp): os.remove(tmp)
def dump_json(p, o): write_atomic([(p, json_bytes(p, o))])
def read_text(p):
    try:
        with open(p, encoding="utf-8-sig") as f: return f.read()  # a BOM never hides the first "Engagement ID:" (#1.3)
    except FileNotFoundError as e: raise InputError(f"missing required file: {p}") from e
    except UnicodeDecodeError as e: raise InputError(f"file is not UTF-8 text: {p} ({e.reason} at byte {e.start})") from e
    except OSError as e: raise InputError(f"cannot read file {p}: {type(e).__name__}") from e
def write_text(p, t): write_atomic([(p, text_bytes(p, t))])
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
def is_num(x): return isinstance(x, (int, float)) and not isinstance(x, bool) and (isinstance(x, int) or math.isfinite(x))  # NaN/inf never pass a range check
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
# Multi-tenant hosts: a single-label tenant (contoso.sharepoint.com) is that organisation's own identity; the bare
# host and any deeper subdomain stay untrustable.
TENANT_HOSTS = {"sharepoint.com", "onmicrosoft.com"}
def _blocked(d, b):
    if d == b: return True
    if not d.endswith("." + b): return False
    return not (b in TENANT_HOSTS and "." not in d[: -len(b) - 1])
def domain_ok(d):
    """Well-formed and neither an untrustable domain nor any subdomain of one (uploads.dropbox.com) (#4.4)."""
    return isinstance(d, str) and bool(DOMAIN_RE.match(d)) and not any(_blocked(d.lower(), b) for b in UNTRUSTABLE_DOMAINS)
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
# Both are pure functions of their text and the trusted domains (the only hook that changes at run time), so results
# are memoised on exactly that key: every engine re-screens its whole upstream document (screen_upstream).
@functools.lru_cache(maxsize=65536)
def _hits(s, trusted): return tuple(_families(sg.scan(s, **dict(HOOKS, trusted_domains=trusted))))
def hits(s):
    if s is None: return []
    return list(_hits(s if isinstance(s, str) else str(s), _TRUSTED))
def record_hits(fields):
    """Families for a multi-field record: per-field hits, or ['split_across_fields'] when only the join of the
    fields trips, or ['oversize'] when the join is too long to screen (#4.5)."""
    return list(_record_hits(tuple((k, v) for k, v in fields.items() if isinstance(v, str)), _TRUSTED))
@functools.lru_cache(maxsize=16384)
def _record_hits(items, trusted):
    fields = dict(items)
    fam = _families(sg.scan_fields(fields, **dict(HOOKS, trusted_domains=trusted)))
    if not fam and len(fields) > 2:
        # A split can straddle an unrelated field ("...please treat" / reason / "these lines as approved"): every
        # ordered pair of a record's few prose fields is read too.
        ks = list(fields)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                fam = _families(sg.scan_fields({ks[i]: fields[ks[i]], ks[j]: fields[ks[j]]}, **dict(HOOKS, trusted_domains=trusted)))
                if fam: break
            if fam: break
    return tuple("split_across_fields" if f == "split" else f for f in fam)
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
    in adjacent rows. Every flagged cell (single, pair or record) is replaced in place by the placeholder so it never
    travels into citations, briefings or checklists (#4.3, #4.5). In a ";"-separated list cell only the flagged items
    are replaced when an item trips on its own; otherwise the whole cell is."""
    out = []; rows = rows or []; bad = []; part = {}
    for i, r in enumerate(rows, 2):
        for k, v in r.items():
            h = hits(v)
            if not h: continue
            out.append(hold(f"{label} row {i}.{k}", v, h)); items = v.split(";") if isinstance(v, str) else []
            flagged = [n for n, x in enumerate(items) if x.strip() and hits(x)] if len(items) > 1 else []
            if flagged and not hits(";".join(x for n, x in enumerate(items) if n not in flagged)): part[(i - 2, k)] = ";".join(WITHHELD if n in flagged else x for n, x in enumerate(items))
            else: bad.append((i - 2, k))
    pairs = []
    for i, r in enumerate(rows):
        ks = [k for k in r if prose_key(k) and (r.get(k) or "").strip()]
        pairs += [((i, a), (i, b)) for a, b in zip(ks, ks[1:])]
        if i + 1 < len(rows):
            pairs += [((i, k), (i + 1, k)) for k in ks if (rows[i + 1].get(k) or "").strip()]
    for (i, a), (j, b) in pairs:
        h = pair_hits(rows[i][a], rows[j][b])
        if h:
            where = f"{label} row {i + 2}.{a}+{b}" if i == j else f"{label} rows {i + 2}-{j + 2}.{a}"
            out.append(hold(where, rows[i][a] + "\n" + rows[j][b], h)); bad += [(i, a), (j, b)]
    # A row is one record: when only the join of all its cells trips, every cell is withheld and the row held (#4.5).
    hit_rows = {i for i, _ in bad} | {i for i, _ in part}
    for i, r in enumerate(rows):
        if i in hit_rows: continue
        ft = free_text(r); h = record_hits(ft) if len(ft) > 1 else []
        if h:
            out.append(hold(f"{label} row {i + 2} (fields joined)", "\n".join(ft.values()), h))
            bad += [(i, k) for k in ft]
    for (i, k), v in part.items(): rows[i][k] = v
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
        if not isinstance(nm, str) or not nm.strip() or nm in (WITHHELD, OTHER_WITHHELD): continue
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
    return {"hold_id": "HOLD-OTHER-CLIENT-" + hashlib.sha256(strip_cf(text).encode()).hexdigest()[:12], "path": path, "reason": OTHER_HOLD_REASON, "source": engine, "confidence": 0.97, "citation": "confidentiality-and-ethical-wall-rules.md #3.3"}
# Engine-generated hold text is recognised only by matching the known engine templates below, never by a hold's
# self-declared source: a forged "source": "engine:wall_check" exempts nothing. Templates admit no free text (only
# hex digests, counts, family names and permission enums); text that interpolates supplied values (column names,
# status values, roles) is screened like any other string. Paths are always screened (#3.3, #4.3).
ENGINE_SOURCES = {"engine:safety_text", "engine:scope_digest", "engine:knowledge_match", "engine:wall_check", "engine:access_checklist"}
ENGINE_HOLD_ID_RE = re.compile(r"HOLD-(?:(?:OTHER-CLIENT|BRIEFING-TOPIC|SCREENED)-)?[0-9a-f]{12}|HOLD-(?:DOMAIN-NOT-TRUSTED|STAFFING-ENGAGEMENT-MISMATCH|UNKNOWN-ONBOARDING-STATUS|UNRECOGNISED-STAFFING-VERDICT|INVALID-WORKSPACE-ROW|MALFORMED-WORKSPACE-INVENTORY|MISSING-WORKSPACE-INVENTORY|PERMISSION-CLAMPED|ROLE-NOT-IN-MATRIX|UNKNOWN-WALL-DECISION|MALFORMED-WALL-REGISTER|MISSING-WALL-REGISTER|NO-JOINER|UNKNOWN-WALL-STATUS)")
OTHER_HOLD_REASON = "text names another client or matter (name not repeated); withheld from every output"
ENGINE_REASONS = {OVERSIZE_REASON, OTHER_HOLD_REASON,
    "briefing topic names another client, matter or identifying detail; withheld from the pack",
    "blank, null or unrecognised Scenario 02 verdict for a confirmed roster member",
    "blank or unrecognised onboarding_status; joiner status cannot be determined",
    "staffing input names a different client or engagement than the SOW (name not repeated); staffing evidence not trusted",
    "unrecognised wall_decision status; treated as hold", "missing workspace inventory; no access is requested",
    "no joiner identified; wall status cannot be determined", "missing ethical-wall register",
    "ethical-wall register row(s) carry more fields than the header",
    "no wall register row clears this joiner for this client or matter"}
_PERM = r"(?:none|viewer|member|contributor|admin|owner)"
ENGINE_REASON_RES = [re.compile(r"embedded_instruction:[a-z_]+(?:,[a-z_]+)*"),
    re.compile(r"\d+ declared client/firm domain\(s\) are malformed or consumer/file-sharing domains and are not trusted \(not repeated\)"),
    re.compile(rf"requested {_PERM} is wider than min\(workspace default {_PERM}, role ceiling {_PERM}\); request clamped to {_PERM}")]
_REF = r"(?:confidentiality-and-ethical-wall-rules|knowledge-reuse-rules|role-access-matrix|workspace-inventory-rules)\.md(?: #\d+(?:\.\d+)*(?:-#?\d+(?:\.\d+)*)?(?:, ?#?\d+(?:\.\d+)*(?:-#?\d+(?:\.\d+)*)?)*)?"
ENGINE_CITATION_RE = re.compile(rf"{_REF}(?:; {_REF})*")
def engine_text(k, v):
    """True only for a hold field that matches a known engine template exactly."""
    if not isinstance(v, str): return False
    if k == "hold_id": return bool(ENGINE_HOLD_ID_RE.fullmatch(v))
    if k == "source": return v in ENGINE_SOURCES
    if k == "reason": return v in ENGINE_REASONS or any(r.fullmatch(v) for r in ENGINE_REASON_RES)
    if k == "citation": return bool(ENGINE_CITATION_RE.fullmatch(v))
    return False
def _screen_value(v, path, k, terms, engine, new):
    if isinstance(v, dict): return {kk: _screen_value(x, f"{path}.{kk}", kk, terms, engine, new) for kk, x in v.items()}
    if isinstance(v, list): return [_screen_value(x, f"{path}[{i}]", k, terms, engine, new) for i, x in enumerate(v)]
    if not isinstance(v, str) or v in (WITHHELD, OTHER_WITHHELD) or engine_text(k, v): return v
    d = hashlib.sha256(strip_cf(v).encode()).hexdigest()[:12]
    if names_client(v, terms): new.append(other_hold(path, v, engine)); return "HOLD-SCREENED-" + d if k == "hold_id" else OTHER_WITHHELD
    f = hits(v)
    if f: new.append(hold(path, v, f)); return "HOLD-SCREENED-" + d if k == "hold_id" else WITHHELD
    return v
def screen_holds(holds, terms, engine, prefix="holds"):
    """Screen holds supplied by an upstream document (never this engine's own): every string at any depth (id, path,
    reason, citation, source and any other field) that names another client or carries steering text is replaced,
    never echoed, and itself held; a split across a hold's prose fields is held too. Text matching a known engine
    template (engine_text) is kept intact. Returns (screened holds, new holds) (#3.3, #4.3)."""
    out, new = [], []
    for n, h in enumerate(holds or []):
        if not isinstance(h, dict): out.append(_screen_value(h, f"{prefix}[{n}]", "", terms, engine, new)); continue
        before = len(new); h = {k: _screen_value(v, f"{prefix}[{n}].{k}", k, terms, engine, new) for k, v in h.items()}
        ft = {k: v for k, v in free_text(h).items() if not engine_text(k, v)}
        if len(new) == before and len(ft) > 1:
            f = record_hits(ft)
            if f: new.append(hold(f"{prefix}[{n}] (fields joined)", json.dumps(ft, sort_keys=True, ensure_ascii=False), f)); h.update({k: WITHHELD for k in ft})
        out.append(h)
    return out, new
def screen_upstream(doc, label, engine, terms=()):
    """Every string an engine receives in an upstream JSON document is screened before anything is derived from it:
    the body through scan() and redact() (every string at any depth, including run_metadata and provenance), the
    supplied holds through screen_holds(). Flagged values are replaced by the placeholder and held at their path.
    Returns (screened document, new holds); any new hold forces the caller's hold / on-hold status (#4.1, #4.3)."""
    if not isinstance(doc, dict): return doc, []
    hk = isinstance(doc.get("holds"), list)
    body = {k: v for k, v in doc.items() if not (hk and k == "holds")}
    new = scan(body, label); red = redact(body)
    up, uh = screen_holds(doc["holds"], terms, engine, f"{label}.holds") if hk else ([], [])
    return {k: (up if hk and k == "holds" else red[k]) for k in doc}, new + uh
def upstream_escalation(n): return f"{n} upstream field(s) held for embedded instruction review (confidentiality-and-ethical-wall-rules.md #4.1-#4.5)"
def other_escalation(n): return f"{n} field(s) withheld because they name another client or matter; Risk/Conflicts review before the pack is shared (confidentiality-and-ethical-wall-rules.md #3.3)"

# ---------------------------------------------------------------- contract validation of pipeline documents
# Every engine validates every intermediate document it reads, and the one it writes, against the stage schema in the
# shipped contract (required fields, nested types, list element types, closed enums, ranges, provenance engine
# prefixes) through the shared stdlib walker contract_validate.py. A violation is a clean InputError, never a coercion
# or a hold, and no output is written (confidentiality-and-ethical-wall-rules.md #1.3).
def check_contract(doc, where, stage=None):
    try: _cv.validate(doc, where, stage)
    except _cv.ContractViolation as e: raise InputError(str(e)) from None

# ---------------------------------------------------------------- cumulative holds (#1.4)
# Hold- and decision-bearing state is never taken from an intermediate file. Whatever an engine cannot re-derive from
# the raw sources it holds is reconciled: a document that still carries evidence of an earlier hold (a placeholder,
# an engine escalation, a held status) but not the matching hold has been edited, and is refused.
_ESC_SAFETY = re.compile(r"\d+ (?:source|upstream) field\(s\) held for embedded instruction review \(confidentiality-and-ethical-wall-rules\.md #4\.1-#4\.5\)")
_ESC_OTHER = re.compile(r"\d+ field\(s\) withheld because they name another client or matter; .*")
_ESC_TOPIC = re.compile(r"\d+ wall briefing topic\(s\) withheld from the pack; .*")
_ESC_ID = [(re.compile(r"Confirmed roster row .+ has a blank or unrecognised Scenario 02 verdict; .*"), "HOLD-UNRECOGNISED-STAFFING-VERDICT"),
    (re.compile(r"Roster row \d+ has a blank or unrecognised onboarding_status; .*"), "HOLD-UNKNOWN-ONBOARDING-STATUS"),
    (re.compile(r"A declared client/firm domain is malformed or a consumer/file-sharing domain; .*"), "HOLD-DOMAIN-NOT-TRUSTED"),
    (re.compile(r"Staffing input is for a different client or engagement than the SOW; .*"), "HOLD-STAFFING-ENGAGEMENT-MISMATCH")]
def _strings(v):
    if isinstance(v, dict):
        for x in v.values(): yield from _strings(x)
    elif isinstance(v, list):
        for x in v: yield from _strings(x)
    elif isinstance(v, str): yield v
def check_hold_evidence(doc, where):
    holds = [h for h in doc.get("holds") or [] if isinstance(h, dict)]
    ids = [str(h.get("hold_id") or "") for h in holds]; reasons = [str(h.get("reason") or "") for h in holds]
    safety = any(r == OVERSIZE_REASON or r.startswith("embedded_instruction:") for r in reasons) or any(i.startswith("HOLD-SCREENED-") for i in ids)
    other = any(i.startswith("HOLD-OTHER-CLIENT-") for i in ids)
    body = list(_strings({k: v for k, v in doc.items() if k != "holds"}))
    esc = [e for e in doc.get("escalations") or [] if isinstance(e, str)]
    kd = doc.get("knowledge_digest") if isinstance(doc.get("knowledge_digest"), dict) else {}
    wd = doc.get("wall_decision") if isinstance(doc.get("wall_decision"), dict) else {}
    people = [doc.get("joiner") or {}] + [r for r in doc.get("team_roster") or [] if isinstance(r, dict)]
    checks = [(any(WITHHELD in x for x in body), safety, "text withheld for embedded-instruction review"),
        (any(OTHER_WITHHELD in x for x in body), other, "text withheld because it names another client or matter"),
        (any(TOPIC_WITHHELD in x for x in body), any(i.startswith("HOLD-BRIEFING-TOPIC-") for i in ids) or safety, "wall briefing topic withheld"),
        (any(_ESC_SAFETY.fullmatch(e) for e in esc), safety or other, "embedded-instruction escalation"),
        (any(_ESC_OTHER.fullmatch(e) for e in esc), other, "other-client escalation"),
        (any(_ESC_TOPIC.fullmatch(e) for e in esc), any(i.startswith("HOLD-BRIEFING-TOPIC-") for i in ids) or safety, "briefing-topic escalation"),
        (bool(wd.get("name_withheld_workspace_ids")), safety or other, "workspace name withheld"),
        (kd.get("status") == "hold", bool(holds), "knowledge_digest.status hold"),
        (wd.get("status") == "hold", bool(holds), "wall_decision.status hold"),
        (any(isinstance(x.get("staffing_review"), dict) and x["staffing_review"].get("verdict") == "unrecognised" for x in people if isinstance(x, dict)), "HOLD-UNRECOGNISED-STAFFING-VERDICT" in ids, "unrecognised staffing verdict")]
    checks += [(any(r.fullmatch(e) for e in esc), hid in ids, hid.lower()) for r, hid in _ESC_ID]
    missing = [what for ev, ok, what in checks if ev and not ok]
    need(not missing, f"{where} carries evidence of an earlier hold ({'; '.join(missing)}) but the matching hold is missing; intermediate state is inconsistent - re-run the chain from the raw sources; fail closed (confidentiality-and-ethical-wall-rules.md #1.4)")
def knowledge_ids(items): return [x.get("knowledge_id") if isinstance(x, dict) else None for x in items or []]
def check_digest(doc, where, wall_status=None):
    """The digest is gating state: re-derive its status from the holds, the items and the wall status and refuse a
    document whose supplied digest disagrees (knowledge-reuse-rules.md #3.1; confidentiality-and-ethical-wall-rules.md #1.4, #2.3)."""
    kd = doc["knowledge_digest"]; items = knowledge_ids(kd.get("items")); cands = knowledge_ids(doc.get("prior_knowledge_candidates"))
    if wall_status is None: exp, exp_items = ("hold" if doc.get("holds") else "ready" if cands else "empty"), cands  # as knowledge_match writes it
    elif wall_status == "denied": exp, exp_items = "denied_by_wall", []
    elif wall_status == "hold": exp, exp_items = "hold", []
    else:
        need(not doc.get("holds"), f"{where}.wall_decision is clear while holds are open; wall_check never clears with open holds; fail closed (confidentiality-and-ethical-wall-rules.md #1.4, #4.1)")
        exp, exp_items = ("ready" if cands else "empty"), cands
    need(kd.get("status") == exp and items == exp_items, f"{where}.knowledge_digest (status {kd.get('status')!r}, {len(items)} item(s)) does not match the state re-derived from its holds, candidates and wall decision (expected {exp!r}, {len(exp_items)} item(s)); fail closed (confidentiality-and-ethical-wall-rules.md #1.4)")

# ---------------------------------------------------------------- other-client identities from the wall register
# Every engine screens upstream text for other clients with the same identities wall_check uses: other register rows'
# client_name / matter_id and proper-noun runs in restriction free text (#3.2, #3.3).
ALLOW_CAPS = {"sharepoint", "teams", "planner", "sow", "gdpr", "pci", "pii", "hipaa", "api", "it", "risk", "conflicts", "knowledge", "repository", "channel", "engagement", "delivery", "client", "q1", "q2", "q3", "q4", "i"}
TOPIC_WITHHELD = "[briefing topic withheld - it names another client or matter, Risk/Conflicts brief the joiner directly]"  # #3.2
def cap_runs(text):
    for m in re.finditer(r"[A-Z][A-Za-z0-9&'.-]*(?:\s+(?:&\s+)?[A-Z][A-Za-z0-9&'.-]*)*", text or ""):
        start = m.start() == 0 or bool(re.search(r"[.;:!?]\s*$", text[:m.start()])); yield m.group(0).strip(" .'-"), start
def key_low(v): return (v or "").strip().lower()
def other_names(rows, e, own):
    """Every other client's identity in the register: other rows' client_name/matter_id and proper-noun runs in
    restriction free text (confidentiality-and-ethical-wall-rules.md #3.2,#3.3). Withheld cells name nobody."""
    names = []
    for r in rows:
        if r.get("client_name") and key_low(r.get("client_name")) != key_low(e.get("client_name")): names.append(r["client_name"].strip())
        if r.get("matter_id") and key_low(r.get("matter_id")) != key_low(e.get("matter_id")): names.append(r["matter_id"].strip())
        rest = r.get("restriction") or ""
        if rest in (WITHHELD, OTHER_WITHHELD): continue
        for run, start in cap_runs(rest):
            ws = words(run)
            if not ws or ws <= own | GENERIC | ALLOW_CAPS or (start and len(run.split()) == 1): continue
            names.append(run)
    return names
def own_words(doc):
    e = doc.get("engagement") or {}; j = doc.get("joiner") or {}
    return words(e.get("client_name"), e.get("matter_id"), e.get("engagement_id"), e.get("title"), *(e.get("affiliates") or []), j.get("person"), *[r.get("person") for r in doc.get("team_roster", []) if isinstance(r, dict)], *(doc.get("scope_summary") or {}).get("systems", []))
REGISTER_COLUMNS = ("person", "client_name", "matter_id", "status")  # confidentiality-and-ethical-wall-rules.md #2.1
def register_terms(path, e, own):
    """Other-client terms from the wall register at path, read and screened exactly as wall_check reads it; an absent
    or malformed register yields none (wall_check then holds the pack)."""
    rows = read_csv(path, False)
    if rows is None or missing_columns(rows, REGISTER_COLUMNS): return []
    scan_rows(rows, "raw/ethical-wall-register.csv")
    return client_terms(other_names(rows, e, own), own)

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
