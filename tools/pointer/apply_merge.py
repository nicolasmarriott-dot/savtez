"""Apply the model merge to spans.json -> spans_v1.json. Code verifies the model never changed text."""
import json, re, random
S = json.load(open("spans.json"))
M = json.load(open("merge_out.json"))
by = {s["id"]: s for s in S["spans"]}
bad = []
new = []
mp = {m["id"]: m for m in M.get("flagged", [])}
for s in S["spans"]:
    m = mp.get(s["id"])
    if not m:
        new.append(s); continue
    pcs = m.get("pieces") or [s["text"]]
    if "".join(pcs) != s["text"]:
        bad.append(("text_changed", s["id"])); new.append(s); continue
    sa = m.get("scope_add", {}) or {}
    for k, pc in enumerate(pcs):
        t = dict(s); t["text"] = pc
        if len(pcs) > 1:
            t["id"] = s["id"].replace(f".{S['source_hash']}", f"{chr(97+k)}.{S['source_hash']}")
        t["scope"] = list(s.get("scope", [])) + list(sa.get(str(k), []))
        if m.get("fact_count"): t["fact_count"] = m["fact_count"]
        if m.get("note"): t["merge_note"] = m["note"]
        t["merged"] = True
        new.append(t)
# tables -> cell facts
cells = []
for tb in M.get("tables", []):
    blk = [b for b in S["tables"] if b["block"] == tb["block"]][0]
    alltext = " ".join(blk["rows"])
    hdr = tb.get("header", [])
    for h in hdr:
        if h not in alltext: bad.append(("header_not_substring", tb["block"], h))
    for r in tb.get("rows", []):
        r2 = [" ".join(c) if isinstance(c, list) else c for c in r]
        for c in r:
            for part in (c if isinstance(c, list) else [c]):
                if part not in alltext: bad.append(("cell_not_substring", tb["block"], part))
        if len(r2) != len(hdr):
            bad.append(("cell_count", tb["block"], r2)); continue
        for j in range(1, len(r2)):
            cells.append({"id": f"{tb['block']}.{r2[0]}.{j}.{S['source_hash']}", "pid": "+".join(blk["pids"]), "type": "cell",
                          "text": f"{r2[0]} | {hdr[j]}: {r2[j]}", "row": r2[0], "header": hdr[j], "value": r2[j]})
S["spans"] = new + cells
S["merge_problems"] = bad
json.dump(S, open("spans_v1.json", "w"), indent=1, ensure_ascii=False)
facts = [s for s in new if s["type"] == "fact"]
print("facts", len(facts), "cells", len(cells), "problems", len(bad))
for b in bad: print(b)
