import json,re,sys
P={p['id']:p['text'] for q in json.load(open('passages.json')).values() for p in q}
def expand(inp,out):
    o=[]
    for line in open(inp):
        line=line.rstrip()
        if not line: continue
        o.append(line)
        for pid in re.findall(r'P\d+',' '.join(re.findall(r'\[([^\]]*)\]',line))):
            if pid in P: o.append(f'    SOURCE {pid}: {P[pid]}')
    open(out,'w').write('\n'.join(o))
expand(sys.argv[1],sys.argv[2])
