import json,re,collections,sys,os
S=os.environ.get('PAGEMAP_DIR') or os.path.dirname(os.path.abspath(__file__))
def words(s):
    s=s.replace('-\n','').lower()
    return re.findall(r'[a-zçë]+',s)
def grams(w,n=3): return {tuple(w[i:i+n]) for i in range(len(w)-n+1)}
pdfw={n:words(open(f'{S}/raw26/p{n:03d}.txt',encoding='utf-8',errors='replace').read()) for n in range(1,130)}
pdfg={n:grams(w) for n,w in pdfw.items()}
texts=json.load(open('content/i18n/sq-XK/texts.json'))
pages=json.load(open('content/pages.json'))
B2P={}
scr=[]  # (section, bundlepage, [(id,words)])
for p in pages:
    h=open(p['href']).read()
    ids=list(dict.fromkeys(re.findall(r'data-id="([^"]+)"',h)))
    b=int(p['section_id'][2:5])
    scr.append((p['section_id'],b,[(i,words(texts.get(i,''))) for i in ids if not re.search(r'_im\d|_fig|crop|seg\d',i)]))
# assign each string to a pdf page
by_page=collections.defaultdict(lambda: collections.Counter())  # pdf page -> screen -> words matched
adtg=collections.defaultdict(set)
for sec,b,items in scr:
    nominal=b
    for i,w in items:
        if len(w)<4: continue
        g=grams(w)
        best=None
        for n in range(1,130):
            sc=len(g&pdfg[n])/len(g)
            if sc>=0.5:
                d=abs(n-nominal) if nominal else 99
                key=(round(sc,1),-d)
                if best is None or key>best[0]: best=(key,n)
        if best:
            by_page[best[1]][sec]+=len(w); adtg[best[1]]|=g
allg=set()
for sec,b,items in scr:
    for i,w in items: allg|=grams(w)
rows=[]
for n in range(1,130):
    cov=len(pdfg[n]&allg)/len(pdfg[n]) if pdfg[n] else None
    rows.append({'page':n,'words':len(pdfw[n]),'coverage':cov,'screens':[s for s,_ in sorted(by_page[n].items())],'matched':dict(by_page[n])})
json.dump(rows,open(f'{S}/pagemap.json','w'),indent=1)
for r in rows: print(r['page'],r['words'],None if r['coverage'] is None else round(r['coverage'],2),' '.join(s[2:] for s in r['screens']))
