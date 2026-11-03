#!/usr/bin/env python3
"""SAVTEZ-2 / spec v0.3_r3 section 2 DESIGN PRINCIPLE: GENERATE the ASCII forms, don't hand-pick.
Pipeline: enumerate every 3-char string over the reduced alphabet -> zero multilingual word frequency
-> off acronym / slang / leetspeak / hexspeak lists -> not a single token in major tokenizers
-> typo-safe selection -> assign survivors to concepts. Also screens the current CVC placeholder parts
and picks the ASCII SIGIL fallback by a character-frequency check. Deterministic; PROPOSALS ONLY."""
import itertools, json, glob, os, math, hashlib, unicodedata, sys
import wordfreq, tiktoken
from tokenizers import Tokenizer

# Paths are relative to the repository root (edited for the public copy; the original used absolute local paths).
# The wordlists, tokenizers and corpora are NOT shipped in this repo (see data/SAVTEZ-LISTS_v2.txt); place them
# under external/ or point the SAVTEZ_WORDLISTS / SAVTEZ_TOKENIZERS / SAVTEZ_CORPORA environment variables at them.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WL = os.environ.get("SAVTEZ_WORDLISTS", os.path.join(REPO, "external", "wordlists"))
TK = os.environ.get("SAVTEZ_TOKENIZERS", os.path.join(REPO, "external", "tokenizers"))
CO = os.environ.get("SAVTEZ_CORPORA", os.path.join(REPO, "external", "corpora"))
# ---- reduced alphabet (Rule 0: no confusable characters) ----
TIERS = [  # lowercase only; within a tier no two symbols are confusable with each other; sizes are prime (Damm over Z_p)
 ("A11", "bdfhjkpstxz", "strict: no vowels; drops every member of every confusable class"),
 ("A13", "bdfghjkpstwxz", "A11 + g (q,9 absent) + w (v absent, so vv/w cannot occur)"),
 ("A17", "bcdfghjkmprstwxyz", "A13 + c (e,l absent) + m and r (n absent, so rn/m cannot occur) + y (v absent)"),
]
ALPHA = TIERS[0][1]
DROPPED = {
 "digits 0-9": "0/O/o, 1/l/I, 2/Z, 5/S, 6/b, 8/B, 9/g/q",
 "uppercase A-Z": "case confusion (I/l, O/0, S/s, Z/z...) - one case only",
 "l i j? ": "l/I/1/|, i/l/1 (j kept: dot+descender, no ASCII twin once i,l,1 are gone)",
 "o": "o/0/O", "m n r": "rn/m, n/h, r/n", "u v w y": "u/v, v/y, vv/w",
 "c g q": "c/e, cl/d, g/q/9", "a e": "vowels: a/o/d, e/c, and vowels make strings word-like (gaz ~ gas)",
}
CURRENT = "kef duv vop gaz fub tez rux zim xem sav lod pev fid zof gom wap kyr bix hiw zut vun tib dax".split()
CONFUSABLE_CHARS = set("0123456789ilomnruvwycgqae") | set(map(chr, range(65, 91)))
CONCEPTS = [  # (code point, axis, concept, placeholder)  -- code points from SAVTEZ-2 table
 (0xE000,"HEAD","claim","kef"),(0xE001,"HEAD","source","duv"),(0xE002,"HEAD","log entry","vop"),
 (0xE003,"HEAD","task","gaz"),(0xE004,"HEAD","figure","fub"),(0xE005,"HEAD","statement made","tez"),
 (0xE006,"HEAD","act done","rux"),(0xE007,"HEAD","relation","zim"),(0xE008,"HEAD","gap or contradiction","xem"),
 (0xE100,"E","verified against a primary source","sav"),(0xE101,"E","lead only, unverified","lod"),
 (0xE200,"P","single-origin, no independent corroboration","pev"),(0xE201,"P","calculated by us","fid"),
 (0xE202,"P","quoted verbatim from a source",None),(0xE203,"P","independently corroborated",None),
 (0xE300,"T","queued",None),(0xE301,"T","active",None),(0xE302,"T","waiting on Nick's word","bix"),
 (0xE303,"T","on hold","hiw"),(0xE304,"T","blocked","zut"),(0xE305,"T","done",None),
 (0xE306,"T","failed",None),(0xE307,"T","canceled",None),
 (0xE400,"A","searched the named source, nothing found","zof"),(0xE401,"A","record that should exist is absent","gom"),
 (0xE500,"R","associated, causation not claimed","wap"),(0xE501,"R","causal, established","kyr"),
 (0xE600,"H","internal, not for outside release","vun"),(0xE601,"H","append-only, never edited","tib"),
 (0xE700,"ACT","inform",None),(0xE701,"ACT","request",None),(0xE702,"ACT","confirm",None),
 (0xE703,"ACT","disconfirm",None),(0xE704,"ACT","refuse",None),(0xE705,"ACT","propose",None),
 (0xE706,"ACT","failure",None),(0xE707,"ACT","not-understood",None),
]
SPARES = [("gaz", 0xE003, 2), ("wap", 0xE500, 2)]
ACRONYMS = set(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "SAVTEZ-PROPOSE_v0.3.py")).read()
               .split('ACRONYMS = set("""')[1].split('"""')[0].split())   # 695-entry list written for SAVTEZ-2 r1
HEXSPEAK = set("""ace add bad bed bee cab cad dab dad deb dec def fab fad fed fee abe ada bab bea cee dee ebb eff
 b00 b0b d0d f00 f0e 0ff c0d 5ec 7ab 7ed be5 0dd ba5 5ad 5ea 5ee de5 d1e 1ce 1d0 b1d f1b f1d f1t b0a 10c c0c c01""".split())
LEET = {"z": ["s"], "k": ["c", "ck", "q"], "x": ["ks", "cks", "ex", "cs"], "f": ["ph", "v"], "j": ["g", "y"],
        "p": ["p"], "b": ["b", "8"], "d": ["d", "th"], "t": ["t", "7"], "s": ["s", "z", "5"], "h": ["h", "#"]}

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]

def load():
    langs = sorted(wordfreq.available_languages()); large = set(wordfreq.available_languages("large"))
    D = {l: wordfreq.get_frequency_dict(l, "large" if l in large else "best") for l in langs}
    ud = set()
    for f in sorted(glob.glob(f"{WL}/ud/*")):
        for line in open(f, encoding="utf-8", errors="ignore"): ud.add(line.strip().lower())
    import re, html
    nl = set(html.unescape(x).strip().lower() for x in re.findall(r'<a href="[^"]*">([^<]{1,12})</a>',
             open(f"{WL}/netlingo.html", encoding="utf-8", errors="ignore").read()))
    sys.path.insert(0, WL); import wikifetch
    W = wikifetch.ensure(["".join(p) for _, a, _ in TIERS for p in itertools.product(a, repeat=3)] + CURRENT)
    tk = {n: tiktoken.get_encoding(n) for n in ["cl100k_base", "o200k_base", "p50k_base", "r50k_base"]}
    hf = {os.path.basename(f)[:-5]: Tokenizer.from_file(f) for f in sorted(glob.glob(f"{TK}/*.json")) if os.path.getsize(f) > 1000}
    # txtspk / disemvowel skeletons of the 20k commonest words in Latin-script languages
    skel = set()
    for l in ["en","fr","de","es","pt","it","nl","pl","tr","sv","cs","ca","fi","nb","da","ro","hu","id","ms","fil","sk","sl","lt","lv","is","vi","sh"]:
        for w in itertools.islice(wordfreq.iter_wordlist(l, "large" if l in large else "best"), 20000):
            w2 = "".join(c for c in unicodedata.normalize("NFKD", w) if not unicodedata.combining(c)).lower()
            s = "".join(c for c in w2 if c.isalpha() and c not in "aeiouy")
            if 2 <= len(s) <= 4: skel.add(s)
    return langs, large, D, ud, nl, W, tk, hf, skel

def wf_hits(s, langs, D):
    """wordfreq.word_frequency > 0 in any of the 42 languages (CJK tokenizers installed), or an exact
    entry in that language's frequency list; returns [(zipf, lang)] sorted"""
    out = []
    for l in langs:
        f = wordfreq.word_frequency(s, l, "large" if l in LARGE else "best")
        if f > 0 or s in D[l]:
            out.append((round(math.log10(f) + 9, 2) if f > 0 else 0.0, l))
    return sorted(out, reverse=True)
LARGE = set(wordfreq.available_languages("large"))

def leet_variants(s):
    opts = [[c] + LEET.get(c, []) for c in s]
    return set("".join(p) for p in itertools.product(*opts)) - {s}

def single_token(s, tk, hf):
    hits = []
    for n, e in tk.items():
        if any(len(e.encode(v)) == 1 for v in (s, " " + s)): hits.append(n)
    for n, t in hf.items():
        if any(len(t.encode(v, add_special_tokens=False).ids) == 1 for v in (s, " " + s)): hits.append(n)
    return hits

def ham(a, b): return sum(x != y for x, y in zip(a, b))
def transposes(a, b): return any(a[:i] + a[i+1] + a[i] + a[i+2:] == b for i in range(len(a) - 1) if a[i] != a[i+1])
def safe_pair(a, b): return ham(a, b) >= 2 and not transposes(a, b)
def boundary_ok(S):
    """no transposition across a part boundary turns two parts into two other parts"""
    Sset = set(S); bad = []
    for p in S:
        for q in S:
            if p[2] == q[0]: continue
            p2, q2 = p[:2] + q[0], p[2] + q[1:]
            if p2 in Sset and q2 in Sset: bad.append((p, q, p2, q2))
    return bad

def main():
    langs, large, D, ud, nl, W, tk, hf, skel = load()
    global ALPHA
    out = []
    P = out.append
    P("SAVTEZ-2 r3 | GENERATED ASCII forms (spec v0.3_r3 s2 design principle) | generated by SAVTEZ-GENERATE_v0.3_r3.py | PROPOSALS ONLY, Nick decides")
    P(f"sources | spec/SAVTEZ-SPEC_v0.3.txt sha {sha(os.path.join(REPO, 'spec', 'SAVTEZ-SPEC_v0.3.txt'))} | spec/SAVTEZ-DICT.txt sha {sha(os.path.join(REPO, 'spec', 'SAVTEZ-DICT.txt'))}")
    P("confusable classes (Rule 0) | " + " ; ".join(f"{k}: {v}" for k, v in DROPPED.items()))
    for t, a, why in TIERS: P(f"alphabet tier {t} | {a} | {len(a)} symbols | {why}")
    P(f"data | wordfreq {wordfreq.__version__ if hasattr(wordfreq,'__version__') else ''}: {len(langs)} languages, 'large' (incl. subtitles, social media) for {len(large)}: {','.join(sorted(large))}; 'best' for the rest")
    P(f"data | Urban Dictionary headwords (mattbierner/urban-dictionary-word-list) {len(ud)} | NetLingo acronyms {len(nl)} | own acronym list {len(ACRONYMS)} | enwiki uppercase TLA page exists | en.wiktionary entry (lower or upper) | hexspeak list {len(HEXSPEAK)} | leet map {len(LEET)} letters | txtspk skeletons {len(skel)} (20k commonest words x 27 Latin-script langs, vowels removed)")
    P(f"data | tokenizers: tiktoken {', '.join(tk)} + HF {', '.join(hf)} | test: string alone and with a leading space")
    top = set()
    for l in ("en","fr","de","es","pt","it","nl","pl","tr","sv"):
        top |= set(itertools.islice(wordfreq.iter_wordlist(l, "large" if l in large else "best"), 50000))
    def leet_ok(s):
        if s in skel: return False                       # txtspk: vowel-dropped common word (e.g. txt, pls)
        for v in leet_variants(s):                         # leet de-substitution gives a common word or acronym
            if v in top or v in nl or v in ACRONYMS: return False
        return True
    def run_tier(ALPHA):
        stages = []
        S = ["".join(p) for p in itertools.product(ALPHA, repeat=3)]; stages.append(("S0 enumerate all 3-char strings over the alphabet", len(S), ""))
        def stage(name, keep, why):
            nonlocal S
            before = S; S = [s for s in S if keep(s)]
            rem = [s for s in before if s not in set(S)]
            stages.append((name, len(S), f"removed {len(rem)}" + (f", e.g. {' '.join(rem[:8])}" if rem else "")))
        stage("S1 zero frequency: wordfreq.word_frequency == 0 in all 42 languages (large lists where available) and no exact list entry", lambda s: not wf_hits(s, langs, D), "")
        stage("S2a not an acronym (own list, NetLingo, enwiki TLA page)", lambda s: s not in ACRONYMS and s not in nl and not W["enwiki_upper"].get(s.upper()), "")
        stage("S2b not slang (Urban Dictionary headword, Wiktionary entry)", lambda s: s not in ud and not W["enwiktionary_lower"].get(s) and not W["enwiktionary_upper"].get(s.upper()), "")
        stage("S2c not leetspeak / txtspk (string is a vowel-dropped skeleton of a top-20k word in 27 langs, or one leet de-substitution gives a top-50k word in 10 langs or an acronym)", leet_ok, "")
        stage("S2d not hexspeak", lambda s: s not in HEXSPEAK, "")
        stage("S3 not a single token (4 tiktoken + %d HF tokenizers)" % len(hf), lambda s: not single_token(s, tk, hf), "")
        stage("S4 no repeated character (design choice: doubled letters invite doubling/dropping and miscounts)", lambda s: len(set(s)) == 3, "")
        pool = S[:]
        # S5: typo-safe set: Damerau distance >=2 (Hamming>=2 and no adjacent transposition) + boundary-transposition safe
        def greedy_max(pool):
            chosen, rest = [], pool[:]
            while rest:
                def kills(s): return sum(1 for t in rest if t != s and not safe_pair(s, t))
                s = min(rest, key=lambda s: (kills(s), s))
                if not boundary_ok(chosen + [s]): chosen.append(s)
                rest = [t for t in rest if t != s and safe_pair(s, t)]
            return chosen
        maxset = greedy_max(pool)
        stages.append(("S5 largest typo-safe set found (greedy; pairwise Damerau>=2 + cross-boundary transposition safe)", len(maxset), f"from the {len(pool)} S4 survivors"))
        return stages, pool, maxset
    need = len(CONCEPTS) + sum(n for _, _, n in SPARES)
    results = {}
    for t, a, why in TIERS:
        results[t] = run_tier(a)
    P("stage | " + " | ".join(f"{t} survivors" for t, _, _ in TIERS))
    for i in range(len(results[TIERS[0][0]][0])):
        P(results[TIERS[0][0]][0][i][0] + " | " + " | ".join(str(results[t][0][i][1]) for t, _, _ in TIERS))
    for t, _, _ in TIERS:
        P(f"{t} removed per stage | " + " ; ".join(f"{n.split(' ')[0]}: {note}" for n, c, note in results[t][0][1:]))
    chosen_tier = next((t for t, _, _ in TIERS if len(results[t][2]) >= need), None)
    mode = "strict (Damerau>=2 + boundary-safe, plus CHECK)"
    if chosen_tier is None:
        chosen_tier = next((t for t, _, _ in TIERS if len(results[t][1]) >= need), None)
        mode = "relaxed (CHECK only; distinct forms) per spec 4 r3"
    if chosen_tier is None:
        P(f"need | {need} | no tier has enough survivors | BLOCKED"); print("\n".join(out)); sys.exit(1)
    ALPHA = dict((t, a) for t, a, _ in TIERS)[chosen_tier]
    stages, pool, maxset = results[chosen_tier]
    P(f"chosen tier | {chosen_tier} = {ALPHA} | smallest tier whose typo-safe set covers all {need} forms | selection mode {mode}")
    P(f"{chosen_tier} S4 survivors ({len(pool)}) | {' '.join(pool)}")
    P(f"{chosen_tier} S5 typo-safe set ({len(maxset)}) | {' '.join(maxset)}")
    P(f"need | {need} forms = {len(CONCEPTS)} concepts (29 word parts + 8 message acts) + 4 spares (2 for task/gaz, 2 for associated/wap) | {'OK' if len(maxset) >= need else 'NOT ENOUGH'}")
    if len(maxset) < need: maxset = pool
    # assignment: deterministic, in code-point order; prefer same-axis siblings at Hamming distance 3
    assigned = []
    avail = maxset[:]
    order = [(cp, ax, c, ph) for cp, ax, c, ph in CONCEPTS] + \
            [(cp, "SPARE", f"spare {i+1} for {ph}", ph) for ph, cp, n in SPARES for i in range(n)]
    for cp, ax, c, ph in order:
        sib = [f for (_, a2, _, _, f) in assigned if a2 == ax or (ax == "SPARE" and a2 == "HEAD")]
        def score(s):
            return (sum(1 for t in sib if ham(s, t) < 3), sum(1 for (_, _, _, _, t) in assigned if ham(s, t) == 2),
                    hashlib.sha256((c + s).encode()).hexdigest())
        s = min(avail, key=score); avail.remove(s)
        assigned.append((cp, ax, c, ph, s))
    allf = [a[4] for a in assigned]
    pair_fail = [(a, b) for a, b in itertools.combinations(allf, 2) if not safe_pair(a, b)]
    bfail = boundary_ok(allf)
    P(f"check | {len(allf)} assigned forms | pairs {len(allf)*(len(allf)-1)//2} | Damerau<2 failures {len(pair_fail)} | cross-boundary transposition collisions {len(bfail)}")
    P("code point | axis | concept | current placeholder | GENERATED ASCII form | wordfreq hits | single-token in | own-axis min Hamming")
    for cp, ax, c, ph, s in assigned:
        sib = [a[4] for a in assigned if a[1] == ax and a[4] != s]
        P(f"U+{cp:04X} | {ax} | {c} | {ph or '(TBD)'} | {s} | {len(wf_hits(s, langs, D))} | {','.join(single_token(s, tk, hf)) or 'none'} | {min((ham(s,t) for t in sib), default='-')}")
    json.dump([{"cp": cp, "axis": ax, "concept": c, "placeholder": ph, "form": s} for cp, ax, c, ph, s in assigned],
              open("/tmp/savtez_r3_generated.json", "w"), indent=0)
    # ---- screening table for the CURRENT placeholder parts ----
    P("SCREEN current CVC placeholder parts against the same pipeline (info; parts not changed)")
    P("part | chars outside the chosen confusable-free alphabet | wordfreq hits (top 3 lang:zipf) | acronym | slang | leet/txtspk | single token in (of %d) | Rule 0 verdict" % (len(tk) + len(hf)))
    for p in CURRENT:
        conf = "".join(sorted(set(p) - set(ALPHA))); wf = wf_hits(p, langs, D)
        acr = [n for n, hit in (("own", p in ACRONYMS), ("netlingo", p in nl), ("enwiki", W["enwiki_upper"].get(p.upper()))) if hit]
        sl = [n for n, hit in (("urbandict", p in ud), ("wiktionary", W["enwiktionary_lower"].get(p) or W["enwiktionary_upper"].get(p.upper()))) if hit]
        lt = "yes" if not leet_ok(p) else "no"; st = single_token(p, tk, hf)
        fails = sum([bool(conf), bool(wf), bool(acr), bool(sl), lt == "yes", bool(st)])
        P(f"{p} | {conf or '-'} | {len(wf)} langs: {', '.join(f'{l}:{z}' for z, l in wf[:3]) or '-'} | {','.join(acr) or '-'} | {','.join(sl) or '-'} | {lt} | {len(st)} | {'FAIL ' + str(fails) + '/6 tests' if fails else 'PASS'}")
    # ---- SIGIL: ASCII fallback by character-frequency check ----
    syntax = set("+~!#@|->:§ ")   # used by spec 5 message syntax (# hash, @ref, | fields, -> changes, deltas)
    cands = [c for c in map(chr, range(33, 127)) if not c.isalnum() and c not in syntax]
    corpora = {"prose (Gutenberg x8 + Wikipedia x260)": sorted(glob.glob(f"{CO}/gut_*.txt")) + sorted(glob.glob(f"{CO}/wiki_*.txt")),
               "markdown docs": [f"{CO}/markdown.txt"], "python code": [f"{CO}/pycode.txt"]}
    rates = {}
    for name, files in corpora.items():
        txt = "".join(open(f, encoding="utf-8", errors="ignore").read() for f in files)
        rates[name] = {c: txt.count(c) * 1e6 / len(txt) for c in cands}; rates[name]["_len"] = len(txt)
    ESCAPE = set("\\\"'`")   # escape/quote characters: JSON, shell and markdown rewrite or eat them in transport
    rank = sorted(cands, key=lambda c: (c in ESCAPE, max(rates[n][c] for n in corpora), rates["prose (Gutenberg x8 + Wikipedia x260)"][c]))
    P("SIGIL | ASCII fallback chosen by frequency check over printable ASCII punctuation, excluding characters spec 5 syntax already uses (" + "".join(sorted(syntax - {' '})) + " space)")
    P("char | per million chars: " + " | ".join(f"{n} ({rates[n]['_len']} chars)" for n in corpora) + " | max | escape/quote char? | o200k: alone = 1 token? | merges with next part? (o200k, '<c>kef')")
    o2 = tk["o200k_base"]
    for c in rank:
        merged = o2.decode([o2.encode(c + "kef")[0]]) != c
        P(f"{c} | " + " | ".join(f"{rates[n][c]:.1f}" for n in corpora) + f" | {max(rates[n][c] for n in corpora):.1f} | {c in ESCAPE} | {len(o2.encode(c)) == 1} | {merged}")
    P(f"SIGIL proposal | ASCII fallback '{rank[0]}' (lowest worst-case rate across prose, markdown and code, escape/quote characters excluded) | canonical PUA U+E800 (new framing block E8xx; assumption) | no variants")
    print("\n".join(out))

if __name__ == "__main__":
    main()
