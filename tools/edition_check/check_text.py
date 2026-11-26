#!/usr/bin/env python3
"""Compares the text on the ADT screens with the text of the 2026 PDF, page by page.
   python3 tools/edition_check/check_text.py <dir with pNNN.txt from `pdftotext -f N -l N`>  -> text_check.json"""
import json,re,sys,os,collections,difflib
RAW=sys.argv[1]; HERE=os.path.dirname(os.path.abspath(__file__))
texts=json.load(open('content/i18n/sq-XK/texts.json')); pages=json.load(open('content/pages.json'))
LET=re.compile(r'[^\W\d_]',re.U)
def letters(s):
    s=s.replace('­','')
    idx=[i for i,c in enumerate(s) if LET.match(c)]
    return ''.join(s[i].lower() for i in idx),idx
pdf={}
for n in range(1,130):
    raw=open(f'{RAW}/p{n:03d}.txt',encoding='utf-8',errors='replace').read()
    L,idx=letters(raw); pdf[n]=dict(raw=raw,L=L,idx=idx,cov=bytearray(len(L)))
def words(s): return re.findall(r'[^\W\d_]+',s.lower())
scr=collections.defaultdict(list)
for p in pages:
    h=open(p['href']).read(); n=int(p['section_id'][2:5])
    for i in dict.fromkeys(re.findall(r'data-id="([^"]+)"',h)):
        if re.search(r'_im\d|_fig|crop|seg\d|_map|scene|_ans_|activity',i) or re.search(r'<img[^>]*data-id="%s"'%re.escape(i),h): continue
        scr[n].append((p['section_id'],i,texts.get(i,'')))
adt_issues=[]; 
for n,items in scr.items():
    for sec,i,t in items:
        L,_=letters(t)
        if len(L)<2: continue
        hit=False
        for m in (n,n+1,n-1):
            if m in pdf:
                k=pdf[m]['L'].find(L)
                if k>=0:
                    hit=True
                    while k>=0:
                        pdf[m]['cov'][k:k+len(L)]=b'\x01'*len(L); k=pdf[m]['L'].find(L,k+1)
                    break
        if hit: continue
        # fuzzy: best matching block coverage on page n
        best=(0,n,'')
        for m in (n,n+1,n-1):
            if m not in pdf: continue
            sm=difflib.SequenceMatcher(None,L,pdf[m]['L'],autojunk=False)
            blocks=[b for b in sm.get_matching_blocks() if b.size>=6]
            c=sum(b.size for b in blocks)/len(L)
            if c>best[0]:
                a=min(b.b for b in blocks); z=max(b.b+b.size for b in blocks)
                if z-a<=len(L)*1.6+40:
                    for b in blocks: pdf[m]['cov'][b.b:b.b+b.size]=b'\x01'*b.size
                    P=pdf[m]; near=' '.join(P['raw'][P['idx'][a]:P['idx'][z-1]+1].split())
                else: near=''
                best=(c,m,near)
        adt_issues.append(dict(page=n,screen=sec,id=i,adt=t,match=round(best[0],2),pdf_near=best[2],new_id=bool(re.search(r'_x\d',i))))
pdf_issues=[]
for n,P in pdf.items():
    cov=P['cov']; k=0; N=len(cov)
    while k<N:
        if cov[k]: k+=1; continue
        j=k
        while j<N and not cov[j]: j+=1
        if j-k>=12:
            txt=' '.join(P['raw'][P['idx'][k]:P['idx'][j-1]+1].split())
            pdf_issues.append(dict(page=n,letters=j-k,pdf=txt))
        k=j
json.dump(dict(adt=adt_issues,pdf=pdf_issues),open(HERE+'/text_check.json','w'),ensure_ascii=False,indent=1)
print(len(adt_issues),'ADT strings not word-for-word in the PDF;',len(pdf_issues),'PDF passages not found in the ADT')
c=collections.Counter(('new' if a['new_id'] else 'pdf-id', 'close' if a['match']>=.8 else 'part' if a['match']>=.4 else 'none') for a in adt_issues); print(c)
print(sum(p['letters'] for p in pdf_issues), 'letters uncovered of', sum(len(P['L']) for P in pdf.values()))
