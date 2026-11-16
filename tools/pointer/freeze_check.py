"""Code checks on frozen sentences (outside checker 2a): closed-list diff vs span, and word provenance vs window.
Usage: python3 freeze_check.py items.json out.json   items: [{"id","frozen","span","window_text"}]"""
import json, re, sys
import spacy
nlp = spacy.load("en_core_web_sm")

HEDGE = ["in practice", "generally", "often", "usually", "typically", "may", "might", "could", "up to", "only", "at least",
         "at most", "about", "approximately", "~", "roughly", "likely", "especially", "nearly", "almost", "rarely",
         "sometimes", "somewhat", "moderately", "highly", "can", "slightly", "mostly", "primarily", "potentially"]
NEG = ["not", "no", "never", "n't", "without", "none", "nothing", "cannot"]
COMP_WORDS = ["more", "less", "fewer", "most", "least", "twice", "half", "double", "same", "higher", "lower", "faster",
              "slower", "larger", "smaller", "better", "worse", "best", "worst", "highest", "lowest", "first", "only"]
QUANT = ["some", "all", "most", "every", "each", "many", "few", "any", "both"]
UNIT = r"(teraflops|petaflops|flops|tb/s|gb/s|gb|tb|percent|%|bits?|bytes?|tokens?|x|k|b|m|seconds?|ms|years?)"

def low(t): return t.lower().replace("’", "'")

def phrases(text, lst):
    t = " " + re.sub(r"[^a-z0-9~'/% ]", " ", low(text)) + " "
    out = []
    for w in lst:
        pat = r"(?<![a-z])" + re.escape(w) + r"(?![a-z])" if w != "~" else re.escape(w)
        n = len(re.findall(pat, low(text)))
        out += [w] * n
    return out

def numbers(text):
    t = low(text)
    res = []
    for m in re.finditer(r"(\d[\d,]*\.?\d*)\s*-?\s*" + UNIT + r"?(?![a-z])", t):
        v = m.group(1).replace(",", "").rstrip(".")
        res.append((v, (m.group(2) or "")))
    return res

WORDNUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
           "ten": "10", "twice": "2x", "half": "0.5x", "thousands": "thousands", "hundreds": "hundreds"}

def entities(text):
    return set(re.findall(r"\b(?:[A-Z][A-Za-z0-9]*\d[A-Za-z0-9]*|[A-Z]{2,}[A-Za-z0-9-]*|[A-Z][a-z]+[A-Z][A-Za-z]*)\b", text))

def comps(doc):
    out = [t.lower_ for t in doc if t.tag_ in ("JJR", "JJS", "RBR", "RBS")]
    out += [w for w in phrases(doc.text, COMP_WORDS) if w not in out]
    return sorted(out)

def det_flips(span_doc, fr_doc):
    flips = []
    sd = {}
    for t in span_doc:
        if t.lower_ in ("a", "an", "the") and t.head.pos_ in ("NOUN", "PROPN"):
            sd.setdefault(t.head.lemma_.lower(), set()).add("the" if t.lower_ == "the" else "a")
    for t in fr_doc:
        if t.lower_ in ("a", "an", "the") and t.head.pos_ in ("NOUN", "PROPN"):
            k = t.head.lemma_.lower(); d = "the" if t.lower_ == "the" else "a"
            if k in sd and d not in sd[k]:
                flips.append(f"{'/'.join(sd[k])}->{d} {k}")
    return flips

def multiset_diff(a, b):
    a = list(a); b = list(b); lost = []
    for x in a:
        if x in b: b.remove(x)
        else: lost.append(x)
    return lost, b  # lost from a, added in b

STOP_LEM = {"be", "have", "do", "say", "use", "make", "include", "describe", "state", "note", "refer", "call", "mean",
            "book", "source", "section", "chapter", "text", "following"}

def check(it):
    span, fr, win = it["span"], it["frozen"], it["window_text"]
    sd, fd, wd = nlp(span), nlp(fr), nlp(win)
    flags = []
    # numbers: every number in span must survive; numbers in frozen must be in window
    sn, fn, wn = [n for n, _ in numbers(span)], [n for n, _ in numbers(fr)], [n for n, _ in numbers(win)]
    lost, added = multiset_diff(sn, fn)
    if lost: flags.append(("number_lost", lost))
    nw = [x for x in added if x not in wn]
    if nw: flags.append(("number_not_in_window", nw))
    su = sorted(u for _, u in numbers(span) if u); fu = sorted(u for _, u in numbers(fr) if u)
    l2, a2 = multiset_diff(su, fu)
    if l2 or a2: flags.append(("unit_change", {"lost": l2, "added": a2}))
    for name, lst in (("hedge", HEDGE), ("negation", NEG), ("quantifier", QUANT)):
        l, a = multiset_diff(phrases(span, lst), phrases(fr, lst))
        if l: flags.append((name + "_lost", l))
        a = [x for x in a if x not in phrases(win, lst)]
        if a: flags.append((name + "_added", a))
    l, a = multiset_diff(comps(sd), comps(fd))
    if l: flags.append(("comparative_lost", l))
    a = [x for x in a if x not in comps(wd)]
    if a: flags.append(("comparative_added", a))
    df = det_flips(sd, fd)
    if df: flags.append(("determiner_flip", df))
    se, fe, we = entities(span), entities(fr), entities(win)
    if se - fe: flags.append(("entity_lost", sorted(se - fe)))
    if fe - we: flags.append(("entity_not_in_window", sorted(fe - we)))
    # provenance: content lemmas of frozen must occur in window (lemma or surface)
    wl = {t.lemma_.lower() for t in wd} | {t.lower_ for t in wd}
    noprov = [t.text for t in fd if t.pos_ in ("NOUN", "VERB", "ADJ", "ADV", "PROPN", "NUM") and not t.is_stop
              and t.lemma_.lower() not in wl and t.lower_ not in wl and t.lemma_.lower() not in STOP_LEM
              and t.lower_ not in WORDNUM and not re.fullmatch(r"[\W\d]+", t.text)]
    if noprov: flags.append(("no_provenance", noprov))
    return flags

if __name__ == "__main__":
    items = json.load(open(sys.argv[1]))
    out = [{"id": it["id"], "flags": check(it)} for it in items]
    json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
    print(len(out), "items,", sum(1 for o in out if o["flags"]), "flagged")
