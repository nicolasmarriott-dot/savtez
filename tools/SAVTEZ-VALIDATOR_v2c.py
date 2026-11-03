#!/usr/bin/env python3
"""SAVTEZ-VALIDATOR v2c (task SAVTEZ-2c, AXIS FIX, Rule 1). PROPOSAL pending Nick's yes. Deterministic decoder/validator.
Reject, never guess. = SAVTEZ-VALIDATOR_v2b.py (kept, unchanged) + the SAVTEZ-2c axis split (PROPOSED):
  P (derivation)    = quoted pzx U+E202 | calculated by us tfy U+E201 | inferred by us wxg U+E205 (moved from E) | assumed, not checked xjc U+E204
  C (corroboration) = single-origin dxz U+F200 | independently corroborated cwj U+F201   (NEW block F2xx; see below)
  E (evidence)      = verified against a primary source zbh U+E100 | refuted (checked, found false) hxy U+E104 (NEW form)
                      | inconclusive (checked, undetermined) yhz U+E103 (redefined from "unknown") | unchecked, lead only xrj U+E101
  Slot order H T E P C A R + HEAD. C has the same head compatibility as P (claim, figure, source, statement).
  RETIRED code points (never reused, rejected loudly): U+E102 (v2b E inferred), U+E200 / U+E203 (v2b P single-origin /
  corroborated; now C U+F200 / U+F201).
  C block F2xx: BMP PUA is E000-F8FF; E000-E7FF = 8 axis blocks (HEAD E P T A R H ACT), E8xx = sigil, E900-F104 = check symbols
  (E900 + 0..2052), so F200-F2FF is the first whole hundred-block that is free; its offsets mod 2053 (502, 503) differ from
  every other part's, so the PUA check still separates every part (asserted at import).

FORMS
  new (default)  r3 word = SIGIL + [H][T][E][P][A][R] + HEAD + CHECK, parts = GENERATED 3-char ASCII forms
                 (PROPOSED by SAVTEZ-2, Nick decides). ASCII: SIGIL '^', check char over alphabet A17.
                 Canonical: SIGIL U+E800, one PUA symbol per part, CHECK symbol U+E900+v.
  --legacy       v0.3 placeholder CVC parts, bare words, no sigil/check (old-form gate).
USAGE
  SAVTEZ-VALIDATOR_v2.py WORD              validate one word (ASCII or PUA canonical form)
  SAVTEZ-VALIDATOR_v2.py -m 'MESSAGE'      validate a message (real newlines); -f FILE reads a file
  SAVTEZ-VALIDATOR_v2.py --encode savpevkef   frame a legacy spelling into the new form (+check), print both forms
  SAVTEZ-VALIDATOR_v2.py --hash -f FILE    8-hex body hash;  --table  code point table
  SAVTEZ-VALIDATOR_v2.py --gate [--gate-out F] [--quick]   gate + edge cases + Rule 0 typo gate
OUTPUT  'VALID | <input> | <English decode> | canonical ...'  or  'REJECT | <input> | <rule> (spec N) | required reply ...'
EXIT    0 VALID, 1 REJECT, 2 usage error or gate failure
"""
import sys, re, hashlib, argparse, itertools, random

VERSIONS = {"0.3", "0.3-draft"}
ORDER = ["H", "T", "E", "P", "C", "A", "R"]   # SAVTEZ-2c: C after P
AXNAME = {"H": "handling", "T": "task state", "E": "evidence", "P": "derivation", "C": "corroboration", "A": "absence",
          "R": "relation", "HEAD": "head", "ACT": "message act"}
ALPHA = "bcdfghjkmprstwxyz"          # A17: lowercase, no two symbols confusable (see SAVTEZ-GENERATED-FORMS)
P_ASCII, G_ASCII = 17, 3             # check over Z_17, weight base 3 (primitive root mod 17)
SIGIL, SIGIL_PUA = "^", "\ue800"
P_PUA = 2053                         # smallest prime > 2048 (= code-point offsets E000-E7FF)
CHECK_PUA_BASE = 0xE900              # check symbols U+E900 .. U+E900+2052 (= U+F104)
C_BLOCK = 0xF200                     # SAVTEZ-2c: C (corroboration) block U+F200-U+F2FF, above the check range
# concept table: code point -> (axis, meaning, legacy CVC form or None, new GENERATED form)
CONCEPTS = [
 (0xE000, "HEAD", "claim", "kef", "wfz"), (0xE001, "HEAD", "source", "duv", "jgx"),
 (0xE002, "HEAD", "log entry", "vop", "xwf"), (0xE003, "HEAD", "task", "gaz", "ykc"),
 (0xE004, "HEAD", "figure", "fub", "rzg"), (0xE005, "HEAD", "statement made", "tez", "zxb"),
 (0xE006, "HEAD", "act done", "rux", "gyw"), (0xE007, "HEAD", "relation", "zim", "fhy"),
 (0xE008, "HEAD", "gap or contradiction", "xem", "yjt"),
 (0xE100, "E", "verified against a primary source", "sav", "zbh"), (0xE101, "E", "unchecked, lead only", "lod", "xrj"),
 (0xE103, "E", "inconclusive (checked, undetermined)", None, "yhz"),   # SAVTEZ-2c: redefined from "unknown" (v2b)
 (0xE104, "E", "refuted (checked, found false)", None, "hxy"),         # SAVTEZ-2c NEW form
 (0xE201, "P", "calculated by us", "fid", "tfy"),
 (0xE202, "P", "quoted verbatim from a source", None, "pzx"),
 (0xE204, "P", "assumed, not checked", None, "xjc"),   # SAVTEZ-2b PROPOSED
 (0xE205, "P", "inferred by us", None, "wxg"),         # SAVTEZ-2c: moved from E (v2b U+E102)
 (0xF200, "C", "single-origin, no independent corroboration", "pev", "dxz"),   # SAVTEZ-2c: was P U+E200
 (0xF201, "C", "independently corroborated", None, "cwj"),                    # SAVTEZ-2c: was P U+E203
 (0xE300, "T", "queued", None, "rxm"), (0xE301, "T", "active", None, "xbk"),
 (0xE302, "T", "waiting on Nick's word", "bix", "wty"), (0xE303, "T", "on hold", "hiw", "dyf"),
 (0xE304, "T", "blocked", "zut", "hjz"), (0xE305, "T", "done", None, "zdx"),
 (0xE306, "T", "failed", None, "jzb"), (0xE307, "T", "canceled", None, "yfh"),
 (0xE400, "A", "searched the named source, nothing found", "zof", "xmw"),
 (0xE401, "A", "record that should exist is absent", "gom", "zcj"),
 (0xE500, "R", "associated, causation not claimed", "wap", "xhs"), (0xE501, "R", "causal, established", "kyr", "jxr"),
 (0xE600, "H", "internal, not for outside release", "vun", "fkx"), (0xE601, "H", "append-only, never edited", "tib", "rcy"),
 (0xE700, "ACT", "inform", None, "yzd"), (0xE701, "ACT", "request", None, "wgj"), (0xE702, "ACT", "confirm", None, "txw"),
 (0xE703, "ACT", "disconfirm", None, "xyp"), (0xE704, "ACT", "refuse", None, "zjg"), (0xE705, "ACT", "propose", None, "rhx"),
 (0xE706, "ACT", "failure", None, "jyz"), (0xE707, "ACT", "not-understood", None, "zsy"),
]
RETIRED = {0xE102: "v2b E 'inferred by us' (wxg); now P U+E205",
           0xE200: "v2b P 'single-origin' (dxz); now C U+F200",
           0xE203: "v2b P 'independently corroborated' (cwj); now C U+F201"}   # never reused (Rule 0)
SPARES = {"task (gaz)": ["hzw", "gxj"], "associated (wap)": ["xsz", "yrx"]}   # alternatives only; not accepted
ACT_NAMES = ["inform", "request", "confirm", "disconfirm", "refuse", "propose", "failure", "not-understood"]
HEAD_KEY = {"claim": "kef", "source": "duv", "log entry": "vop", "task": "gaz", "figure": "fub",
            "statement made": "tez", "act done": "rux", "relation": "zim", "gap or contradiction": "xem"}
COMPAT = {"T": {"gaz"}, "R": {"zim"}, "E": {"kef", "fub", "duv", "tez"}, "P": {"kef", "fub", "duv", "tez"},
          "C": {"kef", "fub", "duv", "tez"},    # SAVTEZ-2c: same heads as P
          "A": {"vop", "kef"}, "H": None}       # keys are concept keys (legacy spelling) so both forms share one rule set
RELATIONAL = {"zim", "xem"}
MONEY = re.compile(r"[$€£¥]\s?\d|\d\s?[$€£¥]|\b(USD|EUR|GBP|CAD|JPY|CHF|AUD)\s?\d|\d\s?(USD|EUR|GBP|CAD|JPY|CHF|AUD)\b")

# lookup tables
BY_CP = {cp: (ax, m, old, new) for cp, ax, m, old, new in CONCEPTS}
KEY = {cp: (old or new) for cp, ax, m, old, new in CONCEPTS}            # concept key for COMPAT / RELATIONAL
for cp, (ax, m, old, new) in BY_CP.items():
    if ax == "HEAD": KEY[cp] = HEAD_KEY[m]
NEW = {new: cp for cp, ax, m, old, new in CONCEPTS}
OLD = {old: cp for cp, ax, m, old, new in CONCEPTS if old}
SUSPENDED = {"dax"}
# PUA check works on offsets mod P_PUA: every part (and retired code point) must have a distinct residue, else a
# substitution between two parts could keep the check (Rule 0). Asserted, not assumed.
_RES = [(cp - 0xE000) % P_PUA for cp in list(BY_CP) + list(RETIRED)]
assert len(set(_RES)) == len(_RES), "PUA check residues collide"
assert not any(CHECK_PUA_BASE <= cp < CHECK_PUA_BASE + P_PUA or cp == 0xE800 for cp in list(BY_CP) + list(RETIRED))
assert not set(BY_CP) & set(RETIRED)


class Reject(Exception):
    def __init__(self, rule, sec):
        super().__init__(rule); self.rule, self.sec = rule, sec


# ---------------- check characters (Damm-style: totally anti-symmetric quasigroup x*y = g*x + y mod p) ----------------
def damm(vals, p, g, seed=0):
    i = seed % p
    for v in vals: i = (g * i + v) % p
    return i
def check_ascii(parts_str):   # value -> char in ALPHA
    return ALPHA[(-G_ASCII * damm([ALPHA.index(c) for c in parts_str], P_ASCII, G_ASCII)) % P_ASCII]
def _prim_root(p):
    fac = [q for q in range(2, p) if (p - 1) % q == 0 and all(q % r for r in range(2, int(q ** .5) + 1))]
    return next(g for g in range(2, p) if all(pow(g, (p - 1) // q, p) != 1 for q in fac))
G_PUA = _prim_root(P_PUA)
def check_pua(cps):
    # seeded with the part count: PUA words have no length frame, so an inserted/deleted symbol must change the check
    return chr(CHECK_PUA_BASE + (-G_PUA * damm([(cp - 0xE000) % P_PUA for cp in cps], P_PUA, G_PUA, seed=len(cps))) % P_PUA)


# ---------------- word grammar (shared by both forms; spec 4) ----------------
def grammar(cps, shown):
    """cps: list of concept code points. Returns English decode or raises Reject."""
    axes = [BY_CP[c][0] for c in cps]
    for s, a in zip(shown, axes):
        if a == "ACT":
            raise Reject(f"part outside canonical order: '{s}' is a message act, which has no word slot; acts go in the message header per spec 5", 4)
    if axes[-1] != "HEAD":
        raise Reject(f"part outside canonical order: word must end in its HEAD; last part '{shown[-1]}' is {AXNAME[axes[-1]]} ({axes[-1]})", 4)
    fh = axes.index("HEAD")
    for i in range(fh, len(cps)):
        if axes[i] != "HEAD":
            raise Reject(f"part outside canonical order: modifier '{shown[i]}' ({axes[i]}) comes after a head", 4)
    seen = {}
    for i in range(fh):
        a = axes[i]
        if a in seen:
            raise Reject(f"two values on one axis: {a} ({AXNAME[a]}) has '{seen[a]}' and '{shown[i]}'", 4)
        seen[a] = shown[i]
    for i in range(1, fh):
        if ORDER.index(axes[i]) < ORDER.index(axes[i - 1]):
            raise Reject(f"part outside canonical order: '{shown[i]}' ({axes[i]}) after '{shown[i-1]}' ({axes[i-1]}); order is H T E P C A R + HEAD", 4)
    head, hk, args = cps[-1], KEY[cps[-1]], cps[fh:-1]
    for i in range(fh):
        a = axes[i]
        if COMPAT[a] is not None and hk not in COMPAT[a]:
            allowed = ", ".join(BY_CP[c][1] for c in BY_CP if BY_CP[c][0] == "HEAD" and KEY[c] in COMPAT[a])
            raise Reject(f"axis-head mismatch: {a} ({AXNAME[a]}) '{shown[i]}' is not allowed on head '{shown[-1]}' ({BY_CP[head][1]}); {a} only with: {allowed}", 4)
    if hk in RELATIONAL:
        if len(args) not in (0, 2):
            raise Reject(f"{len(args)} argument head(s) before relational head '{shown[-1]}' ({BY_CP[head][1]}): exactly 0 or 2 allowed (1 or 3+ rejected)", 4)
    elif args:
        raise Reject(f"part outside canonical order: head(s) before non-relational head '{shown[-1]}'; only relation/gap heads take argument heads", 4)
    d = BY_CP[head][1]
    if args: d += f" between [{BY_CP[args[0]][1]}] and [{BY_CP[args[1]][1]}]"
    if fh: d += " | " + "; ".join(f"{axes[i]} {AXNAME[axes[i]]}: {BY_CP[cps[i]][1]}" for i in range(fh))
    return d


def render(cps):
    a = "".join(BY_CP[c][3] for c in cps)
    return SIGIL + a + check_ascii(a), SIGIL_PUA + "".join(map(chr, cps)) + check_pua(cps)


def validate_new(word):
    if word == "": raise Reject("missing sigil: empty word", 4)
    if word[0] == SIGIL_PUA:
        body, chk = word[1:-1], word[-1:]
        if not body: raise Reject("unknown part: no parts between sigil and check", 4)
        for ch in body:
            if ord(ch) in RETIRED:
                raise Reject(f"retired code point U+{ord(ch):04X}: {RETIRED[ord(ch)]} (SAVTEZ-2c); old words are not reinterpreted", 4)
            if ord(ch) not in BY_CP:
                raise Reject(f"unknown part: U+{ord(ch):04X}", 4)
        cps = [ord(c) for c in body]
        if chk != check_pua(cps):
            raise Reject(f"bad check: check symbol U+{ord(chk):04X} does not match the parts (expected U+{ord(check_pua(cps)):04X}); damaged word", 4)
        shown = [BY_CP[c][3] for c in cps]
    else:
        if word[0] != SIGIL:
            raise Reject(f"missing sigil: a Savtez word starts with '{SIGIL}' (ASCII) or U+E800 (canonical)", 4)
        rest = word[1:]
        bad = sorted(set(c for c in rest if c not in ALPHA))
        if bad:
            raise Reject(f"unknown part: character(s) {' '.join(repr(c) for c in bad)} outside the alphabet {ALPHA}", 4)
        if len(rest) < 4 or (len(rest) - 1) % 3:
            raise Reject(f"unknown part: {len(rest)} characters after the sigil; need 3 per part + 1 check", 4)
        a, chk = rest[:-1], rest[-1]
        if chk != check_ascii(a):
            raise Reject(f"bad check: check char '{chk}' does not match the parts (expected '{check_ascii(a)}'); damaged word", 4)
        shown = [a[i:i + 3] for i in range(0, len(a), 3)]
        for s in shown:
            if s not in NEW:
                raise Reject(f"unknown part '{s}'", 4)
        cps = [NEW[s] for s in shown]
    d = grammar(cps, shown)
    asc, pua = render(cps)
    return cps, d, asc, pua


def validate_legacy(word):
    """v0.3 bare CVC placeholder words (no sigil, no check)."""
    if word == "": raise Reject("unknown part: empty word", 4)
    if not re.fullmatch(r"[a-z]+", word): raise Reject(f"unknown part: '{word}' is not lowercase letters only", 4)
    if len(word) % 3: raise Reject(f"unknown part: length {len(word)} is not a whole number of 3-letter parts", 4)
    shown = [word[i:i + 3] for i in range(0, len(word), 3)]
    for s in shown:
        if s in SUSPENDED: raise Reject(f"suspended part '{s}': dax (not) is SUSPENDED; polarity lives in axis values", 4)
        if s not in OLD: raise Reject(f"unknown part '{s}'", 4)
    cps = [OLD[s] for s in shown]
    return cps, grammar(cps, shown)


def run_word(w, legacy=False):
    try:
        if legacy:
            cps, d = validate_legacy(w)
            asc, pua = render(cps)
            return True, f"VALID | {w} | {d} | legacy form; new form {asc} (PROPOSED)"
        cps, d, asc, pua = validate_new(w)
        return True, f"VALID | {show(w)} | {d} | canonical {' '.join('U+%04X' % ord(c) for c in pua)} | ASCII {asc} | legacy {''.join(BY_CP[c][2] or '(TBD)' for c in cps)}"
    except Reject as r:
        return False, f"REJECT | {show(w)} | {r.rule} (spec {r.sec}) | required reply: §L0.3 not-understood"


def show(s):
    return "".join(c if ord(c) < 0xE000 else "<U+%04X>" % ord(c) for c in s).replace("\n", "\\n")


# ---------------- messages (spec 5) ----------------
def body_hash(lines):
    return hashlib.sha256("\n".join(l.rstrip() for l in lines).encode("utf-8")).hexdigest()[:8]


def validate_message(text, legacy=False, critical=False):
    lines = text.replace("\r\n", "\n").split("\n")
    while lines and lines[-1] == "": lines.pop()
    if not lines: raise Reject("empty message: header missing", 5)
    m = re.fullmatch(r"§L(\S+) (\S+)", lines[0].strip())
    if not m: raise Reject(f"bad header '{lines[0]}': must be '§L<version> <ACT>'", 5)
    ver, act = m.groups()
    if act not in ACT_NAMES:
        if legacy: raise Reject(f"unknown message act '{act}'; allowed: {' | '.join(ACT_NAMES)}", 5)
        try:
            cps, _, _, _ = validate_new_act(act)
            act = BY_CP[cps[0]][1]
        except Reject as r:
            raise Reject(f"unknown message act '{show(act)}': {r.rule}; allowed: {' | '.join(ACT_NAMES)} or a framed act form", 5)
    if ver not in VERSIONS: raise Reject(f"version '{ver}' not decodable by this dictionary (v0.3 only)", 6)
    body, hline = lines[1:], None
    if body and body[-1].startswith("#"):
        hline = body.pop()
        if not re.fullmatch(r"#[0-9a-f]{8}", hline.strip()): raise Reject(f"bad integrity line '{hline}': must be # + 8 lowercase hex", 5)
    out, crit, why = [f"header: v{ver}, act {act}"], critical, (["--critical flag"] if critical else [])
    for n, line in enumerate(body, 2):
        lm = re.fullmatch(r"([+~!]) ?(.*)", line)
        if not lm: raise Reject(f"line {n}: item must start with a delta mark + (new), ~ (changed) or ! (retraction)", 5)
        mark, rest = lm.groups()
        f = [x.strip() for x in rest.split("|", 2)]
        if len(f) != 3: raise Reject(f"line {n}: item must be 'WORD | @ref | detail' (3 fields)", 5)
        w, ref, det = f
        try:
            if legacy: cps, d = validate_legacy(w)
            else: cps, d, _, _ = validate_new(w)
        except Reject as r:
            raise Reject(f"line {n}: word '{show(w)}': {r.rule}", r.sec)
        if ref and not re.fullmatch(r"@\S+", ref): raise Reject(f"line {n}: ref '{ref}' must be @ID or empty", 5)
        if mark == "~" and "->" not in det: raise Reject(f"line {n}: changed item (~) needs 'old -> new' in detail", 5)
        if 0xE302 in cps: crit = True; why.append(f"waiting-on-Nick (bix) item line {n}")
        if MONEY.search(det): crit = True; why.append(f"money figure line {n}")
        out.append({"+": "new", "~": "changed", "!": "retraction"}[mark] + ": " + d + (f" | ref {ref}" if ref else "") + (f" | detail: {det}" if det else ""))
    if hline:
        want = body_hash(body)
        if hline.strip()[1:] != want: raise Reject(f"integrity hash mismatch: message has {hline.strip()}, body hashes to #{want}", 5)
        out.append(f"integrity: #{want} matches")
    elif crit:
        raise Reject(f"critical message ({'; '.join(why)}) must end with # + first 8 hex of sha256 of the normalized body", 5)
    return " || ".join(out)


def validate_new_act(tok):
    """header act in new form: a framed single act part (sigil + form + check)."""
    if not tok or tok[0] not in (SIGIL, SIGIL_PUA): raise Reject("missing sigil", 4)
    if tok[0] == SIGIL:
        a, chk = tok[1:-1], tok[-1:]
        if a not in NEW or BY_CP[NEW[a]][0] != "ACT": raise Reject(f"'{a}' is not a message act form", 5)
        if chk != check_ascii(a): raise Reject("bad check", 4)
        return [NEW[a]], None, None, None
    cps = [ord(c) for c in tok[1:-1]]
    if len(cps) != 1 or cps[0] not in BY_CP or BY_CP[cps[0]][0] != "ACT": raise Reject("not a message act symbol", 5)
    if tok[-1] != check_pua(cps): raise Reject("bad check", 4)
    return cps, None, None, None


def run_msg(text, legacy=False, critical=False):
    try:
        return True, "VALID | " + validate_message(text, legacy, critical)
    except Reject as r:
        return False, f"REJECT | {show(text)} | {r.rule} (spec {r.sec}) | required reply: §L0.3 not-understood"


# ---------------- helpers ----------------
def encode_legacy(w):
    cps, d = validate_legacy(w)
    return render(cps)
def frame_raw(parts_ascii):
    """frame arbitrary ASCII parts with sigil + CORRECT check (to test grammar rules behind a valid check)."""
    return SIGIL + parts_ascii + check_ascii(parts_ascii)


def code_table():
    rows = ["code point | axis | concept | legacy (v0.3 placeholder) | NEW generated ASCII form | status"]
    for cp, ax, m, old, new in CONCEPTS:
        tag = {0xE204: "SAVTEZ-2b", 0xE101: "SAVTEZ-2; relabelled SAVTEZ-2c", 0xE103: "SAVTEZ-2b; redefined SAVTEZ-2c",
               0xE104: "SAVTEZ-2c", 0xE205: "SAVTEZ-2c; form from 2b", 0xF200: "SAVTEZ-2c; form from 2", 0xF201: "SAVTEZ-2c; form from 2"}.get(cp, "SAVTEZ-2")
        rows.append(f"U+{cp:04X} | {ax} | {m} | {old or '(TBD)'} | {new} | PROPOSED ({tag}), pending Nick's yes")
    for cp, why in RETIRED.items():
        rows.append(f"U+{cp:04X} | retired | {why} | - | - | RETIRED by SAVTEZ-2c proposal; never reused, rejected")
    rows.append("none | - | not (dax) | dax | none | SUSPENDED: no axis, no code point, no new form")
    rows.append("U+E800 | frame | SIGIL | - | ^ | PROPOSED; approved structure (spec 4 r3)")
    rows.append(f"U+E900-U+{CHECK_PUA_BASE + P_PUA - 1:04X} | frame | CHECK symbols (canonical form) | - | one char of {ALPHA} | PROPOSED")
    rows.append("U+F200-U+F2FF | C block | corroboration values (F200, F201 used) | - | - | PROPOSED (SAVTEZ-2c)")
    for k, v in SPARES.items(): rows.append(f"spare | {k} | alternatives | - | {' / '.join(v)} | would keep the concept's code point")
    return rows


# ---------------- word enumeration + Rule 0 typo gate ----------------
def all_words():
    heads = [cp for cp in BY_CP if BY_CP[cp][0] == "HEAD"]
    vals = {a: [None] + [cp for cp in BY_CP if BY_CP[cp][0] == a] for a in ORDER}
    for h in heads:
        hk = KEY[h]
        axes = [a for a in ORDER if COMPAT[a] is None or hk in COMPAT[a]]
        arglist = [[]] + ([[x, y] for x in heads for y in heads] if hk in RELATIONAL else [])
        for combo in itertools.product(*[vals[a] for a in axes]):
            mods = [c for c in combo if c is not None]
            for args in arglist:
                yield mods + args + [h]

PRINTABLE = [chr(c) for c in range(32, 127)]
def typos(s, alphabet):
    out = set()
    for i in range(len(s)):
        for c in alphabet:
            if c != s[i]: out.add(s[:i] + c + s[i + 1:])
        out.add(s[:i] + s[i + 1:])
        if i + 1 < len(s) and s[i] != s[i + 1]: out.add(s[:i] + s[i + 1] + s[i] + s[i + 2:])
    for i in range(len(s) + 1):
        for c in alphabet: out.add(s[:i] + c + s[i:])
    out.discard(s)
    return out

def typo_gate(quick=False):
    rows, total_fail = [], 0
    words = list(all_words())
    if quick: words = words[::7]
    rnd = random.Random(20261102)
    # complete for PUA: every part symbol + sigil (any other symbol is an unknown part, and a check symbol
    # substituted for the check is unique, so always caught) + a sample of check symbols and ASCII
    pua_alpha = [chr(cp) for cp in BY_CP] + [chr(cp) for cp in RETIRED] + [SIGIL_PUA] + [chr(CHECK_PUA_BASE + v) for v in rnd.sample(range(P_PUA), 40)] + list("abc^ ")
    modes = [
        ("legacy CVC placeholders, bare (current parts)", lambda c: "".join(BY_CP[x][2] or "" for x in c) if all(BY_CP[x][2] for x in c) else None, lambda w: validate_legacy(w)[0], PRINTABLE, False),
        ("NEW forms, bare (no sigil/check; distance rule only)", lambda c: "".join(BY_CP[x][3] for x in c), lambda w: _bare_new(w), PRINTABLE, False),
        ("NEW forms, framed ASCII (sigil + check)", lambda c: render(c)[0], lambda w: validate_new(w)[0], PRINTABLE, True),
        ("NEW forms, framed canonical PUA (sigil + check)", lambda c: render(c)[1], lambda w: validate_new(w)[0], pua_alpha, True),
    ]
    for name, enc, dec, alpha, must_zero in modes:
        nw = nt = mis = 0; examples = []
        for cps in words:
            w = enc(cps)
            if w is None: continue
            nw += 1
            for t in typos(w, alpha):
                nt += 1
                try:
                    got = dec(t)
                except Reject:
                    continue
                if got != cps:
                    mis += 1
                    if len(examples) < 4: examples.append(f"{show(w)}->{show(t)}")
        ok = (mis == 0) if must_zero else True
        total_fail += not ok
        rows.append(f"TYPO | {'PASS' if ok else 'FAIL'} | {name} | words {nw} | single-char typos tried {nt} | misdecodes {mis} ({100.0*mis/max(nt,1):.4f}%) | {'must be 0' if must_zero else 'report only'} | e.g. {'; '.join(examples) or '-'}")
    # double typos on framed ASCII: residual risk
    nt = mis = 0
    for cps in rnd.sample(words, min(400, len(words))):
        w = render(cps)[0]
        singles = list(typos(w, ALPHA + SIGIL))
        for t1 in rnd.sample(singles, min(60, len(singles))):
            t2s = list(typos(t1, ALPHA + SIGIL))
            for t2 in rnd.sample(t2s, min(10, len(t2s))):
                if t2 == w: continue
                nt += 1
                try:
                    if validate_new(t2)[0] != cps: mis += 1
                except Reject:
                    pass
    rows.append(f"TYPO | INFO | NEW framed ASCII, random DOUBLE typos (in-alphabet) | tried {nt} | misdecodes {mis} ({100.0*mis/max(nt,1):.3f}%) | catch rate {100.0*(nt-mis)/max(nt,1):.3f}% | report only (one check char cannot catch every 2-error)")
    # exhaustive proof for the check scheme itself
    sub = trans = 0; ns = nt2 = 0
    for cps in rnd.sample(words, min(300, len(words))):
        a = "".join(BY_CP[c][3] for c in cps); s = a + check_ascii(a)
        for i in range(len(s)):
            for c in ALPHA:
                if c != s[i]:
                    ns += 1; t = s[:i] + c + s[i+1:]
                    sub += t[-1] == check_ascii(t[:-1])
            if i + 1 < len(s) and s[i] != s[i+1]:
                nt2 += 1; t = s[:i] + s[i+1] + s[i] + s[i+2:]
                trans += t[-1] == check_ascii(t[:-1])
    rows.append(f"CHECK | {'PASS' if sub == 0 and trans == 0 else 'FAIL'} | Damm-style x*y=3x+y mod 17 over ASCII chars | single substitutions undetected {sub}/{ns} | adjacent transpositions undetected {trans}/{nt2}")
    total_fail += not (sub == 0 and trans == 0)
    return rows, total_fail

def _bare_new(w):
    if len(w) % 3 or not w or any(c not in ALPHA for c in w): raise Reject("x", 4)
    shown = [w[i:i+3] for i in range(0, len(w), 3)]
    if any(s not in NEW for s in shown): raise Reject("x", 4)
    cps = [NEW[s] for s in shown]; grammar(cps, shown); return cps


# ---------------- gate ----------------
def F(legacy_spelling):           # new framed form of a legacy spelling
    return encode_legacy(legacy_spelling)[0]
def FP(legacy_spelling):
    return encode_legacy(legacy_spelling)[1]
def broken_check(w):
    good = w[-1]; return w[:-1] + next(c for c in ALPHA if c != good)

def gate_cases():
    n = lambda *legs: "".join(BY_CP[OLD[x]][3] for x in legs)   # raw new parts from legacy names
    G = [  # (label, input, legacy?, message?, expect VALID?, required substring)
     ("REJECT wrong order (kefsav)", frame_raw(n("kef", "sav")), False, False, False, "outside canonical order"),
     ("REJECT two values on one axis (savlodkef)", frame_raw(n("sav", "lod", "kef")), False, False, False, "two values on one axis"),
     ("REJECT T on a non-task head (hiwkef)", frame_raw(n("hiw", "kef")), False, False, False, "axis-head mismatch"),
     ("REJECT relation with 1 argument (tezxem)", frame_raw(n("tez", "xem")), False, False, False, "1 argument head"),
     ("REJECT unknown part (qqqkef -> bbbkef: in-alphabet, unassigned)", frame_raw("bbb" + n("kef")), False, False, False, "unknown part 'bbb'"),
     ("REJECT unknown part (qqqkef: q outside alphabet)", SIGIL + "qqq" + n("kef") + "b", False, False, False, "outside the alphabet"),
     ("REJECT missing sigil (savpevkef new form without ^)", F("savpevkef")[1:], False, False, False, "missing sigil"),
     ("REJECT bad check (savpevkef new form, check char altered)", broken_check(F("savpevkef")), False, False, False, "bad check"),
     ("ACCEPT savpevkef (new form) [v2c: expectation changed by the axis split; v2b expected 'P provenance: single-origin']", F("savpevkef"), False, False, True, "claim | E evidence: verified against a primary source; C corroboration: single-origin, no independent corroboration"),
     ("ACCEPT tezruxxem (new form)", F("tezruxxem"), False, False, True, "gap or contradiction between [statement made] and [act done]"),
     ("ACCEPT bixgaz (new form)", F("bixgaz"), False, False, True, "task | T task state: waiting on Nick's word"),
     ("ACCEPT savtez (new form)", F("savtez"), False, False, True, "statement made | E evidence: verified against a primary source"),
     ("ACCEPT savpevkef (canonical PUA) [v2c: expectation changed by the axis split; v2b expected 'P provenance']", FP("savpevkef"), False, False, True, "claim | E evidence: verified against a primary source; C corroboration"),
     ("REJECT bad check (canonical PUA)", FP("savpevkef")[:-1] + chr(ord(FP("savpevkef")[-1]) ^ 1), False, False, False, "bad check"),
    ]
    L = [  # legacy old-form gate (v0.3 bare words)
     ("LEGACY REJECT kefsav", "kefsav", True, False, False, "outside canonical order"),
     ("LEGACY REJECT savlodkef", "savlodkef", True, False, False, "two values on one axis"),
     ("LEGACY REJECT hiwkef", "hiwkef", True, False, False, "axis-head mismatch"),
     ("LEGACY REJECT tezxem", "tezxem", True, False, False, "1 argument head"),
     ("LEGACY REJECT qqqkef", "qqqkef", True, False, False, "unknown part 'qqq'"),
     ("LEGACY ACCEPT savpevkef [v2c: expectation changed by the axis split; v2b expected 'P provenance: single-origin']", "savpevkef", True, False, True, "claim | E evidence: verified against a primary source; C corroboration: single-origin, no independent corroboration"),
     ("LEGACY ACCEPT tezruxxem", "tezruxxem", True, False, True, "gap or contradiction between [statement made] and [act done]"),
     ("LEGACY ACCEPT bixgaz", "bixgaz", True, False, True, "task | T task state: waiting on Nick's word"),
     ("LEGACY ACCEPT savtez", "savtez", True, False, True, "statement made | E evidence: verified against a primary source"),
    ]
    b1 = "+ " + F("bixgaz") + " | @SAVTEZ-2 | approve proposals"
    m2 = "+ " + F("fidfub") + " | | spend $120 -> $140"
    E = [
     ("EDGE head only", F("kef"), False, False, True, "claim"),
     ("EDGE empty", "", False, False, False, "missing sigil"),
     ("EDGE sigil only", "^", False, False, False, "unknown part"),
     ("EDGE legacy spelling in new mode", "savpevkef", False, False, False, "missing sigil"),
     ("EDGE legacy spelling framed", frame_raw("savpevkef") if all(c in ALPHA for c in "savpevkef") else "^savpevkefb", False, False, False, "outside the alphabet"),
     ("EDGE uppercase", F("kef").upper(), False, False, False, "outside the alphabet"),
     ("EDGE wrong length", F("kef")[:-2] + F("kef")[-1], False, False, False, "need 3 per part"),
     ("EDGE sigil variant (U+02C6 modifier circumflex)", "\u02c6" + F("kef")[1:], False, False, False, "missing sigil"),
     ("EDGE double sigil", "^" + F("kef"), False, False, False, "outside the alphabet"),
     ("EDGE hiwgaz", F("hiwgaz"), False, False, True, "on hold"),
     ("EDGE zutgaz", F("zutgaz"), False, False, True, "blocked"),
     ("EDGE kyrzim", F("kyrzim"), False, False, True, "causal, established"),
     ("EDGE wapzim", F("wapzim"), False, False, True, "associated"),
     ("EDGE R on claim", frame_raw(n("kyr", "kef")), False, False, False, "axis-head mismatch"),
     ("EDGE A on source", frame_raw(n("zof", "duv")), False, False, False, "axis-head mismatch"),
     ("EDGE E on log entry", frame_raw(n("sav", "vop")), False, False, False, "axis-head mismatch"),
     ("EDGE E on task", frame_raw(n("sav", "gaz")), False, False, False, "axis-head mismatch"),
     ("EDGE two H", frame_raw(n("vun", "tib", "vop")), False, False, False, "two values on one axis"),
     ("EDGE H on any head (vun+xem with args)", F("vuntezruxxem"), False, False, True, "internal"),
     ("EDGE all slots on claim", F("vunsavpevzofkef"), False, False, True, "nothing found"),
     ("EDGE H after E", frame_raw(n("sav", "vun", "kef")), False, False, False, "outside canonical order"),
     ("EDGE P before E", frame_raw(n("pev", "sav", "kef")), False, False, False, "outside canonical order"),
     ("EDGE head before non-relational head", frame_raw(n("tez", "kef")), False, False, False, "non-relational head"),
     ("EDGE modifier after head", frame_raw(n("kef", "sav", "kef")), False, False, False, "comes after a head"),
     ("EDGE relation 3 args", frame_raw(n("tez", "rux", "kef", "xem")), False, False, False, "3 argument head"),
     ("EDGE relation 2 args", F("kefduvzim"), False, False, True, "relation between [claim] and [source]"),
     ("EDGE E on gap head", frame_raw(n("sav", "tez", "rux", "xem")), False, False, False, "axis-head mismatch"),
     ("EDGE new T value queued", SIGIL + "rxm" + n("gaz") + check_ascii("rxm" + n("gaz")), False, False, True, "queued"),
     ("EDGE new P value quoted", SIGIL + n("sav") + "pzx" + n("kef") + check_ascii(n("sav") + "pzx" + n("kef")), False, False, True, "quoted verbatim"),
     ("EDGE 2b E inferred on claim [v2c: expectation changed by the axis split; v2b expected 'E evidence: inferred by us']", SIGIL + "wxg" + n("kef") + check_ascii("wxg" + n("kef")), False, False, True, "P derivation: inferred by us"),
     ("EDGE 2b E unknown on figure [v2c: expectation changed by the axis split; v2b expected 'E evidence: unknown']", SIGIL + "yhz" + n("fub") + check_ascii("yhz" + n("fub")), False, False, True, "E evidence: inconclusive (checked, undetermined)"),
     ("EDGE 2b P assumed on claim [v2c: expectation changed by the axis split; v2b expected 'P provenance: assumed']", SIGIL + "xjc" + n("kef") + check_ascii("xjc" + n("kef")), False, False, True, "P derivation: assumed, not checked"),
     ("EDGE 2b E inferred + P assumed on statement [v2c: expectation changed by the axis split; v2b expected ACCEPT; both are P now]", SIGIL + "wxgxjc" + n("tez") + check_ascii("wxgxjc" + n("tez")), False, False, False, "two values on one axis: P"),
     ("EDGE 2b PUA E unknown on claim [v2c: expectation changed by the axis split; v2b expected 'E evidence: unknown']", SIGIL_PUA + "\ue103\ue000" + check_pua([0xE103, 0xE000]), False, False, True, "E evidence: inconclusive"),
     ("EDGE 2b two E (verified + inferred) [v2c: expectation changed by the axis split; v2b expected REJECT two E; now E + P]", frame_raw(n("sav") + "wxg" + n("kef")), False, False, True, "E evidence: verified against a primary source; P derivation: inferred by us"),
     ("EDGE 2b two E (inferred + unknown) [v2c: expectation changed by the axis split; v2b expected 'two values'; now P before E]", frame_raw("wxgyhz" + n("kef")), False, False, False, "outside canonical order"),
     ("EDGE 2b two P (single-origin + assumed) [v2c: expectation changed by the axis split; v2b expected 'two values'; now C before P]", frame_raw(n("pev") + "xjc" + n("kef")), False, False, False, "outside canonical order"),
     ("EDGE 2b P before E (assumed, inferred) [v2c: expectation changed by the axis split; v2b expected 'outside canonical order'; now two P]", frame_raw("xjcwxg" + n("kef")), False, False, False, "two values on one axis"),
     ("EDGE 2b E unknown on task", frame_raw("yhz" + n("gaz")), False, False, False, "axis-head mismatch"),
     ("EDGE 2b P assumed on log entry", frame_raw("xjc" + n("vop")), False, False, False, "axis-head mismatch"),
     # ---- SAVTEZ-2c (PROPOSAL): the 4 brief cases ----
     ("EDGE 2c BRIEF P and C: quoted + single-origin + claim", frame_raw("pzxdxz" + n("kef")), False, False, True, "claim | P derivation: quoted verbatim from a source; C corroboration: single-origin"),
     ("EDGE 2c BRIEF two P values (quoted + calculated)", frame_raw("pzxtfy" + n("kef")), False, False, False, "two values on one axis: P"),
     ("EDGE 2c BRIEF C before P (single-origin, quoted)", frame_raw("dxzpzx" + n("kef")), False, False, False, "outside canonical order: 'pzx' (P) after 'dxz' (C)"),
     ("EDGE 2c BRIEF refuted + claim", frame_raw("hxy" + n("kef")), False, False, True, "claim | E evidence: refuted (checked, found false)"),
     # ---- SAVTEZ-2c extra cases ----
     ("EDGE 2c refuted + claim (PUA)", SIGIL_PUA + "\ue104\ue000" + check_pua([0xE104, 0xE000]), False, False, True, "E evidence: refuted"),
     ("EDGE 2c P and C (PUA, quoted + single-origin + claim)", SIGIL_PUA + "\ue202\uf200\ue000" + check_pua([0xE202, 0xF200, 0xE000]), False, False, True, "P derivation: quoted verbatim from a source; C corroboration: single-origin"),
     ("EDGE 2c inferred (now P) on claim, PUA U+E205", SIGIL_PUA + "\ue205\ue000" + check_pua([0xE205, 0xE000]), False, False, True, "P derivation: inferred by us"),
     ("EDGE 2c corroborated + figure", frame_raw("cwj" + n("fub")), False, False, True, "figure | C corroboration: independently corroborated"),
     ("EDGE 2c E + P + C on statement (refuted, calculated, corroborated)", frame_raw("hxytfycwj" + n("tez")), False, False, True, "E evidence: refuted (checked, found false); P derivation: calculated by us; C corroboration: independently corroborated"),
     ("EDGE 2c all 7 slots: H E P C A on claim", frame_raw(n("vun") + "zbhpzx" + "cwj" + n("zof") + n("kef")), False, False, True, "H handling: internal"),
     ("EDGE 2c two C (single-origin + corroborated)", frame_raw("dxzcwj" + n("kef")), False, False, False, "two values on one axis: C"),
     ("EDGE 2c two E (refuted + inconclusive)", frame_raw("hxyyhz" + n("kef")), False, False, False, "two values on one axis: E"),
     ("EDGE 2c C before E", frame_raw("dxzhxy" + n("kef")), False, False, False, "outside canonical order"),
     ("EDGE 2c A before C", frame_raw(n("zof") + "dxz" + n("kef")), False, False, False, "outside canonical order"),
     ("EDGE 2c C on task", frame_raw("cwj" + n("gaz")), False, False, False, "axis-head mismatch: C"),
     ("EDGE 2c C on log entry", frame_raw("dxz" + n("vop")), False, False, False, "axis-head mismatch: C"),
     ("EDGE 2c C on relation", frame_raw("dxz" + n("zim")), False, False, False, "axis-head mismatch: C"),
     ("EDGE 2c refuted on task", frame_raw("hxy" + n("gaz")), False, False, False, "axis-head mismatch: E"),
     ("EDGE 2c retired U+E102 (v2b E inferred)", SIGIL_PUA + "\ue102\ue000" + check_pua([0xE102, 0xE000]), False, False, False, "retired code point U+E102"),
     ("EDGE 2c retired U+E200 (v2b P single-origin)", SIGIL_PUA + "\ue200\ue000" + check_pua([0xE200, 0xE000]), False, False, False, "retired code point U+E200"),
     ("EDGE 2c retired U+E203 (v2b P corroborated)", SIGIL_PUA + "\ue203\ue000" + check_pua([0xE203, 0xE000]), False, False, False, "retired code point U+E203"),
     ("EDGE 2c v2b PUA word ^zbh dxz claim (E100 E200 E000) not reinterpreted", SIGIL_PUA + "\ue100\ue200\ue000" + check_pua([0xE100, 0xE200, 0xE000]), False, False, False, "retired code point U+E200"),
     ("EDGE 2c unassigned C-block symbol U+F202", SIGIL_PUA + "\uf202\ue000" + check_pua([0xF202, 0xE000]), False, False, False, "unknown part: U+F202"),
     ("EDGE 2c unassigned survivor wjx", frame_raw("wjx" + n("kef")), False, False, False, "unknown part 'wjx'"),
     ("LEGACY EDGE 2c pevfidkef (C before P)", "pevfidkef", True, False, False, "outside canonical order"),
     ("LEGACY EDGE 2c fidpevkef (P + C)", "fidpevkef", True, False, True, "P derivation: calculated by us; C corroboration: single-origin"),
     ("EDGE 2b unassigned survivor zrw", frame_raw("zrw" + n("kef")), False, False, False, "unknown part 'zrw'"),
     ("EDGE two T (bix + active)", frame_raw(n("bix") + "xbk" + n("gaz")), False, False, False, "two values on one axis"),
     ("EDGE act part inside a word", frame_raw("yzd" + n("kef")), False, False, False, "message act"),
     ("EDGE spare form not accepted", frame_raw("hzw"), False, False, False, "unknown part 'hzw'"),
     ("EDGE PUA unknown symbol", SIGIL_PUA + "\ue0ff" + "\ue900", False, False, False, "unknown part: U+E0FF"),
     ("LEGACY EDGE dax", "daxkef", True, False, False, "suspended"),
     ("LEGACY EDGE Kef", "Kef", True, False, False, "unknown part"),
     ("MSG valid", "§L0.3 inform\n+ " + F("savkef") + " | @R-1 | revenue up\n+ " + F("zofvop") + " | @LOG-7 |", False, True, True, "act inform"),
     ("MSG act in new form", "§L0.3 ^yzd" + check_ascii("yzd") + "\n+ " + F("savkef") + " | @R-1 | x", False, True, True, "act inform"),
     ("MSG act new form bad check", "§L0.3 ^yzd" + broken_check("^yzd" + check_ascii("yzd"))[-1] + "\n+ " + F("savkef") + " | @R-1 | x", False, True, False, "unknown message act"),
     ("MSG legacy word in new mode", "§L0.3 inform\n+ savkef | @R-1 | x", False, True, False, "missing sigil"),
     ("MSG bad version", "§L0.2 inform\n+ " + F("savkef") + " | @R-1 | x", False, True, False, "version '0.2'"),
     ("MSG unknown act", "§L0.3 tell\n+ " + F("savkef") + " | @R-1 | x", False, True, False, "unknown message act"),
     ("MSG no delta mark", "§L0.3 inform\n" + F("savkef") + " | @R-1 | x", False, True, False, "delta mark"),
     ("MSG ~ needs ->", "§L0.3 inform\n~ " + F("savkef") + " | @R-1 | changed", False, True, False, "old -> new"),
     ("MSG critical without hash", "§L0.3 request\n" + b1, False, True, False, "critical message"),
     ("MSG critical with hash", "§L0.3 request\n" + b1 + "\n#" + body_hash([b1]), False, True, True, "integrity"),
     ("MSG wrong hash", "§L0.3 request\n" + b1 + "\n#00000000", False, True, False, "hash mismatch"),
     ("MSG money without hash", "§L0.3 inform\n" + m2, False, True, False, "money figure"),
     ("MSG legacy message", "§L0.3 inform\n+ savkef | @R-1 | x", True, True, True, "act inform"),
    ]
    return G, L, E

def gate(out_path=None, quick=False):
    G, L, E = gate_cases()
    rows, fails = [], 0
    for group, cases in (("GATE", G), ("GATE-LEGACY", L), ("EDGE", E)):
        for label, inp, leg, msg, want, need in cases:
            ok, res = (run_msg(inp, leg) if msg else run_word(inp, leg))
            passed = ok == want and need in res
            fails += not passed
            rows.append(f"{group} | {'PASS' if passed else 'FAIL'} | {label} | input {show(inp) or '(empty)'} | got {res}")
    n_cases = len(G) + len(L) + len(E)
    trows, tfail = typo_gate(quick)
    rows += trows
    rows.append(f"SUMMARY | gate {sum('GATE | PASS' in r for r in rows)}/{len(G)} | legacy gate {sum('GATE-LEGACY | PASS' in r for r in rows)}/{len(L)} | edge {sum('EDGE | PASS' in r for r in rows)}/{len(E)} | Rule 0 typo/check gates {'PASS' if tfail == 0 else 'FAIL'} | {'GATE PASSED' if fails == 0 and tfail == 0 else 'GATE FAILED'}")
    text = "\n".join(rows); print(text)
    if out_path:
        with open(out_path, "x", encoding="utf-8") as fh: fh.write(text + "\n")   # never overwrite
    return 0 if fails == 0 and tfail == 0 else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("word", nargs="?"); ap.add_argument("-m", "--message"); ap.add_argument("-f", "--file")
    ap.add_argument("--legacy", action="store_true"); ap.add_argument("--critical", action="store_true")
    ap.add_argument("--encode"); ap.add_argument("--hash", action="store_true"); ap.add_argument("--table", action="store_true")
    ap.add_argument("--gate", action="store_true"); ap.add_argument("--gate-out"); ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    if a.gate: return gate(a.gate_out, a.quick)
    if a.table: print("\n".join(code_table())); return 0
    if a.encode:
        try:
            asc, pua = encode_legacy(a.encode)
            print(f"{a.encode} | ASCII {asc} | canonical {' '.join('U+%04X' % ord(c) for c in pua)}"); return 0
        except Reject as r:
            print(f"REJECT | {a.encode} | {r.rule} (spec {r.sec})"); return 1
    msg = a.message if a.message is not None else (open(a.file, encoding="utf-8").read() if a.file else None)
    if msg is None and a.word and a.word.startswith("§"): msg = a.word
    if a.hash:
        if msg is None: ap.error("--hash needs -m or -f")
        ls = msg.replace("\r\n", "\n").split("\n")
        while ls and ls[-1] == "": ls.pop()
        print("#" + body_hash([l for l in ls[1:] if not l.startswith("#")])); return 0
    if msg is not None: ok, res = run_msg(msg, a.legacy, a.critical)
    elif a.word is not None: ok, res = run_word(a.word, a.legacy)
    else: ap.print_help(); return 2
    print(res); return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
