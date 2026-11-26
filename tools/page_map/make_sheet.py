import json,re,glob,os,collections
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
S=os.environ.get('PAGEMAP_DIR') or os.path.dirname(os.path.abspath(__file__))
rows=json.load(open(S+'/pagemap.json'))
texts=json.load(open('content/i18n/sq-XK/texts.json'))
pages=json.load(open('content/pages.json'))
order=[p['section_id'] for p in pages]; num={p['section_id']:p.get('page_number') for p in pages}
title={}
for f in glob.glob('tools/specs/*.json'):
    for s in json.load(open(f)).get('screens',[]):
        title[s['id']]=' '.join(texts.get(s.get('title',''),'').split())
P2B={}
PICT={9:'pg008_sec001',11:'pg010_sec001',57:'pg056_sec001',113:'pg112_sec001',121:'pg120_sec001',123:'pg122_sec001'}
L=[10,12,16,19,21,23,25,27,29,31,33,35,37,39,41,43,45,47,49,51,53,55,57,59,63,65,67,70,73,76,79,81,83,85,88,93,95,97,99,102,105,107,109,111,113,115,117,121,123,125,128,131,133,135]
out=[]; inv=collections.defaultdict(list)
for r in rows:
    n=r['page']; b=P2B.get(n,n)
    scr={s for s,c in r['matched'].items() if c>=12}
    scr|={s for s in order if int(s[2:5])==b}
    note=''
    if n in PICT:
        scr.add(PICT[n]); note=f'Full-page picture belonging to the lesson that starts on page {n-1}; in the ADT the picture is on the first screen of that lesson.'
    if n==2: note='Blank page in the PDF (inside cover).'
    if n==127: note='Second page of the self-check questions; in the ADT they continue on the same screen as page 126.'
    scr=sorted(scr,key=order.index)
    t=next((title[s] for s in scr if title.get(s)),'') or {1:'Kopertina (cover)',3:'Përmbajtja (contents)',4:'Përmbajtja (contents, continued)'}.get(n,'')
    labels=sorted({num[s] for s in scr if num.get(s)})
    idx=[order.index(s)+1 for s in scr]; rng=[]
    for i in idx:
        if rng and i==rng[-1][1]+1: rng[-1][1]=i
        else: rng.append([i,i])
    slides=', '.join(str(a) if a==b_ else f'{a}–{b_}' for a,b_ in rng)
    for s_ in scr: inv[s_].append(n)
    out.append([n,t,'Blank page' if n==2 else ('Yes' if scr else 'NO'),slides,', '.join(s+'.html' for s in scr),', '.join(map(str,labels)),'Yes' if n in L else '',note])
json.dump(out,open(S+'/sheetrows.json','w'),ensure_ascii=False)
wb=Workbook(); ws=wb.active; ws.title='PDF to ADT map'
F='Arial'; thin=Side(style='thin',color='D0D0D0'); B=Border(left=thin,right=thin,top=thin,bottom=thin)
def head(ws,cols,widths):
    ws.append(cols)
    for i,c in enumerate(ws[1]):
        c.font=Font(name=F,bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='1F4E78'); c.alignment=Alignment(wrap_text=True,vertical='center'); c.border=B
        ws.column_dimensions[c.column_letter].width=widths[i]
    ws.row_dimensions[1].height=34; ws.freeze_panes='A2'
head(ws,['Print page (2026 edition)','Lesson (title in the ADT)','In the ADT?','ADT slide numbers (left column of the reader\'s page list)','ADT screen files','"Printo faqen" label shown in the reader','On the reported "missing" list?','Note'],[10,38,11,16,62,14,14,70])
for o in out:
    ws.append(o)
    for c in ws[ws.max_row]:
        c.font=Font(name=F); c.alignment=Alignment(wrap_text=True,vertical='top'); c.border=B
    if o[6]:
        for c in ws[ws.max_row]: c.fill=PatternFill('solid',fgColor='FFF2CC')
ws.auto_filter.ref=ws.dimensions
wA=wb.create_sheet('ADT slide to print page')
head(wA,['ADT slide number','Screen file','Lesson','"Printo faqen" label shown in the reader','Print / PDF page(s) whose content is on this slide','Label matches?'],[10,24,38,16,22,40])
for i,sid in enumerate(order):
    real=sorted(inv.get(sid,[])); lab=num.get(sid)
    if lab is None: ok='No label shown'
    elif lab in real: ok='Yes' if len(real)==1 else 'Yes (slide also carries content of page '+', '.join(str(x) for x in real if x!=lab)+')'
    else: ok='NO: label says %s, content is print page %s'%(lab,', '.join(map(str,real)))
    wA.append([i+1,sid+'.html',title.get(sid,''),lab,', '.join(map(str,real)),ok])
    for c in wA[wA.max_row]:
        c.font=Font(name=F); c.alignment=Alignment(wrap_text=True,vertical='top'); c.border=B
        if ok.startswith('NO'): c.fill=PatternFill('solid',fgColor='F8CBAD')
wA.auto_filter.ref=wA.dimensions
w2=wb.create_sheet('Reported pages')
head(w2,['Reported page','Exists in the PDF?','In the ADT?','ADT slide numbers','Screen files','Lesson','Note'],[10,12,11,16,62,38,70])
by={o[0]:o for o in out}
for n in L:
    o=by.get(n)
    w2.append([n,'Yes',o[2],o[3],o[4],o[1],o[7]] if o else [n,'No','—','','','','The 2026 PDF has 129 pages (the 2024 one 128), so there is no such page in this book.'])
    for c in w2[w2.max_row]:
        c.font=Font(name=F); c.alignment=Alignment(wrap_text=True,vertical='top'); c.border=B
w3=wb.create_sheet('How to read this')
notes=['Book: Shoqëria dhe Mjedisi 4 (source PDF: the 2026 edition, Shoqeria dhe mjedisi 4 Baze.pdf, 129 pages). Printed page numbers equal PDF page numbers.',
'ADT slide number = the position of the screen in the reader, i.e. the number in the left column of the page list (Lista e faqeve). The "Printo faqen N" label on the right of that list is the print page the reader claims for the slide.',
'Each PDF page is split into one or more ADT screens (story, questions, key points, activity). Screen files are named pgNNN_secXXX.html, where NNN is the ADT page number.',
'The mapping was made automatically by matching the text of each PDF page against the text on every ADT screen (three-word sequences), plus the picture identifiers for the six pages that are only a picture.',
'The ADT text follows the 2026 edition. The 2024 edition (128 pages) differs: pages 84–91 are in another order, there is no glossary page, and the references are on page 128.',
'Rows highlighted in yellow on the first sheet are the pages that were reported as missing.',
'Mapping generated on 2026-11-25 from the current state of the bundle.']
for t in notes: w3.append([t])
w3.column_dimensions['A'].width=140
for r in w3.iter_rows():
    for c in r: c.font=Font(name=F); c.alignment=Alignment(wrap_text=True,vertical='top')
wb.save('tools/page_map/PDF-to-ADT-page-map.xlsx')
print(collections.Counter(o[2] for o in out)); print([o[0] for o in out if not o[1]]); 

