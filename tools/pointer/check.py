import json,re,sys
P={p['id']:p['text'] for q in json.load(open('passages.json')).values() for p in q}
QUAL=['only','up to','median','often','may','at least','at low','less than','under','about','approximately','~','or so','generally','most']
def nums(t):
    t=t.replace('\\%','%').replace(',','')
    out=[]
    for m in re.finditer(r'(?<![A-Za-z\d.])(\d+(?:\.\d+)?)\s*([KMB])?(?![A-WYZa-wyz\d])',t):
        v=float(m.group(1)); u=m.group(2)
        v*= {'K':1e3,'M':1e6,'B':1e9}.get(u,1)
        out.append((m.group(0),v))
    return out
def match(v,pool,raw=None):
    d=0
    if raw:
        m=re.match(r'\d+(?:\.(\d+))?',raw.replace(',',''))
        d=len(m.group(1)) if m and m.group(1) else 0
    for w in pool:
        if abs(round(w,d)-v)<1e-9 or abs(v-w)<1e-9: return True
        if raw is None and w and abs(v-w)/abs(w)<0.051: return True
    return False
def check(path):
    flags=[]
    text=open(path).read()
    sents=re.split(r'(?<=[\.\]])\s+(?=[A-Z])',text.replace('\n',' '))
    for s in sents:
        cites=re.findall(r'[A-Z]\d+',' '.join(re.findall(r'\[([^\]]*)\]',s)))
        body=re.sub(r'\[[^\]]*\]','',s)
        if not cites: 
            if len(body.split())>4: flags.append(('NO-CITE',s.strip()))
            continue
        src=' '.join(P.get(c,'') for c in cites)
        pool=[v for _,v in nums(src)]
        for raw,v in nums(body):
            if match(v,pool,raw.strip()): continue
            der=[a/b for a in pool for b in pool if b and a!=b]+[(a/b-1)*100 for a in pool for b in pool if b and a>b]+[(1-a/b)*100 for a in pool for b in pool if b and a<b]+[a*b/100 for a in pool for b in pool]+[a-b for a in pool for b in pool]
            if match(v,der): flags.append((f'DERIVED {raw} (arithmetic ok, check relation)',s.strip()))
            else: flags.append((f'NUM {raw} not in cited',s.strip()))
        for qw in QUAL:
            if re.search(r'\b'+re.escape(qw)+r'\b',src,re.I) and not re.search(r'\b'+re.escape(qw)+r'\b',body,re.I):
                pass  # dropped-qualifier: only flag 'only','up to','at least','median'
        for qw in ['only','up to','at least','median']:
            if re.search(r'\b'+qw+r'\b',src,re.I) and not re.search(r'\b'+qw+r'\b',body,re.I) and any(n for n in nums(body)):
                flags.append((f'QUAL "{qw}" dropped?',s.strip()))
    return flags
if __name__=='__main__':
    for f in check(sys.argv[1]): print(f[0],'||',f[1][:200])
