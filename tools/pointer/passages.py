import re, json, sys
L = open('book.txt').read().split('\n')
SECS = {"Q1": (1604, 1743), "Q2": (2588, 2814), "Q3": (2818, 2977), "Q4": (2977, 3132)}
HDR = re.compile(r'^(\d+ Chapter \d+: .*|\d+(\.\d+)+ .* \d+)$')
def fix(t):
    t = re.sub(r'(?<![A-Za-z])fi (?=[a-z])', 'fi', t)
    t = re.sub(r'(?<=[a-z])fi (?=[a-z])', 'fi', t)
    t = re.sub(r'(?<=[a-z])fl (?=[a-z])|(?<![A-Za-z])fl (?=[a-z])', 'fl', t)
    return t
out = {}
pid = 0
for q, (a, b) in SECS.items():
    paras, cur = [], ''
    for line in L[a-1:b-1]:
        s = line.rstrip('\n')
        if not s.strip() or HDR.match(s.strip()):
            continue
        cur += s
        if not s.endswith(' '):
            paras.append(fix(cur.strip())); cur = ''
    if cur.strip(): paras.append(fix(cur.strip()))
    # merge very short lines (headings, bullets stay separate but join tiny fragments)
    res = []
    for p in paras:
        pid += 1
        res.append({"id": f"P{pid}", "text": p})
    out[q] = res
json.dump(out, open('passages.json', 'w'), indent=0)
for q in out: print(q, len(out[q]), sum(len(p['text']) for p in out[q]))
