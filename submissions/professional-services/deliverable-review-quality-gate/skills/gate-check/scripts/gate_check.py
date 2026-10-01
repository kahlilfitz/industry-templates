#!/usr/bin/env python3
"""gate_check - deterministic quality-gate compliance engine."""
import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import assertion_rules as rules  # noqa: E402  byte-identical copy of skills/assertion-map/scripts/assertion_rules.py

ENGINE = "engine:gate_check"
ENGINE_VERSION = "1.0.4"
CONTRACT_VERSION = "ps.deliverable-review-quality-gate.v1"
RELIANCE_RESTRICTION_REQUIRED_FOR_THIRD_PARTY = True  # quality-gate-criteria.md #2.2
DISCLAIMER_TYPES = {"general_advice", "reliance_restriction"}  # quality-gate-criteria.md #2.4: anything else holds
CONFIDENTIALITY_MARK_REQUIRED = True  # quality-gate-criteria.md #4.1
CLIENT_DATA_CLEAN_VALUE = "ok"  # quality-gate-criteria.md #4.3: the only clean client_data_handling value
LEGAL_MARK_DEFECT_BLOCKS = True  # quality-gate-criteria.md #5.2
BRAND_CHECK_STATUSES = {"pass", "fail"}  # quality-gate-criteria.md #5.3: anything else is "not verified" and holds
LICENSED_ATTRIBUTION_REQUIRED = True  # quality-gate-criteria.md #6.1
LICENSE_STATUS_KNOWN = "known"  # quality-gate-criteria.md #6.3: closed enum known/unknown; anything else is unknown
PRIOR_FIX_MUST_LAND = True  # quality-gate-criteria.md #7.1-#7.2
EMBEDDED_INSTRUCTION_HOLD = True  # quality-gate-criteria.md #8.1-#8.3
MAX_G8_HITS = 5
RELEASE_BLOCKER = "release_blocker"  # severity-rules.md #1.1
MUST_FIX = "must_fix"  # severity-rules.md #1.2
ADVISORY = "advisory"  # severity-rules.md #1.3
SEVERITY_RANK = {ADVISORY: 1, MUST_FIX: 2, RELEASE_BLOCKER: 3}
VALID_SEVERITIES = set(SEVERITY_RANK)
# quality-gate-criteria.md #8.4: finding-ID prefixes and source tags only the engines may emit.
ENGINE_OWNED_PREFIXES = {"GC-": ENGINE, "AM-": rules.AM_ENGINE}
GATES = {"G1": "Evidence support and substantiation", "G2": "Required disclaimer, limitation and reliance language", "G3": "Scope-of-work alignment", "G4": "Confidentiality marking and client-data handling", "G5": "Brand and formatting standards", "G6": "Third-party and licensed content attribution", "G7": "Prior-findings closure", "G8": "Data-as-data and embedded-instruction handling"}
# Recipient classification (quality-gate-criteria.md #2.5): client-only requires a positive client-name match.
EXTERNAL_RECIPIENT_PATTERN = re.compile(r"\b(?:" + "|".join((
    r"counsel", r"lawyers?", r"solicitors?", r"attorneys?", r"law firms?", r"lenders?", r"lending", r"banks?", r"bankers?",
    r"financiers?", r"creditors?", r"bondholders?", r"noteholders?", r"investors?", r"shareholders?", r"private equity",
    r"regulators?", r"regulatory", r"auditors?", r"external audit", r"buyers?", r"bidders?", r"acquirers?", r"purchasers?",
    r"vendors?", r"suppliers?", r"insurers?", r"underwriters?", r"rating agenc(?:y|ies)", r"trustees?", r"brokers?",
    r"arrangers?", r"counterpart(?:y|ies)", r"consultants?", r"advisers?", r"advisors?", r"outside", r"external",
    r"third party", r"third parties", r"independent", r"public", r"press", r"media", r"government",
)) + r")\b")
CLIENT_ROLE_PHRASES = ("general counsel", "in house counsel", "in house legal", "internal audit", "audit committee")
CLIENT_ROLE_WORDS = {
    "s", "the", "of", "and", "&", "for", "management", "manager", "managers", "board", "directors", "director",
    "executive", "executives", "leadership", "committee", "steering", "sponsor", "sponsors", "team", "teams", "office",
    "pmo", "programme", "program", "project", "cfo", "ceo", "coo", "cio", "cto", "cro", "chro", "chief", "officer",
    "officers", "finance", "operations", "procurement", "hr", "people", "it", "technology", "digital", "strategy", "legal",
    "risk", "compliance", "head", "heads", "function", "department", "division", "unit", "owner", "owners", "staff",
    "members", "chair", "president", "vp", "vice", "senior", "group",
}
INTERNAL_RECIPIENTS = {"engagement team", "engagement partner", "engagement manager", "reviewing partner", "engagement quality reviewer", "qrm"}
AMBIGUOUS_RECIPIENT_TERMS = ("tbd", "to be confirmed", "external parties", "third parties", "stakeholders", "interested parties", "advisors", "advisers", "allowed users", "distribution list")
# Untrusted sections scanned verbatim. Every other section (assertion_mappings, findings, escalations,
# provenance) is derived from them and is scanned only for text that is not a copy of a primary field.
PRIMARY_SECTIONS = ("deliverable", "criteria", "assertions", "evidence_set", "prior_findings")
UNSCANNED_KEYS = {"contract_version"}  # validated against CONTRACT_VERSION before any scan
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.:#/ -]{1,80}$")

# Letters that render like Latin letters (quality-gate-criteria.md #8.2): Cyrillic, Greek, Armenian, Cherokee, Lisu
# and Latin small capitals / IPA forms. Applied after Unicode Cf stripping and NFKC folding (which already folds
# fullwidth and mathematical alphanumerics) so look-alike spellings of steering text still match. Upper/lower case
# partners are added automatically because normalize_text folds case between two translate passes.
_CONFUSABLE_BASE = {
    # Cyrillic
    "А": "A", "В": "B", "Е": "E", "І": "I", "Ј": "J", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "Х": "X", "У": "Y", "Ѕ": "S", "Ԁ": "D", "Ԛ": "Q", "Ԝ": "W",
    "а": "a", "в": "b", "е": "e", "і": "i", "ј": "j", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p",
    "с": "c", "т": "t", "х": "x", "у": "y", "ѕ": "s", "ԁ": "d", "һ": "h", "ӏ": "l", "ԛ": "q", "ԝ": "w",
    # Greek
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "Ϲ": "C",
    "α": "a", "β": "b", "ε": "e", "η": "n", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t",
    "υ": "u", "χ": "x", "ω": "w", "ϲ": "c", "ϳ": "j",
    # Armenian
    "Օ": "O", "օ": "o", "Ս": "U", "ս": "u", "ո": "n", "հ": "h", "ց": "g", "զ": "q", "ա": "w", "Լ": "L",
    "Տ": "S", "ı": "i",
    # Cherokee (capitals; small forms are added below through str.lower)
    "Ꭰ": "D", "Ꭱ": "R", "Ꭲ": "T", "Ꭵ": "I", "Ꭹ": "Y", "Ꭺ": "A", "Ꭻ": "J", "Ꭼ": "E", "Ꮃ": "W", "Ꮇ": "M",
    "Ꮋ": "H", "Ꮍ": "Y", "Ꮐ": "G", "Ꮒ": "H", "Ꮓ": "Z", "Ꮏ": "B", "Ꮢ": "R", "Ꮤ": "W", "Ꮥ": "S", "Ꮩ": "V",
    "Ꮪ": "S", "Ꮮ": "L", "Ꮯ": "C", "Ꮲ": "P", "Ꮶ": "K", "Ᏼ": "B",
    # Lisu
    "ꓮ": "A", "ꓐ": "B", "ꓚ": "C", "ꓓ": "D", "ꓰ": "E", "ꓝ": "F", "ꓖ": "G", "ꓧ": "H", "ꓲ": "I", "ꓙ": "J",
    "ꓗ": "K", "ꓡ": "L", "ꓟ": "M", "ꓠ": "N", "ꓳ": "O", "ꓑ": "P", "ꓣ": "R", "ꓢ": "S", "ꓔ": "T", "ꓴ": "U",
    "ꓦ": "V", "ꓪ": "W", "ꓫ": "X", "ꓬ": "Y", "ꓜ": "Z",
    # Latin small capitals and IPA look-alikes (Latin script, so only folding catches them)
    "ᴀ": "a", "ʙ": "b", "ᴄ": "c", "ᴅ": "d", "ᴇ": "e", "ꜰ": "f", "ɢ": "g", "ʜ": "h", "ɪ": "i", "ᴊ": "j",
    "ᴋ": "k", "ʟ": "l", "ᴍ": "m", "ɴ": "n", "ᴏ": "o", "ᴘ": "p", "ʀ": "r", "ꜱ": "s", "ᴛ": "t", "ᴜ": "u",
    "ᴠ": "v", "ᴡ": "w", "ʏ": "y", "ᴢ": "z", "ɑ": "a", "ɡ": "g", "ɩ": "i", "ʋ": "u",
}
def _with_case_partners(base):
    table = dict(base)
    for source, target in base.items():
        for variant in (source.lower(), source.upper()):
            if len(variant) == 1 and variant != source and variant not in table and not variant.isascii():
                table[variant] = target.lower() if variant == source.lower() else target.upper()
    return table
CONFUSABLE_MAP = _with_case_partners(_CONFUSABLE_BASE)
CONFUSABLES = str.maketrans(CONFUSABLE_MAP)
CONFUSABLE_CHARS = set(CONFUSABLE_MAP)
# Non-Latin letters routinely used as symbols inside Latin words in consulting prose (ΔEBITDA, 5 μg, σ-level).
# None of them is a Latin look-alike, so they cannot spell steering text; every other non-Latin letter mixed
# with Latin letters in one token is flagged (quality-gate-criteria.md #8.2).
SYMBOL_LETTERS = set("ΔδμσΣπΠΩλθφψγΓµ")

_AI = (r"(?:(?:ai|qrm|quality|human|automated|engagement quality)\s+)?"
       r"(?:ai|assistant|copilot|llm|chatbot|claude|bot|reviewers?|review agent)")
_DOC = r"(?:deliverable|draft|report|document|section|packet|memo|deck|finding|findings|assertion|assertions|claim|claims)"
_OBJ_DOC = r"(?:this|these|that|those|the)\s+(?:[\w'-]+\s+){0,2}?" + _DOC + r"\b"
_OBJ_SELF = r"(?:this|these)\s+(?:[\w'-]+\s+){0,2}?" + _DOC + r"\b"
_OBJ_ANY = r"(?:" + _OBJ_DOC + r"|(?:this|these|that|it|them)\b)"
_END = r"\s*(?:[.;:,!?)]|-|$)"
_OBJ_STRICT = r"(?:" + _OBJ_DOC + r"|(?:this|these|that|it|them)(?=" + _END + r"))"
_CLAUSE = r"(?:^|[.;:!?,(\"'-]\s*|\bplease\s+|\bkindly\s+|\bjust\s+)"
_AUTHORITY = r"(?:(?:engagement|reviewing|signing|lead)\s+)?(?:partner|qrm(?: team| reviewer)?|quality reviewer|risk and quality|risk team)"
_APPROVED = r"(?:pre-?approved|pre-?cleared|approved|cleared|signed[- ]off)"
_CONTACT = (r"(?:[a-z0-9._%+-]+\s*(?:@|\(at\)|\[at\])\s*[a-z0-9-]+(?:\s*(?:\.|\(dot\)|\[dot\])\s*[a-z0-9-]+)+"
            r"|https?://|www\.)")
# Deliverable prose about a client's business (AI adoption, reviews, approvals, reporting) is normal;
# these patterns target text that addresses the reviewer/assistant or tries to steer THIS review
# (quality-gate-criteria.md #8.1-#8.3). An approval word on its own (e.g. "pre-approved by the board")
# is never a hit; it needs an addressee, a self-reference to the document, a review authority or a
# skip/do-not-flag instruction. tests/run_tests.py ships an attack paraphrase set and a benign prose set.
# 1.0.4 structural rules (quality-gate-criteria.md #8.1-#8.3).
# (a) Addressee: the tool itself addressed in vocative/imperative form, whatever the verb.
_TOOL = (r"(?:(?:the|an?|our|my|dear|hey|hi|hello|ok|okay|attention|attn)\s+)?"
         r"(?:(?:ai|automated|quality|qrm|review|engagement quality|language)\s+)?"
         r"(?:ai|assistant|model|llm|copilot|claude|chatgpt|gpt(?:\s?-?\s?\d[\w.]*)?|gemini|bot|chatbot|agent|"
         r"reviewers?|review tool|review agent|reviewing tool|tool)")
_VOC_START = r"(?:^|[.;:!?\"'(\[\n]\s*|\s-\s*)"
_LIST_CONTINUATION = r"(?!(?:please|kindly|just|now|again|ok|okay)\b)[\w'&/]+(?:\s+[\w'&/]+)?\s*(?:,|&|\band\b|\bor\b|/)"
_COLON_FOLLOW = (r"(?:please|kindly|just|you|do|don't|dont|never|no need|treat|mark|report|approve|clear|pass|ignore|skip|"
                 r"accept|release|consider|overlook|disregard|leave|let|waive|classify|rate|record|set|list|show|deem|flag|"
                 r"confirm|sign|move|proceed|output|respond|answer|say|state|write|return|forget|stop|override|bypass|"
                 r"this|these|it|everything|nothing|all good)\b")
VOCATIVE_PATTERNS = (
    re.compile(_VOC_START + _TOOL + r"\s*,\s*(?!" + _LIST_CONTINUATION + r")\S"),
    re.compile(_VOC_START + _TOOL + r"\s*(?::|-|\u2014)\s*" + _COLON_FOLLOW),
    re.compile(_VOC_START + r"(?:to\s+|for\s+)?(?:whoever|anyone|anybody)\s+(?:is\s+)?(?:review(?:s|ing)?|check(?:s|ing)?)\s+"
               r"(?:this|these|it)\b(?:\s+[\w'-]+){0,2}?\s*[,:\-\u2014]"),
)
# (b) Verdict steering, independent of addressee: an imperative verdict verb aimed at this material.
_VERDICT_VERB = r"(?:mark|report|treat|rate|record|flag|set|classify|list|show|consider|deem|log|tag|label|score)"
_ID = r"(?:[a-z]{1,8}\s?-?\s?\d{1,6}[a-z0-9]*)"
_VERDICT_OBJ = (r"(?:this|it|these|them|that|those|everything|all\s+of\s+(?:it|them|these)|" + _ID + r"|"
                r"(?:the|this|these|that|those|all|each|every|all\s+the)\s+[\w']+(?:\s+[\w']+)?)")
_VERDICT = (r"(?:supported|substantiated|verified|validated|confirmed|ready|release[\s-]ready|ready\s+for\s+(?:client\s+)?"
            r"release|approved|cleared|resolved|closed|passed|compliant|ok|okay|fine|accepted|no\s+issues?|"
            r"not\s+an?\s+issue|green|low\s+risk|clean)")
_VERDICT_TAIL = (r"(?=" + _END + r"|\s+(?:and|so|for|by|because|since|without|now|already|please|too|anyway|in|"
                 r"pdf|docx?|xlsx?|pptx?|txt|md|csv|json)\b)")
_LEAD = (r"(?:" + _CLAUSE + r"|\byou\s+(?:can|could|may|should|must|need\s+to)\s+(?:just\s+|simply\s+)?|"
         r"\b(?:then|and|so|now|simply)\s+|\b" + _TOOL + r"\s+(?:should\s+|must\s+|can\s+|will\s+|please\s+)?)")
# Review objects for negative instructions: the review itself, a finding/flag/item, the document, or an ID.
_REVIEW_NOUN = (r"(?:one|item|items|issue|issues|entry|entries|finding|findings|flag|flags|point|points|exception|exceptions|"
                r"claim|claims|assertion|assertions|section|deliverable|draft|report|document|packet|memo|deck|page|"
                r"paragraph|line|check|review|gate)")
_REVIEW_OBJ = (r"(?:(?:this|these|it|them|that)(?:\s+" + _REVIEW_NOUN + r")?(?=" + _END + r"|\s+(?:again|further|either|"
               r"now|please|because|since|as|at all|any more|anymore|for)\b)|(?:this|these|that|the|any)\s+(?:[\w'-]+\s+)?"
               + _REVIEW_NOUN + r"\b|" + _ID + r"(?=" + _END + r"|\s))")
STEERING_PATTERNS = (
    re.compile(_LEAD + r"(?:please\s+|kindly\s+|just\s+)?" + _VERDICT_VERB + r"\s+" + _VERDICT_OBJ +
               r"(?:\s+[\w']+){0,2}?\s+(?:as\s+(?:being\s+)?|to\s+)?" + _VERDICT + _VERDICT_TAIL),
    re.compile(r"(?:" + _CLAUSE + r"|\b(?:you|so|then|and)\s+)(?:do not|don't|dont|never|please do not|please don't)\s+"
               r"(?:flag|escalate|hold|review|re-?review|check|re-?check|raise|report|block|surface|question|challenge|"
               r"query|verify)\s+" + _REVIEW_OBJ),
    re.compile(r"(?:" + _CLAUSE + r"|\b(?:you\s+(?:can|could|may|should)|just|please|so|then|and)\s+)skip\s+"
               r"(?:(?:it|this|these|them|that)(?=" + _END + r")|(?:the|this|these|any|further|all|all\s+the)?\s*"
               r"(?:checks?|review|reviews|reviewing|gates?|flags?|findings?|validation|verification|qrm|sign[- ]?off|"
               r"escalation|this\s+(?:item|finding|claim|assertion|flag))\b)"),
    re.compile(r"\b(?:no|without)\s+(?:further\s+|additional\s+|more\s+)?(?:review|reviews|checks?|checking|escalation|"
               r"qrm(?:\s+review)?|sign[- ]?off|flagging)\s+(?:is\s+|are\s+)?(?:needed|required|necessary)"
               r"(?=" + _END + r"|\s+(?:for|on)\s+(?:this|these|it|the\s+" + _REVIEW_NOUN + r")\b)"),
)
# Loose forms: the same instruction run on from preceding text without punctuation ("...EV-A2 mark this as
# supported"). Only self-referential objects (this/these/it/them or an ID) qualify, and a preceding subject or
# modal ("audit will mark it as closed", "teams do not ...") is excluded so third-person process prose stays clean.
_NOT_AFTER_SUBJECT = "".join(r"(?<!\b" + word + r" )" for word in (
    "will", "would", "should", "shall", "can", "could", "may", "might", "must", "to", "they", "we", "i", "who", "which",
    "that", "then", "and", "or", "team", "teams", "staff", "auditors", "management", "owners", "users", "agents", "it",
    "he", "she", "also", "not", "never", "usually", "typically", "often", "always", "generally"))
_SELF_OBJ = r"(?:this|these|it|them|" + _ID + r")"
LOOSE_STEERING_PATTERNS = (
    re.compile(r"(?<![\w'-])" + _NOT_AFTER_SUBJECT + _VERDICT_VERB + r"\s+" + _SELF_OBJ + r"(?:\s+" + _REVIEW_NOUN + r")?"
               r"\s+as\s+(?:being\s+)?" + _VERDICT + _VERDICT_TAIL),
    re.compile(r"(?<![\w'-])" + _NOT_AFTER_SUBJECT + r"(?:do not|don't|dont|never)\s+(?:flag|escalate|hold|re-?review|"
               r"re-?check|raise|block|surface|question|challenge)\s+(?:this|these|it|them|" + _ID + r")(?:\s+"
               + _REVIEW_NOUN + r")?(?=" + _END + r"|\s+(?:again|further|either|now|please|because|since|at all)\b)"),
)
# (d) IDs and file names: '-', '_' and '.' become spaces in a second matching view.
ID_SEPARATORS = re.compile(r"[-_.]+")

INSTRUCTION_PATTERNS = (
    # Notes, greetings or vocatives addressed to the reviewer/assistant.
    re.compile(r"\b(?:note|message|instruction|reminder|comment)s?\s+(?:to|for)\s+(?:the\s+|any\s+|all\s+)?" + _AI + r"\b"),
    re.compile(r"\b(?:hey|hi|hello|dear|attention|attn)\s+(?:the\s+)?" + _AI + r"\b"),
    re.compile(r"\b" + _AI + r"\s*(?:[:,]|-)\s*(?:please\s+|kindly\s+|just\s+)?(?:treat|mark|approve|clear|pass|ignore|skip|"
               r"accept|release|consider|overlook|disregard|leave|let|waive|wave|do not|don't|dont|no need|nothing to|move on|"
               r"you can|you may)\b"),
    re.compile(r"\b" + _AI + r"\s*(?:[:,]|-)\s*" + _OBJ_ANY + r"\s+(?:is|are)\s+(?:already\s+)?(?:fine|ok|okay|good to go|"
               r"approved|pre-?approved|cleared|signed[- ]off|verified|confirmed)\b"),
    # Permission or instruction given to the reviewer/assistant about this material.
    re.compile(r"\b" + _AI + r"\s+(?:should|must|needs? to|please|can|could|may|will|are free to|is free to)\s+"
               r"(?:safely\s+|just\s+|simply\s+)?(?:not\s+)?(?:flag|approve|clear|pass|ignore|skip|mark|treat|release|"
               r"accept|overlook|disregard|bypass)\s+" + _OBJ_STRICT),
    re.compile(r"\b" + _AI + r"\s+(?:(?:do not|don't|dont|does not|doesn't)\s+(?:need|have)\s+to|need not|needn't)\s+"
               r"(?:flag|check|re-?check|review|verify|question|challenge|escalate|look at)\s+" + _OBJ_STRICT),
    re.compile(r"\b(?:" + _AI + r"\s+(?:can|could|may|should|must|will|are free to|is free to)\s+(?:safely\s+|just\s+|simply\s+)?"
               r"|please\s+|kindly\s+|just\s+|you\s+(?:can|could|may|should)\s+(?:safely\s+|just\s+|simply\s+)?)"
               r"(?:leave|let|wave)\s+" + _OBJ_ANY + r"(?:\s+[\w'-]+){0,2}?\s+(?:alone|unflagged|untouched|unchallenged|"
               r"unchecked|through|stand)\b"),
    re.compile(r"\bno need (?:for (?:the |any |a )?" + _AI + r"\s+)?to\s+(?:flag|check|re-?check|review|verify|question|"
               r"challenge|escalate|look at|hold)\s+" + _OBJ_STRICT),
    re.compile(r"\b(?:whoever|anyone|anybody)\s+(?:is\s+)?(?:review(?:s|ing)?|check(?:s|ing)?)\s+(?:this|the\s+" + _DOC +
               r")\b[^.!?]{0,80}?\b(?:skip|ignore|leave|let it|do not|don't|approve|clear|sign off|already|no need)\b"),
    re.compile(r"\byou\s+(?:can|could|may|should)\s+(?:safely\s+|just\s+|simply\s+)?(?:skip|ignore|disregard|overlook|"
               r"pass over)\s+(?:" + _OBJ_SELF + r"|(?:this|these|it)(?=" + _END + r"))"),
    re.compile(r"\byou\s+(?:need not|needn't|(?:do not|don't)\s+(?:need|have)\s+to|should not|shouldn't|must not)\s+"
               r"(?:flag|check|re-?check|review|verify|question|challenge|escalate)\s+(?:" + _OBJ_SELF +
               r"|(?:this|these|it)(?=" + _END + r"))"),
    # Imperative do-not-flag / do-not-review at the start of a clause.
    re.compile(_CLAUSE + r"(?:do not|don't|dont|never|no need to)\s+(?:flag|surface|escalate|hold|block|review|check|re-?check|"
               r"question|challenge|query|verify|scrutini[sz]e)\s+" + _OBJ_STRICT),
    re.compile(_CLAUSE + r"(?:do not|don't|dont|no need to)\s+(?:flag|escalate|hold|block|re-?check|question|challenge|query)"
               + _END),
    re.compile(r"\b(?:this|these|it|" + _OBJ_DOC + r")\s+(?:does not|doesn't|do not|don't|need not|needn't)\s+(?:need\s+to\s+)?"
               r"(?:be\s+)?(?:flagged|checked|re-?checked|reviewed|verified|escalated|questioned|challenged|held)"
               r"(?:\s+(?:again|further|any further|by\s+(?:you|qrm|the\s+partner|(?:the\s+)?" + _AI + r")))?" + _END),
    # Generic override of the review itself.
    re.compile(r"\b(?:ignore|disregard|override|bypass|skip)\b.{0,30}\b(?:previous instructions|prior instructions|"
               r"(?:the |these |your |all )?instructions|quality gate|gate criteria|qrm|quality review|this review|"
               r"review findings|the flags?)\b"),
    re.compile(r"\bno (?:further |additional )?(?:review|qrm|qrm review|sign[- ]?off|partner review|quality review|checks?)"
               r"(?: is| are)? (?:required|needed|necessary)(?:\s+(?:for|on|of)\s+(?:this|these|the)\s+" + _DOC + r")?" + _END),
    # Approval or authority claims that steer the review (an approval word alone is not enough).
    re.compile(r"(?:\b(?:partner|qrm|reviewers?|note|memo)\b|" + _OBJ_DOC + r")[^.;!?]{0,40}?\b" + _APPROVED +
               r"\s+for\s+(?:client\s+)?(?:release|issue|distribution|sign[- ]?off)\b"),
    re.compile(r"\b" + _APPROVED + r"\s+for\s+(?:client\s+)?(?:release|issue)\b[^.!?]{0,40}?(?:do not|don't|dont|"
               r"no (?:further |additional )?(?:review|qrm|checks?|sign[- ]?off)|skip|ignore|not (?:be )?flag)"),
    re.compile(r"\b(?:the\s+)?" + _AUTHORITY + r"\s+(?:has\s+|have\s+|had\s+)?(?:already\s+(?:pre-?)?|pre-?)(?:confirmed|"
               r"approved|cleared|signed[- ]off(?:\s+on)?|verified|validated|reviewed|checked)\s+" + _OBJ_ANY),
    re.compile(r"\b" + _OBJ_SELF + r"\s+(?:is|are|was|were|(?:has|have|had)\s+been)\s+(?:already\s+|pre-?)(?:approved|"
               r"cleared|signed[- ]off|verified|confirmed|validated|reviewed)\b"),
    re.compile(r"\b" + _OBJ_SELF + r"\s+(?:has|have|had)\s+already\s+been\s+(?:pre-?)?(?:approved|cleared|signed[- ]off|"
               r"verified|confirmed|validated|reviewed)\b"),
    re.compile(r"\b" + _OBJ_DOC + r"\s+(?:is|are|was|were|(?:has|have|had)(?:\s+already)?\s+been)\s+(?:already\s+)?"
               r"(?:approved|cleared|signed[- ]off|verified|confirmed|reviewed)\s+by\s+(?:the\s+)?" + _AUTHORITY + r"\b"),
    re.compile(r"\b(?:waived?|waives|waiving|exempt(?:ed)?|suspended)\b.{0,40}\b(?:disclaimers?|reliance|limitation language|"
               r"quality gate|qrm|gate criteria|quality (?:rules|criteria|review))\b"),
    re.compile(r"\b(?:disclaimer|reliance|qrm|quality|gate)\s+(?:rules?|requirements?|criteria|language|review)?\s*"
               r"(?:are|is|were|was|have been|has been)\s+(?:waived|suspended|not required|not applicable)\b"),
    re.compile(r"\b(?:treat|mark|consider|record|classify)\s+(?:all|every|each|this|these|the)\s+" + _DOC +
               r"\s+(?:as\s+)?(?:supported|verified|substantiated|cleared|approved|resolved|closed|passed|release ready|"
               r"confirmed|accepted)\b"),
    re.compile(r"\b(?:forward|send|e-?mail|share|upload|transmit)\s+(?:this|these|it|a copy|the\s+(?:packet|draft|"
               r"deliverable|report|document|file|review))\b.{0,60}" + _CONTACT),
)


InputError = rules.InputError

def load_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise InputError(f"could not read input JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON input: {exc}") from exc
    except RecursionError as exc:
        raise InputError("input JSON is nested too deeply to process safely") from exc
    return rules.check_depth(payload)

def validate_generated_at(value):
    if value is None:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("--generated-at must be an ISO-8601 timestamp") from exc
    return value

def require_contract(payload):
    if not isinstance(payload, dict):
        raise InputError("input must be a JSON object")
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise InputError(f"expected contract {CONTRACT_VERSION}, got {payload.get('contract_version')!r}")
    if not isinstance(payload.get("deliverable"), dict):
        raise InputError("missing required object: deliverable")
    for key in ("assertions", "assertion_mappings", "findings", "escalations"):
        if key in payload and not isinstance(payload[key], list):
            raise InputError(f"{key} must be an array")
    if "assertion_mappings" not in payload:
        raise InputError("assertion_mappings missing: run skills/assertion-map/scripts/assertion_map.py first; gate_check runs on assertion_map output only")
    if payload.get("criteria") is not None and not isinstance(payload["criteria"], dict):
        raise InputError("criteria must be an object when supplied (absent or null means the criteria register was not loaded)")
    for index, entry in enumerate(payload.get("escalations", [])):
        if not isinstance(entry, (str, dict)):
            raise InputError(f"escalations[{index}] must be a string or object, got {entry!r}")
    rules.validate_assertions(payload.get("assertions"))

def strip_format_characters(value):
    return "".join(ch for ch in unicodedata.normalize("NFKC", str(value)) if unicodedata.category(ch) != "Cf")

def normalize_text(value):
    normalized = strip_format_characters(value).translate(CONFUSABLES).lower().translate(CONFUSABLES)
    for source, target in (("’", "'"), ("‘", "'"), ("‐", "-"), ("‑", "-"), ("–", "-"), ("—", "-")):
        normalized = normalized.replace(source, target)
    return re.sub(r"\s+", " ", normalized).strip()

def letter_script(ch):
    """Script of a letter from its Unicode name ('LATIN', 'CYRILLIC', 'ARMENIAN', ...); None for non-letters."""
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    if name.startswith("MODIFIER LETTER"):
        return None
    return name.split(" ", 1)[0] if name else "UNKNOWN"

def has_confusable_mixed_token(value):
    """True when one token mixes Latin letters with letters of any other script (e.g. 'apprօve' with an Armenian
    'օ', or 'аpproved' with a Cyrillic 'а').

    Digits and punctuation never count. Single-script words (all Cyrillic, all Greek, Turkish 'ı' or other Latin
    letters) are not mixed, and the non-confusable symbol letters in SYMBOL_LETTERS (ΔEBITDA, 5 μg) are allowed.
    Latin small capitals are Latin script; normalize_text folds them instead."""
    for token in re.findall(r"\w+", strip_format_characters(value)):
        scripts = {letter_script(ch) for ch in token if ch not in SYMBOL_LETTERS} - {None}
        if "LATIN" in scripts and len(scripts) > 1:
            return True
    return False

def suspicious_instruction(value):
    if has_confusable_mixed_token(value):
        return True
    text = normalize_text(value)
    views = (text, " ".join(ID_SEPARATORS.sub(" ", text).split()))
    if any(pattern.search(view) for view in views for pattern in VOCATIVE_PATTERNS + STEERING_PATTERNS + LOOSE_STEERING_PATTERNS):
        return True
    return any(pattern.search(text) for pattern in INSTRUCTION_PATTERNS)

def safe_token(value, fallback):
    text = str(value)
    return text if SAFE_TOKEN.match(text) and not suspicious_instruction(text) else fallback

def iter_strings(value, path):
    if isinstance(value, dict):
        for key, child in value.items():
            if key not in UNSCANNED_KEYS:
                yield from iter_strings(child, f"{path}.{safe_token(key, '<field>')}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_strings(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value

def collect_scan_text(payload):
    """Yield (path, text) for every untrusted string, counting a copied value once at its source.

    Primary sections are scanned verbatim, including citation fields. Derived sections are scanned
    after removing any primary text they copy, so an assertion and its assertion_mappings copy raise
    one hit (at the assertion's location) while text introduced only downstream is still caught."""
    primary, derived = [], []
    for key, child in payload.items():
        if key in UNSCANNED_KEYS:
            continue
        target = primary if key in PRIMARY_SECTIONS or not isinstance(child, (dict, list)) else derived
        target.extend(iter_strings(child, f"$.{safe_token(key, '<field>')}"))
    yield from primary
    sources = sorted({text for _, text in primary if len(text.strip()) >= 3}, key=len, reverse=True)
    for path, text in derived:
        residue = text
        for source in sources:
            if source in residue:
                residue = residue.replace(source, " ")
        if residue.strip():
            yield path, residue

MAX_AGGREGATE_CHARS = 4000

def assertion_aggregates(payload):
    """Yield (path, combined text, component texts) per assertion: text, citation, linked evidence titles and the
    location label, joined in reading order and capped at MAX_AGGREGATE_CHARS. This catches steering text split
    across fields (quality-gate-criteria.md #8.1) that no single field contains."""
    evidence = {item["evidence_id"]: item for item in payload.get("evidence_set") or [] if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)}
    for index, assertion in enumerate(payload.get("assertions") or []):
        if not isinstance(assertion, dict):
            continue
        parts = [assertion.get("text"), assertion.get("citation")]
        parts += [evidence.get(evidence_id, {}).get("title") for evidence_id in assertion.get("evidence_ids") or [] if isinstance(evidence_id, str)]
        location = assertion.get("location")
        parts.append(location.get("label") if isinstance(location, dict) else None)
        parts = [part for part in parts if isinstance(part, str) and part.strip()]
        if len(parts) > 1:
            yield f"$.assertions[{index}] (combined text, citation, evidence titles and location label)", " ".join(parts)[:MAX_AGGREGATE_CHARS], parts

def instruction_hits(payload):
    """Every untrusted field that trips the tripwire, then each assertion whose combined fields trip it when none
    of its component fields does on its own (so one note is never counted twice)."""
    hits = [path for path, text in collect_scan_text(payload) if suspicious_instruction(text)]
    for path, combined, parts in assertion_aggregates(payload):
        if suspicious_instruction(combined) and not any(suspicious_instruction(part) for part in parts):
            hits.append(path)
    return hits

def loc(section, page, paragraph, label):
    return {"section": section, "page": page, "paragraph": paragraph, "label": label}

def unplaced(section, label):
    """Register- or field-level location: no page or paragraph applies, so none is invented."""
    return {"section": section, "page": None, "paragraph": None, "label": label}

def add_finding(findings, finding_id, gate_id, severity, title, detail, location, criteria_section, confidence, citation):
    if severity not in VALID_SEVERITIES:
        raise InputError(f"{finding_id}: unknown severity {severity!r}")
    finding = {"finding_id": finding_id, "gate_id": gate_id, "severity": severity, "title": title, "detail": detail, "location": location, "criteria_section": criteria_section, "confidence": confidence, "source": ENGINE, "citation": citation}
    for index, existing in enumerate(findings):
        if existing.get("finding_id") == finding_id:
            # De-duplication may raise severity but never lowers it (quality-gate-criteria.md #8.4).
            if SEVERITY_RANK[severity] > SEVERITY_RANK.get(existing.get("severity"), 0):
                findings[index] = finding
            return
    findings.append(finding)

def validate_upstream_finding(item, index):
    if not isinstance(item, dict):
        raise InputError(f"findings[{index}] must be an object")
    label = f"findings[{index}]"
    rules.require_text(item, "finding_id", label)
    if item.get("severity") not in VALID_SEVERITIES:
        raise InputError(f"{item['finding_id']}: unknown severity {item.get('severity')!r}")
    if item.get("gate_id") not in GATES:
        raise InputError(f"{label} ({item['finding_id']}): gate_id must be one of {', '.join(GATES)}, got {item.get('gate_id')!r}")
    for key in ("title", "detail", "criteria_section", "source", "citation"):
        rules.require_text(item, key, label, required=False, allow_blank=True)
    rules.require_confidence(item, label)
    rules.validate_location(item.get("location"), label, required=False)

def expected_assertion_outputs(payload, evidence_set):
    """Recompute assertion_map output; None when the evidence index was not loaded (nothing to verify against)."""
    if evidence_set is None:
        return None
    evidence_by_id = rules.evidence_index(evidence_set)
    mappings, findings, escalations = [], {}, []
    for assertion in payload["assertions"]:
        mapping, finding, escalation = rules.map_assertion(assertion, evidence_by_id)
        mappings.append(mapping)
        if finding:
            findings[finding["finding_id"]] = finding
            escalations.append(escalation)
    return {"mappings": mappings, "findings": findings, "escalations": escalations}

def screen_upstream_findings(upstream, expected):
    """Keep legitimate upstream findings; drop any engine-owned finding that engine recomputation does not reproduce.

    GC- findings are always recomputed here. An AM- finding is kept only when it is byte-for-byte what assertion_map
    emits for the current assertions and evidence (`expected`); a self-declared source tag proves nothing. Any other
    finding carrying an engine source tag is spoofed. Returns (kept, spoofed IDs) (quality-gate-criteria.md #8.4)."""
    kept, spoofed = [], []
    expected_am = expected["findings"] if expected else None
    for index, item in enumerate(upstream):
        validate_upstream_finding(item, index)
        finding_id = normalize_text(item["finding_id"]).upper()
        source = normalize_text(item.get("source", ""))
        owner = next((tag for prefix, tag in ENGINE_OWNED_PREFIXES.items() if finding_id.startswith(prefix)), None)
        label = safe_token(item["finding_id"], f"findings[{index}]")
        if owner == ENGINE or source == ENGINE:
            spoofed.append(label)
            continue
        if owner == rules.AM_ENGINE:
            if expected_am is None or expected_am.get(item["finding_id"]) != item:
                spoofed.append(label)
            elif not any(kept_item["finding_id"] == item["finding_id"] for kept_item in kept):
                kept.append(item)
            continue
        if source.startswith("engine:"):
            spoofed.append(label)
            continue
        duplicate = next((i for i, kept_item in enumerate(kept) if kept_item["finding_id"] == item["finding_id"]), None)
        if duplicate is None:
            kept.append(item)
        elif SEVERITY_RANK[item["severity"]] > SEVERITY_RANK[kept[duplicate]["severity"]]:
            kept[duplicate] = item
    return kept, spoofed

def reconcile_assertion_outputs(payload, expected, kept, escalations):
    """Restore assertion_map output that was removed or altered upstream. Returns the assertion IDs that differed."""
    if expected is None:
        return []
    provided = {item.get("assertion_id"): item for item in payload["assertion_mappings"] if isinstance(item, dict)}
    altered = [m["assertion_id"] for m in expected["mappings"] if provided.get(m["assertion_id"]) != m]
    if len(payload["assertion_mappings"]) != len(expected["mappings"]) and not altered:
        altered.append("assertion_mappings")
    payload["assertion_mappings"] = expected["mappings"]
    present = {item["finding_id"] for item in kept}
    for finding_id, finding in expected["findings"].items():
        if finding_id not in present:
            kept.append(finding)
            altered.append(finding["finding_id"][len("AM-"):])
    for escalation in expected["escalations"]:
        if escalation not in escalations:
            escalations.append(escalation)
    return [safe_token(item, "assertion") for item in dict.fromkeys(altered)]

def validate_unverified_mappings(mappings):
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            raise InputError(f"assertion_mappings[{index}] must be an object")
        label = f"assertion_mappings[{index}]"
        for key in ("assertion_id", "support_status", "criteria_section"):
            rules.require_text(mapping, key, label)
        if mapping["support_status"] not in {"supported", "limited", "unsupported"}:
            raise InputError(f"{label}.support_status must be supported, limited or unsupported, got {mapping['support_status']!r}")
        for key in ("rationale", "citation"):
            rules.require_text(mapping, key, label, required=False, allow_blank=True)
        rules.require_confidence(mapping, label)
        rules.validate_location(mapping.get("location"), label)

def highest_for_gate(findings, gate_id):
    gated = [item for item in findings if item.get("gate_id") == gate_id]
    return "none" if not gated else max((item["severity"] for item in gated), key=lambda sev: SEVERITY_RANK[sev])

def recipients_of(deliverable):
    recipients = deliverable.get("intended_recipients")
    return recipients if isinstance(recipients, list) else []

def recipient_words(value):
    return " ".join(re.sub(r"[^a-z0-9&]+", " ", normalize_text(value)).split())

def contains_phrase(text, phrase):
    return bool(phrase) and re.search(r"(?:^|\s)" + re.escape(phrase) + r"(?=\s|$)", text) is not None

def strip_role_phrases(text):
    for phrase in CLIENT_ROLE_PHRASES:
        text = re.sub(r"(?:^|\s)" + re.escape(phrase) + r"(?=\s|$)", " ", text)
    return " ".join(text.split())

def has_external_vocabulary(text):
    return EXTERNAL_RECIPIENT_PATTERN.search(strip_role_phrases(text)) is not None

def client_identity_entries(deliverable):
    """Yield (label, raw value, normalised phrase) for client_name and every client_aliases entry."""
    entries = []
    if isinstance(deliverable.get("client_name"), str):
        entries.append(("client_name", deliverable["client_name"], recipient_words(deliverable["client_name"])))
    for index, alias in enumerate(string_list(deliverable, "client_aliases", "deliverable.client_aliases")):
        entries.append((f"client_aliases[{index}]", alias, recipient_words(alias)))
    return [entry for entry in entries if len(entry[2]) >= 3]

def client_identities(deliverable):
    """Client names usable for positive matching. A name or alias containing external-party vocabulary is never
    trusted (quality-gate-criteria.md #2.5): it could otherwise relabel a lender or counsel as the client."""
    return [phrase for _, _, phrase in client_identity_entries(deliverable) if not has_external_vocabulary(phrase)]

def invalid_client_identities(deliverable):
    return [(label, safe_token(value.strip(), label)) for label, value, phrase in client_identity_entries(deliverable) if has_external_vocabulary(phrase)]

def classify_recipient(recipient, identities):
    """Return client, internal, external or unclassified (quality-gate-criteria.md #2.5).

    External-party vocabulary is checked first, on the full recipient text (only the engine's fixed client-role
    phrases such as "general counsel" are exempt); a client name or alias never neutralises it. A recipient is
    client-only only when it positively names a trusted client identity and every remaining word is a client role
    word. Anything else is unclassified; nothing is inferred from the absence of a keyword."""
    text = recipient_words(recipient)
    if text in INTERNAL_RECIPIENTS:
        return "internal"
    if has_external_vocabulary(text):
        return "external"
    matched = False
    for phrase in sorted(identities, key=len, reverse=True):
        if contains_phrase(text, phrase):
            matched = True
            text = re.sub(r"(?:^|\s)" + re.escape(phrase) + r"(?=\s|$)", " ", text)
    text = strip_role_phrases(text)
    if matched and all(word in CLIENT_ROLE_WORDS for word in text.split()):
        return "client"
    return "unclassified"

def recipient_classes(deliverable):
    identities = client_identities(deliverable)
    classes = {"client": [], "internal": [], "external": [], "unclassified": []}
    for index, recipient in enumerate(recipients_of(deliverable)):
        if recipient.strip():
            classes[classify_recipient(recipient, identities)].append(safe_token(recipient.strip(), f"recipient {index + 1}"))
    return classes

def is_third_party_context(deliverable):
    return deliverable.get("third_party_recipient_named") is True or bool(recipient_classes(deliverable)["external"])

def recipient_list_problem(deliverable):
    recipients = deliverable.get("intended_recipients")
    if recipients is None:
        return "recipient list is missing"
    if not recipients:
        return "recipient list is empty"
    if any(not item.strip() for item in recipients):
        return "recipient list contains a blank entry"
    joined = " | ".join(recipients).lower()
    if any(term in joined for term in AMBIGUOUS_RECIPIENT_TERMS):
        return "recipient list is ambiguous"
    return None

def string_list(container, key, label):
    """Optional list of strings: absent or null -> [], wrong type -> InputError."""
    value = container.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise InputError(f"{label} must be an array when present")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise InputError(f"{label}[{index}] must be a string, got {item!r}")
    return value

def validate_deliverable(deliverable):
    """Type-check every deliverable field a gate reads. Wrong JSON types are input errors; enum values are judged by the gates."""
    if deliverable.get("intended_recipients") is not None:
        string_list(deliverable, "intended_recipients", "deliverable.intended_recipients")
    # Required: the declared flag is cross-checked against the classified recipients (quality-gate-criteria.md #2.5).
    rules.require_boolean(deliverable, "third_party_recipient_named", "deliverable")
    for key in ("required_disclaimer_type", "confidentiality_marking", "client_data_handling", "client_name"):
        rules.require_text(deliverable, key, "deliverable", required=False, allow_blank=True)
    for key in ("present_disclaimer_types", "present_language", "client_aliases"):
        string_list(deliverable, key, f"deliverable.{key}")

def require_unique_ids(items, label, id_key):
    seen = set()
    for index, item in enumerate(items):
        if item[id_key] in seen:
            raise InputError(f"{label}[{index}]: duplicate {id_key} {item[id_key]!r}; each register entry must be unique so no entry can mask another")
        seen.add(item[id_key])

def require_entry_basics(item, label, id_key):
    if not isinstance(item, dict):
        raise InputError(f"{label} must be an object")
    rules.require_text(item, id_key, label)
    for key in ("title", "detail", "citation", "source"):
        rules.require_text(item, key, label, required=False, allow_blank=True)
    rules.require_confidence(item, label)
    rules.validate_location(item.get("location"), label, required=False)

def validate_brand_checks(items):
    for index, item in enumerate(items):
        label = f"deliverable.brand_checks[{index}]"
        require_entry_basics(item, label, "check_id")
        rules.require_text(item, "status", label, required=False, allow_blank=True)
        rules.require_boolean(item, "legal_or_release_control", label)
    require_unique_ids(items, "deliverable.brand_checks", "check_id")

def validate_licensed_content(items):
    for index, item in enumerate(items):
        label = f"deliverable.licensed_content[{index}]"
        require_entry_basics(item, label, "content_id")
        rules.require_boolean(item, "attribution_present", label)
        rules.require_text(item, "license_status", label, required=False, allow_blank=True)
    require_unique_ids(items, "deliverable.licensed_content", "content_id")

def validate_prior_findings(items):
    for index, item in enumerate(items):
        label = f"prior_findings[{index}]"
        require_entry_basics(item, label, "finding_id")
        rules.require_boolean(item, "claimed_closed", label)
        rules.require_boolean(item, "document_fix_present", label)
    require_unique_ids(items, "prior_findings", "finding_id")

def entry_location(item, section, label):
    return item.get("location") or unplaced(section, label)

def register(container, key, label):
    """Return the register list, or None when it was not loaded (absent or null). Missing is not empty."""
    if not isinstance(container, dict) or container.get(key) is None:
        return None
    if not isinstance(container[key], list):
        raise InputError(f"{label} must be an array when supplied (absent or null means the register was not loaded)")
    return container[key]

def find_prior_location(payload, *terms):
    priors = payload.get("prior_findings")
    lowered_terms = tuple(term.lower() for term in terms)
    for prior in priors if isinstance(priors, list) else []:
        if not isinstance(prior, dict) or not isinstance(prior.get("location"), dict):
            continue
        location = prior["location"]
        haystack = " ".join(str(value) for value in (prior.get("finding_id", ""), prior.get("detail", ""), prior.get("citation", ""), location.get("section", ""), location.get("label", ""))).lower()
        if all(term in haystack for term in lowered_terms):
            return location
    return None

def disclaimer_location(payload):
    return (
        find_prior_location(payload, "disclaimer")
        or find_prior_location(payload, "reliance")
        or unplaced("Disclaimer", "Disclaimer block (page not supplied in the review input)")
    )

def item_location(items, index):
    if isinstance(items, list) and index < len(items) and isinstance(items[index], dict) and isinstance(items[index].get("location"), dict):
        return items[index]["location"]
    return None

def location_for_scan_path(payload, path):
    deliverable = payload.get("deliverable") or {}
    indexed = (
        (r"^\$\.assertions\[(\d+)\]", payload.get("assertions")),
        (r"^\$\.prior_findings\[(\d+)\]", payload.get("prior_findings")),
        (r"^\$\.assertion_mappings\[(\d+)\]", payload.get("assertion_mappings")),
        (r"^\$\.findings\[(\d+)\]", payload.get("findings")),
        (r"^\$\.deliverable\.brand_checks\[(\d+)\]", deliverable.get("brand_checks")),
        (r"^\$\.deliverable\.licensed_content\[(\d+)\]", deliverable.get("licensed_content")),
    )
    for pattern, items in indexed:
        match = re.match(pattern, path)
        if match:
            found = item_location(items, int(match.group(1)))
            if found:
                return found
            break
    match = re.match(r"^\$\.evidence_set\[(\d+)\]", path)
    if match:
        return unplaced("Evidence index", f"Evidence item {int(match.group(1)) + 1} (evidence_set[{match.group(1)}])")
    if path.startswith("$.deliverable"):
        return disclaimer_location(payload) if "disclaimer" in path or "language" in path else unplaced("Deliverable metadata", "Deliverable field")
    if path.startswith("$.criteria"):
        return unplaced("Criteria register", "Criteria extract field")
    return unplaced("Review input", "Supplied field outside the deliverable body")

def check_missing_registers(payload, deliverable, findings, escalations):
    criteria = payload.get("criteria")
    registers = (
        (criteria, "criteria_sections", "criteria.criteria_sections", "GC-G1-criteria-register-missing", "G1", RELEASE_BLOCKER, "Criteria register is missing", "The applicable criteria list is absent or null, so the gate cannot be treated as having no findings.", "Criteria register", "quality-gate-criteria.md #1-#8; severity-rules.md #1.1", "quality-gate-criteria.md #1-#8; severity-rules.md #1.1"),
        (payload, "evidence_set", "evidence_set", "GC-G1-evidence-index-missing", "G1", RELEASE_BLOCKER, "Evidence index is missing", "The evidence index is absent or null, so assertions cannot be treated as supported.", "Evidence index", "quality-gate-criteria.md #1.1", "quality-gate-criteria.md #1.1; severity-rules.md #1.1"),
        (deliverable, "client_data_handling", None, "GC-G4-client-data-register-missing", "G4", RELEASE_BLOCKER, "Client-data handling register is missing", "Client data handling is absent or null; missing is not the same as a clean data-handling assessment.", "Client-data handling register", "quality-gate-criteria.md #4.2-#4.3", "quality-gate-criteria.md #4.2-#4.3; severity-rules.md #1.1"),
        (deliverable, "brand_checks", "deliverable.brand_checks", "GC-G5-brand-register-missing", "G5", MUST_FIX, "Brand-check register is missing", "Brand and release-control checks are absent or null; missing is not the same as no brand findings.", "Brand-check register", "quality-gate-criteria.md #5.1-#5.2", "quality-gate-criteria.md #5.1-#5.2; severity-rules.md #1.2"),
        (deliverable, "licensed_content", "deliverable.licensed_content", "GC-G6-licensed-content-register-missing", "G6", MUST_FIX, "Licensed-content register is missing", "Licensed and third-party content checks are absent or null; missing is not the same as no licensed-content findings.", "Licensed-content register", "quality-gate-criteria.md #6.1-#6.2", "quality-gate-criteria.md #6.1-#6.2; severity-rules.md #1.2"),
        (payload, "prior_findings", "prior_findings", "GC-G7-prior-findings-register-missing", "G7", MUST_FIX, "Prior-findings register is missing", "Prior-review closure cannot be verified when the prior-findings register is absent or null.", "Prior findings register", "quality-gate-criteria.md #7.1-#7.2", "quality-gate-criteria.md #7.1-#7.2; severity-rules.md #1.2"),
        (deliverable, "required_language", "deliverable.required_language", "GC-G2-required-language-register-missing", "G2", RELEASE_BLOCKER, "Required-language register is missing", "The required-language list is absent or null; missing is not the same as explicitly empty.", "Required-language register", "quality-gate-criteria.md #2.1-#2.3", "quality-gate-criteria.md #2.1-#2.3; severity-rules.md #1.1"),
    )
    loaded = {}
    for container, key, label, finding_id, gate_id, severity, title, detail, section, criteria_section, citation in registers:
        value = container.get(key) if isinstance(container, dict) else None
        if value is None:
            add_finding(findings, finding_id, gate_id, severity, title, detail, unplaced(section, "Register not supplied (absent or null)"), criteria_section, 0.99, citation)
            escalations.append(f"{gate_id}: {section.lower()} not supplied (absent or null) - {severity}; hold for reviewing partner/QRM, missing is not empty ({criteria_section})")
        elif label:
            loaded[key] = register(container, key, label)
    return loaded

def check_client_data_value(deliverable, findings, escalations):
    value = deliverable.get("client_data_handling")
    if value is None or value == CLIENT_DATA_CLEAN_VALUE:
        return
    if value == "attention":
        severity, title, detail = MUST_FIX, "Client-data handling needs attention", "The client-data register records `attention`; only `ok` is clean, so the extract must be corrected or confirmed before release."
    elif value == "breach":
        severity, title, detail = RELEASE_BLOCKER, "Client-data handling breach recorded", "The client-data register records `breach`."
    elif value == "unknown":
        severity, title, detail = RELEASE_BLOCKER, "Client-data handling cannot be confirmed", "The client-data register records `unknown`; safe handling cannot be confirmed."
    else:
        severity, title, detail = RELEASE_BLOCKER, "Client-data handling value is not recognised", "client_data_handling is blank or not one of ok, attention, breach or unknown; an unrecognised value is never treated as clean."
    add_finding(findings, "GC-G4-client-data", "G4", severity, title, detail, unplaced("Client-data handling register", "client_data_handling"), "quality-gate-criteria.md #4.2-#4.3", 0.95, "quality-gate-criteria.md #4.2-#4.3")
    shown = value if value in {"attention", "breach", "unknown"} else "blank/unrecognised"
    escalations.append(f"G4: client_data_handling is {shown}, not ok - {severity}; hold for reviewing partner/QRM (quality-gate-criteria.md #4.2-#4.3)")

def main():
    parser = argparse.ArgumentParser(description="Apply quality-gate compliance checks deterministically.")
    parser.add_argument("--mapped", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    try:
        generated_at = validate_generated_at(args.generated_at)
        payload = load_json(args.mapped)
        require_contract(payload)
        deliverable = payload["deliverable"]
        validate_deliverable(deliverable)
        expected = expected_assertion_outputs(payload, payload.get("evidence_set"))
        if expected is None:
            validate_unverified_mappings(payload["assertion_mappings"])
        escalations = list(payload.get("escalations", []))
        findings, spoofed = screen_upstream_findings(payload.get("findings", []), expected)
        altered = reconcile_assertion_outputs(payload, expected, findings, escalations)
        if spoofed or altered:
            parts = []
            if spoofed:
                parts.append(f"{len(spoofed)} upstream finding(s) used an engine-owned finding ID or engine source tag without matching engine recomputation and were ignored")
            if altered:
                parts.append(f"assertion_map output for {len(altered)} assertion(s) was missing or did not match recomputation and was restored")
            add_finding(findings, "GC-G8-engine-id-spoof", "G8", RELEASE_BLOCKER, "Upstream engine output is spoofed or altered", "; ".join(parts) + ". Engine findings are recomputed and cannot be replaced, removed or downgraded by input data.", unplaced("Upstream findings", "findings[] / assertion_mappings supplied with the review input"), "quality-gate-criteria.md #8.1; quality-gate-criteria.md #8.4", 0.99, "quality-gate-criteria.md #8.1, #8.4; severity-rules.md #1.1")
            if spoofed:
                escalations.append(f"G8: upstream finding(s) {', '.join(spoofed)} reused engine-owned IDs or source tags without matching engine recomputation and were ignored - hold for reviewing partner/QRM (quality-gate-criteria.md #8.4)")
            if altered:
                escalations.append(f"G8: assertion_map output for {', '.join(altered)} was missing or altered upstream and was restored from recomputation - hold for reviewing partner/QRM (quality-gate-criteria.md #8.4)")
        loaded = check_missing_registers(payload, deliverable, findings, escalations)
        brand_checks = loaded.get("brand_checks") or []
        licensed_content = loaded.get("licensed_content") or []
        prior_findings = loaded.get("prior_findings") or []
        required_language = loaded.get("required_language") or []
        for index, section in enumerate(loaded.get("criteria_sections") or []):
            if not isinstance(section, str) or not section.strip():
                raise InputError(f"criteria.criteria_sections[{index}] must be a non-blank string, got {section!r}")
        for index, item in enumerate(required_language):
            if not isinstance(item, str):
                raise InputError(f"deliverable.required_language[{index}] must be a string, got {item!r}")
        validate_brand_checks(brand_checks)
        validate_licensed_content(licensed_content)
        validate_prior_findings(prior_findings)
        recipient_problem = recipient_list_problem(deliverable)
        if recipient_problem:
            add_finding(findings, "GC-G2-recipient-ambiguity", "G2", RELEASE_BLOCKER, "Recipient list is missing or ambiguous", f"{recipient_problem}; reliance language cannot be confirmed until the allowed recipient set is explicit.", disclaimer_location(payload), "quality-gate-criteria.md #2.2", 0.98, "quality-gate-criteria.md #2.2; severity-rules.md #1.1")
            escalations.append(f"G2: {recipient_problem} - release blocker; reviewing partner/QRM must confirm the allowed recipients (quality-gate-criteria.md #2.2)")
        recipients = recipient_classes(deliverable)
        invalid_identities = invalid_client_identities(deliverable)
        if invalid_identities:
            names = ", ".join(f"{label}={value}" for label, value in invalid_identities)
            add_finding(findings, "GC-G2-client-identity-external", "G2", MUST_FIX, "Client name or alias contains external-party vocabulary", f"{names} contains external-party vocabulary (counsel, lender, bank, investor, regulator, auditor, buyer, outside or third party), so it is not trusted to identify the client; recipients naming it are treated as external.", disclaimer_location(payload), "quality-gate-criteria.md #2.5", 0.9, "quality-gate-criteria.md #2.5; severity-rules.md #1.2")
            escalations.append(f"G2: confirm client aliases {names} - contains external-party vocabulary and is not trusted as the client identity; reviewing partner/QRM must confirm the client name, aliases and recipients (quality-gate-criteria.md #2.5)")
        if recipients["external"] and deliverable["third_party_recipient_named"] is False:
            names = ", ".join(recipients["external"])
            add_finding(findings, "GC-G2-recipient-third-party-conflict", "G2", RELEASE_BLOCKER, "External recipient conflicts with third_party_recipient_named=false", f"Recipient(s) {names} match external-party vocabulary (counsel, lender, investor, regulator, auditor, buyer, outside or third party) but third_party_recipient_named is false; the deliverable is treated as third-party and reliance-restriction language is required.", disclaimer_location(payload), "quality-gate-criteria.md #2.2; quality-gate-criteria.md #2.5", 0.97, "quality-gate-criteria.md #2.2, #2.5; severity-rules.md #1.1")
            escalations.append(f"G2: recipient(s) {names} look external but third_party_recipient_named is false - release blocker; reviewing partner/QRM must confirm the recipients and reliance terms (quality-gate-criteria.md #2.5)")
        if recipients["unclassified"] and not recipient_problem:
            names = ", ".join(recipients["unclassified"])
            reason = "no trusted deliverable.client_name or client_aliases entry is supplied, so no recipient can be positively matched to the client" if not client_identities(deliverable) else "they do not positively match the client named in deliverable.client_name/client_aliases or a defined internal role"
            add_finding(findings, "GC-G2-recipient-unconfirmed", "G2", MUST_FIX, "Recipients not confirmed as client-only", f"Recipient(s) {names} are unclassified: {reason}. An unmatched recipient is never assumed to be client-only.", disclaimer_location(payload), "quality-gate-criteria.md #2.5", 0.9, "quality-gate-criteria.md #2.5; severity-rules.md #1.2")
            escalations.append(f"G2: confirm recipients {names} - not positively matched to the client; must-fix until the reviewing partner/QRM confirms they are client-only (quality-gate-criteria.md #2.5)")
        present_disclaimers = string_list(deliverable, "present_disclaimer_types", "deliverable.present_disclaimer_types")
        disclaimer_type = deliverable.get("required_disclaimer_type")
        third_party = is_third_party_context(deliverable)
        if disclaimer_type not in DISCLAIMER_TYPES:
            add_finding(findings, "GC-G2-disclaimer-type-unrecognised", "G2", RELEASE_BLOCKER, "Required disclaimer type is not determined", "required_disclaimer_type is absent, blank or not one of general_advice or reliance_restriction, so the required disclaimer cannot be confirmed; an unrecognised value is never treated as clean.", disclaimer_location(payload), "quality-gate-criteria.md #2.1-#2.2; quality-gate-criteria.md #2.4", 0.97, "quality-gate-criteria.md #2.1-#2.2, #2.4; severity-rules.md #1.1")
            escalations.append("G2: required_disclaimer_type is absent, blank or unrecognised - release blocker; reviewing partner/QRM must confirm the required disclaimer (quality-gate-criteria.md #2.4)")
        if third_party and RELIANCE_RESTRICTION_REQUIRED_FOR_THIRD_PARTY and disclaimer_type in DISCLAIMER_TYPES and disclaimer_type != "reliance_restriction":
            add_finding(findings, "GC-G2-required-disclaimer-wrong", "G2", RELEASE_BLOCKER, "Required disclaimer type is wrong for third-party context", "A third-party recipient or allowed user requires reliance-restriction language.", disclaimer_location(payload), "quality-gate-criteria.md #2.2", 0.98, "quality-gate-criteria.md #2.2; severity-rules.md #1.1")
        if (disclaimer_type == "reliance_restriction" or (third_party and RELIANCE_RESTRICTION_REQUIRED_FOR_THIRD_PARTY)) and "reliance_restriction" not in present_disclaimers:
            if third_party:
                add_finding(findings, "GC-G2-reliance-language", "G2", RELEASE_BLOCKER, "Wrong disclaimer for third-party recipient", "A third-party recipient or allowed user is named but reliance-restriction language is absent; a general-advice disclaimer does not satisfy this gate.", disclaimer_location(payload), "quality-gate-criteria.md #2.2", 0.98, "quality-gate-criteria.md #2.2; severity-rules.md #1.1")
                escalations.append("G2: third-party recipient context and reliance-restriction language absent - release blocker (quality-gate-criteria.md #2.2)")
            else:
                add_finding(findings, "GC-G2-reliance-language", "G2", RELEASE_BLOCKER, "Required reliance-restriction disclaimer is absent", "required_disclaimer_type is reliance_restriction but reliance-restriction language is not in present_disclaimer_types.", disclaimer_location(payload), "quality-gate-criteria.md #2.2; quality-gate-criteria.md #2.4", 0.97, "quality-gate-criteria.md #2.2, #2.4; severity-rules.md #1.1")
                escalations.append("G2: required reliance-restriction disclaimer absent from the deliverable - release blocker (quality-gate-criteria.md #2.4)")
        if disclaimer_type == "general_advice" and "general_advice" not in present_disclaimers:
            add_finding(findings, "GC-G2-general-advice-absent", "G2", MUST_FIX, "Required general-advice disclaimer is absent", "required_disclaimer_type is general_advice but general-advice language is not in present_disclaimer_types; a declared disclaimer requirement is only met when the disclaimer is present.", disclaimer_location(payload), "quality-gate-criteria.md #2.1; quality-gate-criteria.md #2.4", 0.95, "quality-gate-criteria.md #2.1, #2.4; severity-rules.md #1.2")
            escalations.append("G2: required general-advice disclaimer absent from the deliverable - must-fix; reviewing partner/QRM must confirm the disclaimer before release (quality-gate-criteria.md #2.4)")
        present_language = string_list(deliverable, "present_language", "deliverable.present_language")
        for required in required_language:
            if required not in present_language:
                severity = RELEASE_BLOCKER if required == "reliance_restriction" else MUST_FIX
                add_finding(findings, f"GC-G2-missing-{safe_token(required, 'language')}", "G2", severity, f"Missing required language: {safe_token(required, 'required language item')}", f"Required language `{safe_token(required, 'required language item')}` is not present in the deliverable.", disclaimer_location(payload), "quality-gate-criteria.md #2.1-#2.3", 0.94, "quality-gate-criteria.md #2.1-#2.3")
        if CONFIDENTIALITY_MARK_REQUIRED and deliverable.get("confidentiality_marking") != "client confidential":
            add_finding(findings, "GC-G4-confidentiality", "G4", RELEASE_BLOCKER, "Missing client-confidential marking", "Required client-confidential marking is absent from cover/footer.", loc("Cover", 1, 1, "Confidentiality mark"), "quality-gate-criteria.md #4.1", 0.97, "quality-gate-criteria.md #4.1; severity-rules.md #1.1")
        check_client_data_value(deliverable, findings, escalations)
        for index, check in enumerate(brand_checks):
            check_id = safe_token(check["check_id"], f"brand-check-{index + 1}")
            location = entry_location(check, "Brand-check register", f"Brand check {check_id}")
            legal = check["legal_or_release_control"] and LEGAL_MARK_DEFECT_BLOCKS
            status_value = check.get("status")
            if status_value == "fail":
                add_finding(findings, f"GC-G5-{check_id}", "G5", MUST_FIX if legal else ADVISORY, check.get("title", "Brand or formatting defect"), check.get("detail", "Brand check failed"), location, "quality-gate-criteria.md #5.1-#5.2", check.get("confidence", 0.9), check.get("citation", "quality-gate-criteria.md #5.1-#5.2"))
            elif status_value not in BRAND_CHECK_STATUSES:
                severity = RELEASE_BLOCKER if legal else MUST_FIX
                add_finding(findings, f"GC-G5-{check_id}", "G5", severity, "Brand or release-control check not verified", f"Brand check {check_id} has status {safe_token(status_value, 'blank/unrecognised') if status_value else 'blank/missing'}; only pass or fail are recognised, so the check is treated as not verified{' for a legal, confidentiality or release-control mark' if legal else ''}.", location, "quality-gate-criteria.md #5.2-#5.3", 0.95, "quality-gate-criteria.md #5.2-#5.3")
                escalations.append(f"G5: brand check {check_id} status is not pass or fail - {severity}; hold for reviewing partner/QRM (quality-gate-criteria.md #5.3)")
        for index, item in enumerate(licensed_content):
            content_id = safe_token(item["content_id"], f"licensed-content-{index + 1}")
            license_known = item.get("license_status") == LICENSE_STATUS_KNOWN
            if LICENSED_ATTRIBUTION_REQUIRED and item["attribution_present"] is not True:
                severity = MUST_FIX if license_known else RELEASE_BLOCKER
                add_finding(findings, f"GC-G6-{content_id}", "G6", severity, "Licensed content lacks attribution", item.get("detail", "Third-party content requires attribution."), entry_location(item, "Licensed-content register", f"Licensed content {content_id}"), "quality-gate-criteria.md #6.1-#6.2", item.get("confidence", 0.93), item.get("citation", "quality-gate-criteria.md #6.1-#6.2"))
                if not license_known:
                    escalations.append(f"G6: unattributed licensed content {content_id} with license_status not known (unknown, blank or unrecognised) - release blocker; hold for reviewing partner/QRM (quality-gate-criteria.md #6.2-#6.3)")
        for index, prior in enumerate(prior_findings):
            if prior["claimed_closed"] is True and prior["document_fix_present"] is not True and PRIOR_FIX_MUST_LAND:
                prior_id = safe_token(prior["finding_id"], f"prior-finding-{index + 1}")
                add_finding(findings, f"GC-G7-{prior_id}", "G7", MUST_FIX, "Prior finding marked closed but fix is absent", prior.get("detail", "Tracker closure is not supported by the current document."), entry_location(prior, "Prior findings register", f"Prior finding {prior_id}"), "quality-gate-criteria.md #7.1-#7.2", prior.get("confidence", 0.96), prior.get("citation", "quality-gate-criteria.md #7.1-#7.2"))
        for index, assertion in enumerate(payload["assertions"]):
            if assertion["scope_aligned"] is not True:
                assertion_id = safe_token(assertion["assertion_id"], f"assertion-{index + 1}")
                add_finding(findings, f"GC-G3-scope-{assertion_id}", "G3", RELEASE_BLOCKER, "Claim or recommendation falls outside signed scope", "Assertion is marked scope_aligned=false; claims and recommendations must stay inside the signed statement of work and documented evidence set.", assertion["location"], "quality-gate-criteria.md #3.1", assertion.get("confidence", 0.9), f"{assertion['citation']}; quality-gate-criteria.md #3.1; severity-rules.md #1.1")
        verified_am = {item["finding_id"] for item in findings if item["finding_id"].startswith("AM-")}
        for mapping in payload["assertion_mappings"]:
            if mapping["support_status"] in {"unsupported", "limited"} and "#3.2" in mapping["criteria_section"]:
                # Only an AM finding that matched engine recomputation may stand in for the G3 limitation finding.
                if f"AM-{mapping['assertion_id']}" in verified_am:
                    continue
                add_finding(findings, f"GC-G3-{safe_token(mapping['assertion_id'], 'assertion')}", "G3", MUST_FIX, "Scope or sample limitation missing at point of recommendation", mapping.get("rationale", "Recommendation requires limitation."), mapping["location"], "quality-gate-criteria.md #3.2", mapping.get("confidence", 0.8), mapping.get("citation", "quality-gate-criteria.md #3.2"))
        if EMBEDDED_INSTRUCTION_HOLD:
            hits = instruction_hits(payload)
            for hit_index, path in enumerate(hits[:MAX_G8_HITS], start=1):
                add_finding(findings, f"GC-G8-embedded-instruction-{hit_index}", "G8", RELEASE_BLOCKER, "Embedded instruction or forwarding request found in deliverable data", f"Untrusted field {path} contains instruction-like, forwarding or look-alike-character text; it must be treated as data and held for human review.", location_for_scan_path(payload, path), "quality-gate-criteria.md #8.1-#8.3", 0.99, "quality-gate-criteria.md #8.1-#8.3; severity-rules.md #1.1")
                escalations.append(f"G8: embedded-instruction tripwire in {path} - hold for reviewing partner/QRM (quality-gate-criteria.md #8.1-#8.3)")
            if len(hits) > MAX_G8_HITS:
                escalations.append(f"G8: {len(hits) - MAX_G8_HITS} further embedded-instruction hit(s) not listed individually - hold for reviewing partner/QRM (quality-gate-criteria.md #8.1-#8.3)")
        gate_results = []
        for gate_id, name in GATES.items():
            highest = highest_for_gate(findings, gate_id)
            status = "no_engine_findings" if highest == "none" else "blocked" if highest == RELEASE_BLOCKER else "attention_required"
            gate_results.append({"gate_id": gate_id, "name": name, "status": status, "highest_severity": highest, "finding_count": sum(1 for item in findings if item.get("gate_id") == gate_id), "confidence": 0.95, "source": ENGINE, "citation": f"quality-gate-criteria.md #{gate_id[1]}"})
        payload["findings"], payload["gate_results"], payload["escalations"] = findings, gate_results, escalations
        provenance = payload.setdefault("provenance", {})
        if not isinstance(provenance, dict):
            raise InputError("provenance must be an object when present")
        if generated_at:
            provenance["generated_at"] = generated_at
        provenance.setdefault("engines", []).append(f"gate_check/{ENGINE_VERSION}")
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        blockers = sum(1 for item in findings if item["severity"] == RELEASE_BLOCKER)
        must_fix = sum(1 for item in findings if item["severity"] == MUST_FIX)
        advisory = sum(1 for item in findings if item["severity"] == ADVISORY)
        print(f"gate_check: {len(gate_results)} gate(s), blockers={blockers}, must_fix={must_fix}, advisory={advisory} -> {os.path.basename(args.out)}")
        return 0
    except InputError as exc:
        print(f"gate_check input error: {exc}", file=sys.stderr)
        return 1
    except RecursionError:
        print("gate_check input error: input is nested too deeply to process safely", file=sys.stderr)
        return 1
    except (KeyError, TypeError, AttributeError, ValueError, IndexError) as exc:
        print(f"gate_check input error: malformed input ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
