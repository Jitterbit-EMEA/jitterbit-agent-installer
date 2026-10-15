#!/usr/bin/env python3
"""Render the branded HLA and editable SVGs from one canonical scene/model.
Uses ReportLab and Arial; no browser or external diagram service required.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json, math, hashlib, argparse
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT=Path(__file__).resolve().parents[2]
MODEL=json.loads((ROOT/'docs/hla/model.json').read_text())
ASSETS=ROOT/'docs/hla/assets'
TOK=json.loads((ASSETS/'brand-tokens.json').read_text())['brand']['colors']
TEAL=TOK['deepTeal']; ORANGE=TOK['orange']; LINE=TOK['lightBlueGrey']; LIGHT=TOK['offWhite']; GREY='#506875'
W,H=landscape(A4);M=36;CW=W-72;BOTTOM=H-48
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font-dir',type=Path,default=Path('/System/Library/Fonts/Supplemental'),help='Directory containing licensed Arial.ttf and Arial Bold.ttf')
args=parser.parse_args()
for name in ['Arial.ttf','Arial Bold.ttf']:
 if not (args.font_dir/name).is_file():parser.error(f'Missing licensed font: {args.font_dir/name}; provide --font-dir')
pdfmetrics.registerFont(TTFont('Arial',str(args.font_dir/'Arial.ttf')))
pdfmetrics.registerFont(TTFont('ArialBold',str(args.font_dir/'Arial Bold.ttf')))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='ArialBold')
ST={}
for name,size,leading,color,bold in [('body',11,15,TEAL,False),('small',9.2,12.5,GREY,False),('head',12,16,TEAL,True),('cell',10,13.2,TEAL,False),('cellhead',10,13.2,'#ffffff',True)]:
 ST[name]=ParagraphStyle(name,fontName='ArialBold' if bold else 'Arial',fontSize=size,leading=leading,textColor=HexColor(color))
QA=[]
def para(c,txt,x,y,w,style='body'):
 p=Paragraph(txt.replace('\n','<br/>'),ST[style]);_,h=p.wrap(w,1500)
 if y+h>BOTTOM+1:raise ValueError(f'Overflow page {c.getPageNumber()}: {y+h} {txt[:90]}')
 p.drawOn(c,x,H-y-h); QA.append((c.getPageNumber(),'text',x,y,w,h));return y+h

def text(c,t,x,y,size=10,color=TEAL,bold=False):
 c.setFillColor(HexColor(color));c.setFont('ArialBold' if bold else 'Arial',size);c.drawString(x,H-y,t)

def rect(c,x,y,w,h,fill=LIGHT,stroke=LINE,r=7):
 c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke));c.setLineWidth(.65);c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=1)

def background(c):
 # Restrained brand gradient, as in the reference guide.
 a=(.922,.941,.953);b=(1,1,1)
 for i in range(100):
  t=i/99;c.setFillColor(Color(*(a[k]*(1-t)+b[k]*t for k in range(3))));c.rect(W*i/100,0,W/100+1,H,fill=1,stroke=0)
 c.setFillColor(HexColor(ORANGE));c.rect(0,H-4,W,4,fill=1,stroke=0)

def header(c,page,i,total):
 background(c);c.drawImage(str(ASSETS/'jitterbit-logo-long.jpeg'),M,H-46,width=118,height=25.1,preserveAspectRatio=True)
 c.setFont('Arial',8);c.setFillColor(HexColor(GREY));c.drawRightString(W-M,H-33,'JBPA MANAGEMENT / HIGH-LEVEL ARCHITECTURE')
 text(c,f'{i:02d}  /  '+page['title'],M,85,22,TEAL,True)
 para(c,page['subtitle'],M,97,CW,'body')
 c.setStrokeColor(HexColor(ORANGE));c.setLineWidth(1.2);c.line(M,H-122,W-M,H-122)
 c.setStrokeColor(HexColor(LINE));c.setLineWidth(.6);c.line(M,32,W-M,32)
 text(c,f'Jitterbit | Proposed design v{MODEL["version"]} | {MODEL["date"]}',M,H-18,8,GREY)
 c.setFont('Arial',8);c.drawRightString(W-M,18,f'{i} / {total}')

def table(c,model,y):
 widths=model.get('widths') or [CW/len(model['headers'])]*len(model['headers'])
 widths=[v*CW/sum(widths) for v in widths]
 data=[[Paragraph(escape(str(v)),ST['cellhead']) for v in model['headers']]]
 data += [[Paragraph(escape(str(v)),ST['cell']) for v in row] for row in model['rows']]
 t=Table(data,colWidths=widths);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor(TEAL)),('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor(LIGHT)]),('LINEBELOW',(0,0),(-1,-1),.45,HexColor(LINE)),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
 _,h=t.wrap(CW,2000)
 if y+h>BOTTOM:raise ValueError(f'Table overflow p{c.getPageNumber()}: {y+h}')
 t.drawOn(c,M,H-y-h);return y+h+12

def sections(c,sections,y):
 for s in sections:
  y=para(c,escape(s['title']),M,y,CW,'head')+4
  y=para(c,escape(s['text']),M,y,CW,'body')+12
 return y

def callout(c,t,y):
 p=Paragraph(t,ST['body']);_,h=p.wrap(CW-28,1500)
 if y+h+24>BOTTOM:raise ValueError(f'Callout overflow p{c.getPageNumber()}')
 rect(c,M,y,CW,h+22);c.setFillColor(HexColor(ORANGE));c.roundRect(M,H-y-h-22,4,h+22,2,fill=1,stroke=0)
 p.drawOn(c,M+14,H-y-11-h);return y+h+32

class Scene:
 def __init__(self,w=CW,h=330):self.w=w;self.h=h;self.ops=[];self.boxes=[]
 def r(self,x,y,w,h,fill=LIGHT,stroke=LINE,r=8):self.ops.append(('rect',x,y,w,h,fill,stroke,r))
 def t(self,x,y,t,size=10,color=TEAL,bold=False,anchor='start'):
  # SVG/PDF share positions, wrapped lines and baseline metrics.
  self.ops.append(('text',x,y,t,size,color,bold,anchor))
 def wrap(self,t,w,size=10,bold=False):
  font='ArialBold' if bold else 'Arial';lines=[]
  for row in t.split('\n'):
   words=row.split();line=''
   for word in words:
    cand=(line+' '+word).strip()
    if pdfmetrics.stringWidth(cand,font,size)>w and line:lines.append(line);line=word
    else:line=cand
   lines.append(line)
  return lines
 def label(self,x,y,t,w,size=10,color=TEAL,bold=False,anchor='start'):
  lines=self.wrap(t,w,size,bold)
  for i,l in enumerate(lines):self.t(x,y+i*(size+3),l,size,color,bold,anchor)
  return len(lines)*(size+3)
 def box(self,x,y,w,h,title,body,dark=False):
  self.r(x,y,w,h,TEAL if dark else '#ffffff',ORANGE if dark else LINE)
  hh=self.label(x+12,y+22,title,w-24,11,'#ffffff' if dark else TEAL,True)
  bh=self.label(x+12,y+24+hh,body,w-24,9.8,'#ffffff' if dark else GREY)
  if 24+hh+bh>h+3:raise ValueError('Node text overflow '+title)
  self.boxes.append((x,y,w,h,title))
 def line(self,pts,color=ORANGE,dashed=False,arrow=True):self.ops.append(('line',pts,color,dashed,arrow))
 def arrowlabel(self,x,y,t,w=150):
  lines=self.wrap(t,w,9.4);h=len(lines)*12.4;self.r(x-3,y-10,w+6,h+2,'#ffffff','#ffffff',2)
  self.label(x,y,t,w,9.4,GREY)
 def export(self,path):
  parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">']
  for op in self.ops:
   if op[0]=='rect':
    _,x,y,w,h,f,s,r=op;parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{f}" stroke="{s}" stroke-width="0.7"/>')
   elif op[0]=='text':
    _,x,y,t,size,col,bold,anchor=op;parts.append(f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{"bold" if bold else "normal"}" text-anchor="{anchor}" fill="{col}">{escape(t)}</text>')
   else:
    _,pts,col,dash,arrow=op;parts.append(f'<polyline points="'+ ' '.join(f'{x},{y}' for x,y in pts)+f'" fill="none" stroke="{col}" stroke-width="1.5"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')
    if arrow:
     (x1,y1),(x,y)=pts[-2:];a=math.atan2(y-y1,x-x1);points=[(x,y),(x-6*math.cos(a-.45),y-6*math.sin(a-.45)),(x-6*math.cos(a+.45),y-6*math.sin(a+.45))];parts.append(f'<polygon points="'+ ' '.join(f'{xx},{yy}' for xx,yy in points)+f'" fill="{col}"/>')
  parts.append('</svg>');path.write_text('\n'.join(parts))
 def draw(self,c,x,y):
  for op in self.ops:
   if op[0]=='rect':
    _,xx,yy,w,h,f,s,r=op;c.setFillColor(HexColor(f));c.setStrokeColor(HexColor(s));c.setLineWidth(.7);c.roundRect(x+xx,H-y-yy-h,w,h,r,fill=1,stroke=1)
   elif op[0]=='text':
    _,xx,yy,t,size,col,bold,anchor=op;c.setFont('ArialBold' if bold else 'Arial',size);c.setFillColor(HexColor(col));method=c.drawCentredString if anchor=='middle' else c.drawRightString if anchor=='end' else c.drawString;method(x+xx,H-y-yy,t)
   else:
    _,pts,col,dash,arrow=op;c.setStrokeColor(HexColor(col));c.setLineWidth(1.5);c.setDash(5,4) if dash else c.setDash()
    for (x1,y1),(x2,y2) in zip(pts,pts[1:]):c.line(x+x1,H-y-y1,x+x2,H-y-y2)
    c.setDash()
    if arrow:
     (x1,y1),(xx,yy)=pts[-2:];a=math.atan2(yy-y1,xx-x1);p=c.beginPath();p.moveTo(x+xx,H-y-yy)
     for aa in [a-.45,a+.45]:p.lineTo(x+xx-6*math.cos(aa),H-y-yy+6*math.sin(aa))
     p.close();c.setFillColor(HexColor(col));c.drawPath(p,fill=1,stroke=0)

def solution():
 s=Scene(h=326)
 for x,w,title in [(0,120,'AI INTERFACE'),(137,215,'JITTERBIT HARMONY'),(370,265,'CUSTOMER MANAGEMENT'),(653,117,'TARGET HOSTS')]:
  s.r(x,4,w,308,LIGHT,LINE,10);s.t(x+10,23,title,8.5,TEAL,True)
 s.box(12,58,96,104,'AI client','Submit tool\nRead result')
 s.box(153,55,183,75,'MCP + APIM','Tools and protected APIs',True)
 s.box(153,171,183,86,'Studio + JBMQ','Submit / relay / dispatch\nRequest queue + DLQ',True)
 s.box(389,55,227,75,'Parent API','Accept jobs / read status')
 s.box(389,171,137,86,'JBPA worker','Fixed adapter\nNamed target / SSH')
 s.box(543,171,80,86,'DB','PostgreSQL\nJob state')
 s.box(665,171,93,106,'PA hosts','Existing SSH\nLifecycle\nEvidence')
 s.line([(108,92),(153,92)]);s.t(116,80,'MCP',8,GREY)
 s.line([(244,130),(244,171)]);s.t(254,152,'trigger',9,GREY)
 s.line([(336,208),(359,208),(359,92),(389,92)]);s.t(340,161,'HTTPS',8.6,GREY)
 s.line([(456,130),(456,171)],TEAL);s.t(466,152,'claim',9,GREY)
 s.line([(591,130),(591,171)],TEAL);s.t(552,152,'persist',9,GREY)
 s.line([(526,211),(543,211)],TEAL)
 s.line([(456,257),(456,274),(647,274),(647,211),(665,211)],TEAL);s.t(626,233,'SSH',9,GREY)
 s.t(390,290,'API / worker / database / TLS are on a dedicated host.',9.4,GREY)
 return s

def sequence(kind):
 if kind=='submission':
  names=['AI + MCP','APIM / Studio','Parent API','PostgreSQL','JBMQ'];xs=[65,225,385,545,705]
  msgs=[(0,1,'Submit target + action'),(1,2,'Create job; same request key'),(2,3,'Commit job + outbox'),(3,2,'Commit confirmed'),(2,1,'Return stable job ID'),(1,4,'Publish job reference'),(1,2,'Record publication'),(1,0,'202 + observed state')]
 elif kind=='execution':
  names=['JBMQ','Studio dispatcher','Parent / DB','Worker','Target host'];xs=[65,225,385,545,705]
  msgs=[(0,1,'Deliver job reference'),(1,2,'Accept execution'),(2,1,'READY committed'),(1,0,'ACK delivery'),(3,2,'Claim job + host'),(2,3,'Claim + attempt confirmed'),(3,4,'SSH: fixed JBPA action'),(4,3,'Structured result'),(3,2,'Persist final outcome')]
 else:
  names=['AI + MCP','APIM / Studio','Parent API','PostgreSQL'];xs=[75,275,475,675]
  msgs=[(0,1,'Get job by ID'),(1,2,'Authorized status query'),(2,3,'Read retained job'),(3,2,'State + safe result'),(2,1,'Current state/result'),(1,0,'Explain outcome')]
 s=Scene(h=342)
 for i,(name,x) in enumerate(zip(names,xs)):
  s.r(x-58,4,116,32,TEAL,TEAL,5);s.label(x,23,name,110,9.4,'#ffffff',True,'middle');s.line([(x,38),(x,333)],LINE,True,False)
 gap=31 if len(msgs)==9 else 35 if len(msgs)==8 else 45;y=61
 for n,(a,b,label) in enumerate(msgs,1):
  x1,x2=xs[a],xs[b]
  responses=({3,6,8} if kind=='execution' else {4,5,8} if kind=='submission' else {4,5,6})
  response=n in responses
  s.line([(x1,y+13),(x2,y+13)],TEAL if response else ORANGE,response,True)
  center=(x1+x2)/2;span=abs(x2-x1)-14
  # Message labels sit centered above their own arrow, never in another lane.
  lines=s.wrap(f'{n}. {label}',span,9.4)
  for j,l in enumerate(lines):s.t(center,y-2-(len(lines)-1-j)*11,l,9.4,TEAL,False,'middle')
  y+=gap
 s.t(0,340,'Solid orange = request. Dashed teal = response. Time progresses downward.',8.5,GREY)
 return s

def deployment():
 s=Scene(h=326)
 s.r(130,5,510,308,LIGHT,LINE,11);s.t(148,24,'DEDICATED LINUX MANAGEMENT HOST - COMPOSE STACK',9.4,TEAL,True)
 s.box(0,61,105,90,'Management PA','Private HTTPS\nSame parent URL',True)
 s.box(150,60,178,74,'NGINX','TLS entry :443')
 s.box(438,60,182,74,'FastAPI / Uvicorn','Internal API :8080')
 s.box(150,205,178,78,'PostgreSQL','Internal :5432\nPersistent data')
 s.box(438,205,182,78,'Python worker','Pinned JBPA + SSH\nProtected key mounts')
 s.box(665,205,105,78,'PA targets','Existing SSH\nNo new port')
 s.line([(105,96),(150,96)]);s.t(107,82,'HTTPS',8,GREY)
 s.line([(328,96),(438,96)]);s.t(350,82,'internal HTTP',9,GREY)
 s.line([(530,134),(530,169),(241,169),(241,205)],TEAL);s.t(336,160,'persist / query',9,GREY)
 s.line([(438,244),(328,244)],TEAL);s.t(351,231,'claim / result',9,GREY)
 s.line([(620,244),(665,244)],TEAL);s.t(630,231,'SSH',9,GREY)
 s.t(150,301,'Only TLS is published. DB/API ports are internal. Backups are stored off-host.',9.3,GREY)
 return s

DIAGRAMS={'solution':solution,'submission':lambda:sequence('submission'),'execution':lambda:sequence('execution'),'results':lambda:sequence('results'),'deployment':deployment}

def columns(c,blocks):
 gap=22;col=(CW-gap)/2;ys=[140,140]
 # Two blocks per column, ordered top-to-bottom within each column.
 for index,b in enumerate(blocks):
  which=index%2;x=M+which*(col+gap);y=ys[which]
  title=Paragraph(escape(b['title']),ST['head']);_,th=title.wrap(col-26,1000)
  body=Paragraph(escape(b['text']).replace('\n','<br/>'),ST['body']);_,bh=body.wrap(col-26,1000)
  hh=th+bh+30
  if y+hh>BOTTOM:raise ValueError(f'Column overflow p{c.getPageNumber()} {b["title"]} {y+hh}')
  rect(c,x,y,col,hh,'#ffffff',LINE,8);title.drawOn(c,x+13,H-y-12-th);body.drawOn(c,x+13,H-y-18-th-bh)
  ys[which]=y+hh+12

def cover(c,total):
 background(c);c.drawImage(str(ASSETS/'jitterbit-logo-long.jpeg'),M,H-94,width=174,height=37,preserveAspectRatio=True)
 text(c,'JITTERBIT PRIVATE AGENT MANAGEMENT',M,146,10,ORANGE,True)
 text(c,'Customer-deployable management platform',M,188,27,TEAL,True)
 text(c,'High-level architecture',M,225,27,TEAL,True)
 para(c,'A clear path from AI request to governed delivery, isolated execution and a durable result.',M,248,CW,'body')
 table(c,{'headers':['Purpose','Design','Reusable product'], 'rows':[['Automate Private Agent lifecycle actions on named, supported hosts.','Jitterbit MCP + APIM/Studio + JBMQ; dedicated API/worker/database.','Portable Linux containers, customer configuration, versioned release and support matrix.']]},295)
 callout(c,'<b>Proposed production architecture v2.0</b> | 06 October 2026<br/>This design guides the product build. Current runtime qualification and remaining implementation gates are explicitly recorded.',405)
 text(c,'Jitterbit brand assets and report conventions reused from the Opportunity Intelligence project.',M,508,9,GREY)
 text(c,f'JBPA Management | {total} pages',M,557,8,GREY)

def references(c,p):
 col=(CW-24)/2
 for i,(key,title,url) in enumerate(p['references']):
  which=0 if i<11 else 1;row=i if i<11 else i-11;x=M+which*(col+24);y=140+row*22
  para(c,f'<b>[{key}]</b> <a href="{escape(url)}" color="{ORANGE}">{escape(title)}</a>',x,y,col,'small')
 y=395
 y=sections(c,[{'title':'Repository and visual provenance','text':'R1: docs/jbpa-management-product.md. R2: docs/production-readiness.md. R3: docs/integrations/skills/README.md. R4: docs/customer-start-here.md. R5: tools/handoff/customer_remote.py. Visual source: jitterbit-se-opportunity-intelligence brand tokens, logo, user guide and reference architecture examples.'}],y)
 para(c,'Upstream sources were reviewed during this revision. License labels describe selected components, not every base-image dependency. Diagrams are generated as editable SVGs and drawn into the PDF from the same canonical scene. Proposed contracts and production gates remain clearly distinguished from current evidence.',M,y,CW,'small')

out=ROOT/'output/pdf/JBPA_Management_High_Level_Architecture.pdf';diagdir=ROOT/'output/hla/diagrams';diagdir.mkdir(parents=True,exist_ok=True)
c=canvas.Canvas(str(out),pagesize=landscape(A4));c.setTitle('JBPA Management Platform - High-Level Architecture v2.0');c.setAuthor('Jitterbit');c.setSubject('Customer-deployable agent lifecycle management; proposed architecture')
total=len(MODEL['pages'])
for i,p in enumerate(MODEL['pages'],1):
 c.bookmarkPage(f'p{i}');c.addOutlineEntry(p['title'],f'p{i}',0,False)
 if p['kind']=='cover':cover(c,total)
 else:
  header(c,p,i,total)
  if p['kind']=='diagram':
   scene=DIAGRAMS[p['diagram']]();scene.export(diagdir/(p['diagram']+'.svg'));scene.draw(c,M,134);para(c,p['caption'],M,134+scene.h+12,CW,'body')
  elif p['kind']=='columns':columns(c,p['blocks'])
  elif p['kind']=='references':references(c,p)
  else:
   y=140
   if p.get('table'):y=table(c,p['table'],y)
   if p.get('sections'):y=sections(c,p['sections'],y)
   if p.get('callout'):callout(c,p['callout'],y+2)
 c.showPage()
c.save()
manifest={'version':MODEL['version'],'pages':total,'pdf':str(out.relative_to(ROOT)),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'diagrams':[str(p.relative_to(ROOT)) for p in diagdir.glob('*.svg')],'brand_source':'jitterbit-se-opportunity-intelligence','status':'PROPOSED_DESIGN','visual_qa':'PENDING'}
(ROOT/'output/hla/manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
