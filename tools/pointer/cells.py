"""Turn 10-K statement pages into one sentence per table cell (code only), plus prose lines for the freezer.
Usage: python3 cells.py -> store_raw.json"""
import json, re, pdfplumber
R = {json.loads(l)["financebench_id"]: json.loads(l) for l in open("fb.jsonl")}
Q = ["financebench_id_02987", "financebench_id_06655", "financebench_id_10130", "financebench_id_04103",
     "financebench_id_05915", "financebench_id_03856"]
NUM = r"\(?\$?\s?-?[\d,]+(?:\.\d+)?\)?%?|—|-"
VAL = re.compile(r"(?:(?<=\s)|^)(\$\s*)?(\(?[\d,]+(?:\.\d+)?\)?%?|—)(?=\s|$)")
YEAR = re.compile(r"\b(19|20)\d{2}\b")

def unit_of(text):
    m = re.search(r"\((?:[Ii]n|[Aa]mounts in|[Dd]ollars in) (thousands|millions|billions)", text)
    return m.group(1) if m else None

def split_line(line):
    toks = line.split()
    vals = []
    while toks:
        t = toks[-1]
        if re.fullmatch(r"\$", t):
            toks.pop(); continue
        if re.fullmatch(r"\(\$?[\d,]*\d(?:\.\d+)?\)%?|\$?[\d,]*\d(?:\.\d+)?%?|—|\$?—", t) and not (re.fullmatch(r"(19|20)\d{2}", t) and not vals and len(toks) < 3):
            vals.insert(0, t.replace("$", "")); toks.pop()
        else:
            break
    return " ".join(toks).rstrip(" $"), vals

def page_cells(text, company, doc, page):
    unit = unit_of(text) or "units as stated"
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    title = next((l for l in lines[:6] if l.isupper() and len(l) > 12 and "TABLE OF CONTENTS" not in l.upper()), "")
    years, section, cells, prose, infeasible = None, "", [], [], []
    for l in lines:
        ys = YEAR.findall(l)
        yrs = re.findall(r"\b(?:19|20)\d{2}\b", l)
        label, vals = split_line(l)
        if len(yrs) >= 2 and (not label or len(re.sub(r"[^A-Za-z]", "", label)) < 40) and all(re.fullmatch(r"(19|20)\d{2}", v) for v in vals or ["2000"]):
            years = yrs; continue
        if vals and label and years:
            if len(vals) != len(years):
                infeasible.append({"line": l, "reason": f"{len(vals)} values vs {len(years)} year columns"}); continue
            full = f"{section} {label}".strip() if section and not label.lower().startswith("total") else label
            for y, v in zip(years, vals):
                cells.append({"text": f"{company} {doc.split('_')[1]} 10-K, {title.title() or 'statement'}, {full}, {y}: {v} ({unit})",
                              "row": full, "year": y, "value": v, "page": page})
            continue
        if not vals and l.endswith(":"):
            section = l.rstrip(":"); continue
        if not vals and re.search(r"[a-z].*\.$", l) and len(l.split()) > 6:
            prose.append({"text": l, "page": page})
    return cells, prose, infeasible

out = {}
for q in Q:
    r = R[q]; pdf = pdfplumber.open(f"pdfs/{r['doc_name']}.pdf")
    ev = sorted({int(e["evidence_page_num"]) for e in r["evidence"]})
    pages = sorted({p + d for p in ev for d in (-1, 0, 1) if 0 <= p + d < len(pdf.pages)})
    allc, allp, inf = [], [], []
    for p in pages:
        c, pr, i = page_cells(pdf.pages[p].extract_text() or "", r["company"], r["doc_name"], p)
        allc += c; allp += pr; inf += [dict(x, page=p) for x in i]
    out[q] = {"doc": r["doc_name"], "question": r["question"], "answer": r["answer"], "justification": r["justification"],
              "evidence_pages": ev, "pages": pages, "cells": allc, "prose": allp, "infeasible": inf}
    print(q, r["doc_name"], "pages", pages, "cells", len(allc), "prose", len(allp), "infeasible", len(inf))
json.dump(out, open("store_raw.json", "w"), indent=1, ensure_ascii=False)
