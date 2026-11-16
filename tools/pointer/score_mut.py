import json, re, sys, collections
K=json.load(open('mut_key_SEALED.json'))
C={x['id']:bool(x['flags']) for x in json.load(open('mut_fc_out.json'))}
def load(fn):
    R={}
    for l in open(fn):
        m=re.match(r"\s*(M\d{3})\s*\|.*ok:\s*(yes|no)",l,re.I)
        if m: R[m.group(1)]=(m.group(2).lower()=='no')
    return R
H=load('haiku_mut_out.txt'); G=load(sys.argv[1]) if len(sys.argv)>1 else {}
print('parsed haiku',len(H),'grok',len(G))
types=['comparative','hedge','referent','agency','scope']
for t in types+['control']:
    ids=[i for i in K if K[i]['type']==t]
    c=sum(C[i] for i in ids); h=sum(H.get(i,False) for i in ids); g=sum(G.get(i,False) for i in ids) if G else None
    hm=sum((not C[i]) and (not H.get(i,False)) for i in ids)
    allm=sum((not C[i]) and (not H.get(i,False)) and (not G.get(i,False)) for i in ids) if G else None
    hg=sum((not H.get(i,False)) and (not G.get(i,False)) for i in ids) if G else None
    print(f"{t:12s} n={len(ids)} code={c} haiku={h} grok={g} | missed by code+haiku={hm} | both models miss={hg} | all three miss={allm}")
