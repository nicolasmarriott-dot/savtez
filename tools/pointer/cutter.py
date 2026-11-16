"""Savtez span cutter v0 (code only). Input passages.json -> spans.json.
Full partition: every character of the normalized text is in exactly one span (fact, glue, heading, table_raw, list_lead).
"""
import json, re, hashlib, sys
import spacy

nlp = spacy.load("en_core_web_sm")
D = json.load(open("passages.json"))

SCOPE = ["in practice", "generally", "often", "usually", "typically", "may", "might", "could", "up to", "only",
         "at least", "at most", "about", "approximately", "~", "roughly", "most", "some", "likely", "especially",
         "around", "nearly", "almost", "not", "no", "never", "rarely", "sometimes", "at low batch", "somewhat",
         "moderately", "highly", "least", "can"]
GLUE_LEAD = re.compile(r"^(However|Instead|For example|That said|Additionally|Also|Remember that|Then|Again|But|And|So)\b,?\s*", re.I)
REFER = re.compile(r"\b(this|these|that|those|it|its|they|their|them|such|the former|the latter|that approach|these layers|this limitation|this is why)\b", re.I)
CONTRAST_MARK = {"while", "although", "whereas", "though"}

def norm_passages():
    """Normalize: drop soft-hyphen control chars, rejoin words split across passages. Keep map to original IDs."""
    out = []
    for q in D:
        for p in D[q]:
            out.append({"q": q, "ids": [p["id"]], "text": p["text"].replace("\x02", "")})
    merged = []
    for p in out:
        if merged and re.search(r"[a-z]-$", merged[-1]["text"]) and re.match(r"^[a-z]", p["text"]) and merged[-1]["q"] == p["q"]:
            merged[-1]["text"] = merged[-1]["text"][:-1] + p["text"]
            merged[-1]["ids"] += p["ids"]
        else:
            merged.append(p)
    return merged

def kind(t):
    if re.match(r"^\d+(\.\d+)+ \S", t) and not t.endswith("."):
        return "heading"
    if re.match(r"^(•|\d+\. )", t):
        return "item"
    if t.endswith(":"):
        return "lead"
    if not re.search(r"[.!?:”\"]$", t) and not t.startswith("Figure"):
        return "tableish"
    return "prose"

def scope_hits(text):
    hits = []
    low = text.lower()
    for w in SCOPE:
        pat = r"(?<![a-z])" + re.escape(w) + r"(?![a-z])" if w != "~" else re.escape(w)
        for m in re.finditer(pat, low):
            hits.append((m.start(), m.end(), w))
    # drop shorter hits contained in longer ones
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    res, last = [], -1
    for h in hits:
        if h[0] >= last:
            res.append(h); last = h[1]
    return res

def clause_cuts(sent):
    """Return char offsets (relative to sentence start) where the sentence is cut, with relation labels."""
    cuts = []
    s0 = sent.start_char
    for tok in sent:
        # coordinated finite clause with its own subject: cut before the coordinator
        if tok.dep_ == "conj" and tok.pos_ in ("VERB", "AUX") and any(c.dep_ in ("nsubj", "nsubjpass", "expl") for c in tok.children):
            cc = [c for c in tok.head.children if c.dep_ == "cc" and c.i < tok.i]
            punct = [c for c in tok.head.children if c.dep_ == "punct" and c.i < tok.i and (not cc or c.i < cc[-1].i)]
            start_tok = punct[-1] if punct else (cc[-1] if cc else None)
            if start_tok is not None:
                rel = "contrast" if cc and cc[-1].lower_ in ("but", "yet") else "and"
                cuts.append((start_tok.idx - s0 + (1 if start_tok.dep_ == "punct" else 0), rel))
        # concessive subordinate clause
        if tok.dep_ == "advcl" and any(c.dep_ == "mark" and c.lower_ in CONTRAST_MARK for c in tok.children):
            sub = sorted(tok.subtree, key=lambda t: t.i)
            a, b = sub[0].idx - s0, sub[-1].idx + len(sub[-1].text) - s0
            if a == 0:
                cuts.append((b + (1 if sent.text[b:b+1] == "," else 0), "concession"))
            else:
                cuts.append((a, "concession"))
    return sorted(set(cuts))

def finite_preds(doc_span):
    n = 0
    for t in doc_span:
        if t.pos_ in ("VERB", "AUX") and t.dep_ in ("ROOT", "conj", "ccomp", "advcl", "parataxis", "relcl", "acl") and (
                "Fin" in t.morph.get("VerbForm") or any(c.dep_ in ("nsubj", "nsubjpass") for c in t.children)):
            n += 1
    return n

def coord_args(doc_span):
    for t in doc_span:
        if t.dep_ in ("nsubj", "nsubjpass", "dobj", "attr", "pobj") and t.pos_ in ("NOUN", "PROPN") and \
                any(c.dep_ == "conj" and c.pos_ in ("NOUN", "PROPN") for c in t.children):
            return True
    return False

def has_subject(doc_span):
    if any(t.dep_ in ("nsubj", "nsubjpass", "expl", "csubj") for t in doc_span):
        return True
    first = [t for t in doc_span if not t.is_punct]
    if first and first[0].tag_ == "VB":  # imperative
        return True
    return False

def main():
    ps = norm_passages()
    src = "\n".join(p["text"] for p in ps)
    shash = hashlib.sha256(src.encode()).hexdigest()[:8]
    spans, edges, blocks = [], [], []
    i = 0
    while i < len(ps):
        p = ps[i]; t = p["text"]; k = kind(t); pid = "+".join(p["ids"])
        def add(text, typ, **kw):
            sid = f"{pid}.{sum(1 for s in spans if s['pid'] == pid)}.{shash}"
            spans.append({"id": sid, "pid": pid, "q": p["q"], "type": typ, "text": text, **kw})
            return sid
        if k == "heading":
            add(t, "heading"); i += 1; continue
        if k == "tableish":
            # gather consecutive tableish passages into one table block; header binding done by the model step
            j = i
            while j < len(ps) and kind(ps[j]["text"]) == "tableish" and ps[j]["q"] == p["q"]:
                j += 1
            if j - i >= 2:
                blk = {"block": f"T{len(blocks)}", "pids": [x for pp in ps[i:j] for x in pp["ids"]], "rows": [pp["text"] for pp in ps[i:j]]}
                blocks.append(blk)
                for pp in ps[i:j]:
                    spans.append({"id": f"{'+'.join(pp['ids'])}.0.{shash}", "pid": "+".join(pp["ids"]), "q": pp["q"], "type": "table_raw", "text": pp["text"], "block": blk["block"]})
                i = j; continue
        if k == "lead" and i + 1 < len(ps) and kind(ps[i+1]["text"]) == "item":
            j = i + 1
            while j < len(ps) and kind(ps[j]["text"]) == "item":
                j += 1
            items = ps[i+1:j]
            ordered = bool(re.match(r"^\d+\. ", items[0]["text"]))
            lead_sid = add(t, "list_lead")
            item_sids = []
            for it in items:
                it_pid = "+".join(it["ids"])
                d = nlp(it["text"])
                sid = f"{it_pid}.0.{shash}"
                spans.append({"id": sid, "pid": it_pid, "q": it["q"], "type": "fact", "text": it["text"], "list": lead_sid,
                              "flags": flags_for(d[:], it["text"]), "scope": [h[2] for h in scope_hits(it["text"])], "context": t})
                item_sids.append(sid)
            if ordered:
                edges.append({"rel": "ordered_list", "lead": lead_sid, "items": item_sids})
            else:
                edges.append({"rel": "list", "lead": lead_sid, "items": item_sids})
            i = j; continue
        # prose (also stray items / leads / single tableish lines)
        doc = nlp(t)
        prev_sent_text = None
        for sent in doc.sents:
            stext = sent.text
            cuts = clause_cuts(sent)
            bounds = [0] + [c for c, _ in cuts] + [len(stext)]
            rels = [r for _, r in cuts]
            pieces = []
            for a, b in zip(bounds, bounds[1:]):
                if b > a:
                    pieces.append((a, b))
            # sentence-initial scope adverbial: scope words before the first subject apply to every piece
            subj = [tk for tk in sent if tk.dep_ in ("nsubj", "nsubjpass", "expl")]
            first_subj = (subj[0].idx - sent.start_char) if subj else 0
            sent_scope = [h for h in scope_hits(stext) if h[1] <= first_subj]
            piece_ids = []
            for (a, b) in pieces:
                ptext = stext[a:b]
                m = GLUE_LEAD.match(ptext)
                glue = None
                if m and m.end() < len(ptext):
                    glue = ptext[:m.end()]; ptext_f = ptext[m.end():]
                else:
                    ptext_f = ptext
                if glue:
                    add(glue, "glue", sent=stext)
                own = [h[2] for h in scope_hits(ptext_f)]
                inherited = [h[2] for h in sent_scope if not (a <= h[0] and h[1] <= b)] if len(pieces) > 1 else []
                d = doc.char_span(sent.start_char + b - len(ptext_f), sent.start_char + b, alignment_mode="expand")
                fl = flags_for(d, ptext_f)
                ctx = prev_sent_text if fl.get("refer") else None
                sid = add(ptext_f, "fact", scope=own + inherited, scope_inherited=inherited, flags=fl, context=ctx)
                piece_ids.append(sid)
            for k2, r in enumerate(rels):
                if k2 + 1 < len(piece_ids):
                    edges.append({"rel": r, "a": piece_ids[k2], "b": piece_ids[k2 + 1]})
            # sentence-level contrast with previous sentence
            if re.match(r"^(However|But|Instead|Yet)\b", stext) and prev_sent_text:
                edges.append({"rel": "contrast_prev_sentence", "b": piece_ids[0] if piece_ids else None})
            prev_sent_text = stext
        i += 1
    # partition check: concatenation of span texts (whitespace-insensitive) equals source
    cat = re.sub(r"\s+", "", "".join(s["text"] for s in spans))
    srcn = re.sub(r"\s+", "", "".join(p["text"] for p in ps))
    json.dump({"source_hash": shash, "spans": spans, "edges": edges, "tables": blocks, "partition_ok": cat == srcn},
              open("spans.json", "w"), indent=1, ensure_ascii=False)
    facts = [s for s in spans if s["type"] == "fact"]
    print("partition_ok", cat == srcn, "spans", len(spans), "facts", len(facts), "tables", len(blocks),
          "edges", len(edges))
    for f in ("multi_pred", "coord", "no_subject", "refer"):
        print(f, sum(1 for s in facts if s["flags"].get(f)))

def flags_for(d, text):
    fl = {}
    if d is None:
        return {"parse_fail": True}
    if finite_preds(d) >= 2: fl["multi_pred"] = True
    if coord_args(d): fl["coord"] = True
    if not has_subject(d): fl["no_subject"] = True
    if REFER.search(text): fl["refer"] = True
    return fl

if __name__ == "__main__":
    main()
