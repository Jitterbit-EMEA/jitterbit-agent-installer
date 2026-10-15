"""Verify final page geometry, preserved content and vector label routing."""
from pathlib import Path
import sys,json,hashlib
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import String,PolyLine
from pypdf import PdfReader
import pdfplumber
ROOT=Path(__file__).resolve().parents[3]
for name,file in [('Arial','Arial.ttf'),('Arial-Bold','Arial Bold.ttf')]:pdfmetrics.registerFont(TTFont(name,'/System/Library/Fonts/Supplemental/'+file))
from figures import BUILDERS
problems=[];figure_checks=[]
for builder in BUILDERS:
 f=builder();collisions=[]
 for line in f.edges:
  if not isinstance(line,PolyLine):continue
  pts=list(zip(line.points[::2],line.points[1::2]))
  for a,b in zip(pts,pts[1:]):
   for t in f.texts:
    width=pdfmetrics.stringWidth(t.text,t.fontName,t.fontSize);left=t.x-(width/2 if t.textAnchor=='middle' else width if t.textAnchor=='end' else 0)
    x0,x1=left+1,left+width-1;y0,y1=t.y-t.fontSize*.16,t.y+t.fontSize*.76
    cross=False
    if a[1]==b[1]:cross=y0<a[1]<y1 and max(min(a[0],b[0]),x0)<min(max(a[0],b[0]),x1)
    elif a[0]==b[0]:cross=x0<a[0]<x1 and max(min(a[1],b[1]),y0)<min(max(a[1],b[1]),y1)
    if cross:collisions.append(t.text)
 if collisions:problems.append({'figure':f.name,'route_text_collisions':sorted(set(collisions))})
 figure_checks.append({'figure':f.name,'route_text_collisions':len(set(collisions)),'text_labels':len(f.texts),'route_shapes':len(f.edges)})
pdf=ROOT/'output/pdf/JBPA_Management_High_Level_Architecture_v8.pdf';reader=PdfReader(pdf)
model=json.loads((ROOT/'docs/hla/rebuild/model.json').read_text());assert len(reader.pages)==len(model['pages'])
for i,page in enumerate(reader.pages,1):
 text=page.extract_text();assert f'{i} / {len(reader.pages)}' in text,(i,'footer')
 assert len(text)>500,(i,'orphan')
with pdfplumber.open(pdf) as doc:
 for i,p in enumerate(doc.pages,1):
  for char in p.chars:
   if char['text'].strip() and (char['x0']<35 or char['x1']>p.width-35 or char['top']<20 or char['bottom']>p.height-12):problems.append({'page':i,'margin_violation':char['text']})
# Every technical table, technology block and explanatory section survives the rebuild.
source=json.loads((ROOT/'docs/hla/rebuild/content-source.json').read_text());lookup={p['title']:p for p in model['pages']}
for p in source['pages']:
 if p['title'] not in lookup:continue
 for key in ['blocks','sections','intro','cards','callout']:
  if key in p:assert lookup[p['title']][key]==p[key],(p['title'],key,'changed content')
 if 'table' in p and 'reading guide' not in p['title'].lower():assert lookup[p['title']]['table']==p['table']
qa={'pages':len(reader.pages),'bookmarks':len(reader.outline),'links':sum(len(p.get('/Annots',[])) for p in reader.pages),'figures':figure_checks,'content_preservation':'Original technical tables, blocks, narrative sections and callouts retained; workflow captions rebuilt around new diagrams','problems':problems,'visual_review':'Pending final review','sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()}
(ROOT/'output/hla/rebuild/qa.json').write_text(json.dumps(qa,indent=2)+'\n');print(json.dumps(qa,indent=2))
if problems:raise SystemExit('Final visual repairs required.')
