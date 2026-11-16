"""v3 relay (v2 + fixes from the v2 run): validate an agent's hop output, keep the ledger, render the next hop's input or the final brief.
Usage: python3 relay.py Q k      (reads Q_v2_h{k}.raw, writes Q_v2_h{k}.txt and, at k=5, Q_v2_final.txt)"""
import json, re, sys
q, k = sys.argv[1], int(sys.argv[2])
store = json.load(open("store.json"))[q]
TEXT = {i: v["text"] for i, v in store.items()}
REASONS = {"off-topic", "duplicate", "background", "superseded"}
NAME = re.compile(r"\b(?:[A-Za-z]*\d[A-Za-z0-9]*|[A-Z]{2,}[A-Za-z0-9-]*|[A-Z][a-z]+[A-Z][A-Za-z]*)\b|(?<=[a-z,;] )[A-Z][a-z]+\b")
ids_of = lambda s: re.findall(r"F\d+", " ".join(re.findall(r"\[([^\]]*)\]", s)))

def prev_live():
    if k == 1:
        return set(TEXT)
    return set(json.load(open(f"{q}_v2_h{k-1}.state.json"))["live"])

lines, log = [], {"rejected": [], "bad_format": [], "silent_drops": [], "unknown_ids": []}
fact_ids, judge_ids, drops = [], set(), {}
for raw in open(f"{q}_v2_h{k}.raw"):
    s = raw.strip().lstrip("-*• ").strip()
    if not s:
        continue
    m = re.match(r"^FACT\s*\[?(F\d+)\]?\s*$", s, re.I)
    if m:
        fid = m.group(1)
        if fid not in TEXT: log["unknown_ids"].append(fid); continue
        if fid not in fact_ids: fact_ids.append(fid); lines.append(("FACT", fid))
        continue
    m = re.match(r"^DROP\s*\[?(F\d+)\]?\s*[:\-–]?\s*(.*)$", s, re.I)
    if m:
        fid, why = m.group(1), m.group(2).strip().lower()
        why = next((r for r in REASONS if r in why), None)
        if why is None: log["bad_format"].append(s); continue
        drops[fid] = why; continue
    m = re.match(r"^JUDGE\s*:?\s*(.*)$", s, re.I)
    if m:
        body = m.group(1); cited = ids_of(body)
        bad = [c for c in cited if c not in TEXT]
        free = re.sub(r"\[[^\]]*\]", " ", body)
        backing = " ".join(TEXT[c] for c in cited if c in TEXT)
        names = [n for n in NAME.findall(free) if n and n not in ("I",)]
        unbacked = [n for n in names if n.lower() not in backing.lower()]
        free_nb = free
        for n in names:
            if n not in unbacked: free_nb = re.sub(r"\b" + re.escape(n) + r"\b", " ", free_nb)
        if re.search(r"\d", free_nb) or unbacked or bad or not cited:
            log["rejected"].append({"line": s, "digits": bool(re.search(r"\d", free_nb)), "unbacked_names": unbacked,
                                    "no_cite": not cited, "unknown": bad})
            continue
        judge_ids |= set(cited); lines.append(("JUDGE", body))
        continue
    log["bad_format"].append(s)

for fid in list(drops):
    if fid in fact_ids or fid in judge_ids:
        log["bad_format"].append(f"DROP and cite of {fid} at one hop; drop ignored"); del drops[fid]
rej_ids = set(c for r in log["rejected"] for c in ids_of(r["line"]))
prev_drops = {} if k == 1 else json.load(open(f"{q}_v2_h{k-1}.state.json")).get("all_drops", {})
all_drops = dict(prev_drops); all_drops.update({f: f"{w} (hop {k})" for f, w in drops.items()})
before = prev_live()
live = (set(fact_ids) | judge_ids) & set(TEXT)
log["lost_by_rejection"] = []
for fid in sorted(before - live - set(drops), key=lambda x: int(x[1:])):
    (log["lost_by_rejection"] if fid in rej_ids else log["silent_drops"]).append(fid)
if log["rejected"]:
    open(f"{q}_v2_h{k}.returns.txt", "w").write("These lines were rejected by code; fix each once and resubmit the whole output:\n" +
        "\n".join(f"{r['line']}  || digits outside slots: {r['digits']}; names not in cited facts: {r['unbacked_names']}; no citation: {r['no_cite']}; unknown IDs: {r['unknown']}" for r in log["rejected"]))
json.dump({"live": sorted(live, key=lambda x: int(x[1:])), "drops": drops, "all_drops": all_drops, "log": log}, open(f"{q}_v2_h{k}.state.json", "w"), indent=1)

# next hop input: facts rendered by code, judgments as written
out = []
for kind, x in lines:
    out.append(f"{x}: {TEXT[x]}" if kind == "FACT" else f"JUDGE: {x}")
extra = [i for i in sorted(judge_ids, key=lambda x: int(x[1:])) if i in TEXT and i not in fact_ids]
if extra:
    out.append("")
    out.append("Facts cited in JUDGE lines (rendered by code):")
    out += [f"{i}: {TEXT[i]}" for i in extra]
if all_drops:
    out.append("")
    out.append("Dropped earlier in the chain (still in the source store; do not claim the source lacks them):")
    out += [f"{f}: {w}: {TEXT[f]}" for f, w in sorted(all_drops.items(), key=lambda x: int(x[0][1:]))]
open(f"{q}_v2_h{k}.txt", "w").write("\n".join(out) + "\n")
if k == 5:
    brief, shown = [], set()
    for kind, x in lines:
        if kind == "FACT":
            if x not in shown: brief.append(TEXT[x].replace("[verbatim] ", "")); shown.add(x)
        else:
            for c in ids_of(x):
                if c in TEXT and c not in shown: brief.append(TEXT[c].replace("[verbatim] ", "")); shown.add(c)
            brief.append(re.sub(r"\s*\[[^\]]*\]", "", x).strip())
    open(f"{q}_v2_final.txt", "w").write(" ".join(brief) + "\n")
print(q, k, "facts", len(fact_ids), "judge", sum(1 for l in lines if l[0] == "JUDGE"), "drops", len(drops),
      "rejected", len(log["rejected"]), "bad", len(log["bad_format"]), "silent", len(log["silent_drops"]), "lost_by_rejection", len(log["lost_by_rejection"]), "unknown", len(log["unknown_ids"]))
