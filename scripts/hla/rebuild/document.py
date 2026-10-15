#!/usr/bin/env python3
"""Rebuilt HLA using the Opportunity Intelligence document composition."""
from pathlib import Path
import json,sys,hashlib,copy,re
from html import escape
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.colors import HexColor,white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics import renderPDF
ROOT=Path(__file__).resolve().parents[3]
for name,file in [('Arial','Arial.ttf'),('Arial-Bold','Arial Bold.ttf')]:pdfmetrics.registerFont(TTFont(name,'/System/Library/Fonts/Supplemental/'+file))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold')
from figures import build_all
T=HexColor('#073847');O=HexColor('#FF6529');G=HexColor('#506875');L=HexColor('#C7D4DA');P=HexColor('#EBF0F3');B=HexColor('#F6F9FA')
W,H=landscape(A4);X=36;CW=W-72;BOTTOM=H-44
ST={k:ParagraphStyle(k,fontName=font,fontSize=size,leading=lead,textColor=color,spaceAfter=0) for k,font,size,lead,color in [('body','Arial',10,14,T),('small','Arial',9,12.5,G),('cell','Arial',9.3,12.7,T),('cellhead','Arial-Bold',9.3,12,white),('head','Arial-Bold',12,15,T),('white','Arial',10,14,white),('code','Courier',8.5,11.7,T)]}
SOURCE=ROOT/'docs/hla/rebuild/content-source.json';source=json.loads(SOURCE.read_text());pages=copy.deepcopy(source['pages'])
# Reuse verified subject matter only. Every page composition and figure is new.
figs={3:'01-deployment',9:'02-target-resolution',11:'03-admission',13:'04-dispatch',14:'06-data-ownership',15:'07-recovery',16:'08-result'}
for i,n in figs.items():pages[i]['diagram']=n
pages[3]['title']='Architecture and ordered job lifecycle'
pages[3]['subtitle']='Accept and persist -> dispatch and execute -> retain and retrieve; management-host actions are explicit.'
pages[3]['caption']='Numbers identify lifecycle actions, not separate containers. The API and PostgreSQL appear again where they serve later phases. Acceptance returns a job ID; queue ACK follows READY. The worker owns remote execution and persisted outcomes. Result retrieval is a new short request.'
pages[9]['caption']='Both management PAs use the same parent endpoint. The parent retains the accepted target and mapping revision; the worker claims canonical-host ownership before using pinned SSH access. Scheduling cannot redirect the target, and aliases cannot create a second mutation owner.'
pages[11]['caption']='Parent receipt precedes publication in this recovery-relay view. Submit may publish on its fast path; the job and outbox are committed first. The relay repairs interrupted sends. Reused keys return the original job; changed input with the same key conflicts.'
pages[13]['title']='Queue dispatch and durable acknowledgement';pages[13]['subtitle']='Delivery acceptance is a short transaction; the installation runs independently.'
pages[13]['caption']='The dispatcher validates a queue reference and asks the parent to commit READY. A repeated reference returns compatible prior acceptance. Only then does Studio acknowledge the message. Delivery failures receive bounded retry or quarantine; a known installation failure belongs to the job result.'
pages.insert(14,{'title':'Remote execution and host ownership','subtitle':'A background worker runs the fixed JBPA caller against the explicitly named target.','diagram':'05-execution','caption':'The worker claims the job and canonical host, records an attempt and executes through pinned SSH access. The original attempt must remain discoverable after interruption. A resolved result is persisted; an uncertain outcome enters NEEDS_RECONCILIATION with ownership retained. Queue acknowledgements and HTTP calls do not span the installation.'})
pages[0]['subtitle']='High-Level Architecture | Customer-deployable Private Agent lifecycle management'
pages[1]['table']['rows']=[['What is being built?','Purpose, architecture and ownership','1, 3-5'],['Why these technologies?','Selections, value, reuse and target isolation','6-11'],['How is a job delivered?','Admission, publication and reusable Jitterbit operations','12-13'],['How is it executed and returned?','Dispatch, remote execution, state, recovery and retrieval','14-19'],['What are the contracts?','Persistence, queue rules, MCP and parent APIs','20-23'],['How is it controlled?','Security, target onboarding and interruption handling','24-26'],['How is the product operated?','Deployment, upgrades, observability and release gates','27-30'],['What is reusable?','Licensing, customer configuration and evidence','31-33']]
pages[-1]['subtitle']='Primary references and scoped repository evidence support the proposed design.'
# Section names support navigation and clarify the logical sequence.
def chapter(i):
 if i<=5:return '01  PRODUCT AND SYSTEM CONTEXT'
 if i<=11:return '02  TECHNOLOGY AND COMPONENT DESIGN'
 if i<=19:return '03  JOB DELIVERY AND EXECUTION'
 if i<=23:return '04  DATA AND INTERFACE CONTRACTS'
 if i<=26:return '05  SECURITY AND RECOVERY'
 if i<=30:return '06  DEPLOYMENT AND OPERATIONS'
 return '07  REUSE AND EVIDENCE'

def e(t):return escape(str(t)).replace('\n','<br/>')
def rich(t):
 t=e(t)
 for word in ['WHY:','VALUE:','REUSE:','TRADEOFF:']:t=t.replace(word,'<b>'+word+'</b>')
 return t

def paragraph(text,x,y,w,style='body',draw=True):
 p=Paragraph(text,ST[style]);_,h=p.wrap(w,2000)
 if draw:p.drawOn(c,x,H-y-h)
 return h

def box(x,y,w,h,fill=B,border=L,r=8):
 c.setFillColor(fill);c.setStrokeColor(border);c.setLineWidth(.6);c.roundRect(x,H-y-h,w,h,r,stroke=1,fill=1)

def label(text,x,y,size=9,color=G,bold=False):
 c.setFillColor(color);c.setFont('Arial-Bold' if bold else 'Arial',size);c.drawString(x,H-y,text)

def callout(text,y,title='DESIGN IMPLICATION',w=CW,x=X):
 h=paragraph(rich(text),x+15,y+31,w-30,'small',False)+44
 box(x,y,w,h,HexColor('#F4F8FA'));c.setFillColor(O);c.rect(x,H-y-h,4,h,stroke=0,fill=1)
 label(title,x+15,y+18,8,T,True);paragraph(rich(text),x+15,y+29,w-30,'small')
 return y+h+12

def header(page,i,total):
 c.setFillColor(white);c.rect(0,0,W,H,fill=1,stroke=0);c.setFillColor(O);c.rect(0,H-4,W,4,fill=1,stroke=0)
 c.drawImage(str(ROOT/'docs/hla/assets/jitterbit-logo-icon.png'),X,H-53,width=24,height=24,mask='auto',preserveAspectRatio=True)
 label('Jitterbit',X+30,49,21,T,True)
 box(W-238,29,202,25,B,L,5);label('JBPA MANAGEMENT  |  HLA 8.0',W-225,45,7.8,T,True)
 box(X,71,CW,77,HexColor('#F6F9FA'),L,9);c.setFillColor(O);c.roundRect(X,H-148,4,77,2,fill=1,stroke=0)
 label(chapter(i),X+16,88,7.4,G,True)
 # Use equal headline size unless a title genuinely requires a two-line treatment.
 title=page['title'];sz=23
 if pdfmetrics.stringWidth(title,'Arial-Bold',sz)>CW-32:sz=21
 label(title,X+16,115,sz,T,True)
 paragraph(e(page['subtitle']),X+16,125,CW-32,'small')
 c.setStrokeColor(L);c.line(X,31,W-X,31)
 label('Jitterbit  |  Proposed product architecture  |  06 October 2026',X,H-18,7,G)
 c.setFont('Arial',7);c.drawRightString(W-X,18,f'{i} / {total}')

def card_grid(items,y,columns=2):
 gap=14;w=(CW-gap*(columns-1))/columns
 for start in range(0,len(items),columns):
  group=items[start:start+columns];heights=[]
  for title,text in group:
   # Paragraph body preserves reasons and tradeoffs as separate labelled lines.
   heights.append(37+paragraph(rich(text),0,0,w-28,'small',False)+14)
  h=max(heights)
  for j,(title,text) in enumerate(group):
   x=X+j*(w+gap);box(x,y,w,h);label(title,x+14,y+22,11,T,True);paragraph(rich(text),x+14,y+37,w-28,'small')
  y+=h+12
 return y

def cover_cards(items,y):
 gap=14;w=(CW-2*gap)/3;h=124
 for j,(title,value,note) in enumerate(items):
  x=X+j*(w+gap);box(x,y,w,h)
  label(title.upper(),x+14,y+20,7.5,G,True)
  paragraph('<b>'+e(value)+'</b>',x+14,y+31,w-28,'head')
  paragraph(e(note),x+14,y+76,w-28,'small')
 return y+h+12

def cover_flow(y):
 label('REQUEST TO RESULT',X,y+8,8,G,True);y+=18
 names=['AI / MCP','APIM / Studio + MQ','Parent / PostgreSQL','Worker / JBPA','Named target / SSH']
 gap=15;w=(CW-gap*4)/5
 for j,name in enumerate(names):
  x=X+j*(w+gap);box(x,y,w,38,T,T,5)
  label(f'{j+1:02d}',x+9,y+16,7.5,HexColor('#A5BEC3'),True)
  label(name,x+9,y+29,8,white,True)
  if j<4:
   c.setStrokeColor(O);c.setLineWidth(1.2);c.line(x+w,H-y-19,x+w+gap,H-y-19)
 return y+50

def table(spec,y):
 heads=spec['headers'];rows=spec['rows'];n=len(heads)
 ratios=[.24]+[(.76/(n-1))]*(n-1)
 if n==2:ratios=[.27,.73]
 if heads==['Question','Sections','Pages']:ratios=[.27,.61,.12]
 # Column widths are semantic, not equal: short component names never steal rationale space.
 if n>=4:ratios=[.19]+[(.81/(n-1))]*(n-1)
 if spec.get('widths'):
  raw=spec['widths'];ratios=[v/sum(raw) for v in raw]
 widths=[CW*v for v in ratios]
 data=[[Paragraph(e(v),ST['cellhead'] if i==0 else ST['cell']) for v in row] for i,row in enumerate([heads]+rows)]
 t=Table(data,colWidths=widths,hAlign='LEFT');styles=[('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),T),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.45,L),('LINEBEFORE',(1,0),(-1,-1),.35,L),('BOX',(0,0),(-1,-1),.5,L)]
 for r in range(1,len(data)):
  styles.append(('BACKGROUND',(0,r),(-1,r),B if r%2 else white))
 t.setStyle(TableStyle(styles));_,h=t.wrap(CW,2000)
 t.drawOn(c,X,H-y-h);return y+h+13

def sections(specs,y):
 if len(specs)==1:return card_grid([(s['title'],s['text']) for s in specs],y,1)
 return card_grid([(s['title'],s['text']) for s in specs],y,2)

def contracts(blocks,y):
 gap=14;w=(CW-gap)/2
 for start in range(0,len(blocks),2):
  group=blocks[start:start+2];heights=[]
  for b in group:
   heights.append(40+(paragraph(rich(b['text']),0,0,w-28,'small',False) if 'semantics' in b['title'].lower() else len(b['text'].splitlines())*11.7)+14)
  h=max(heights)
  for j,b in enumerate(group):
   x=X+j*(w+gap);box(x,y,w,h,HexColor('#F6F9FA'));label(b['title'],x+14,y+23,11,T,True)
   text=b['text'];yy=y+43
   if 'semantics' in b['title'].lower():
    paragraph(rich(text),x+14,y+40,w-28,'small');continue
   for line in text.splitlines():
    if pdfmetrics.stringWidth(line,'Courier',8.5)>w-28:raise ValueError('Contract line too wide '+line)
    c.setFont('Courier',8.5);c.setFillColor(T);c.drawString(x+14,H-yy,line);yy+=11.7
  y+=h+12
 return y

out=ROOT/'output/pdf/JBPA_Management_High_Level_Architecture_v8.pdf';out.parent.mkdir(parents=True,exist_ok=True)
figures=build_all(ROOT/'output/hla/rebuild/diagrams')
c=canvas.Canvas(str(out),pagesize=(W,H),pageCompression=1);c.setTitle('JBPA Management Platform | High-Level Architecture');c.setAuthor('Jitterbit');c.setSubject('Customer-deployable management architecture - proposed design and qualification gates')
qa=[]
for i,p in enumerate(pages,1):
 header(p,i,len(pages));c.bookmarkPage(f'p{i}');c.addOutlineEntry(p['title'],f'p{i}',level=0)
 y=163
 if p.get('intro'):
  for txt in p['intro']:y+=paragraph(rich(txt),X,y,CW,'body')+9
 if p.get('cards'):
  y=cover_cards(p['cards'],y)
 if p.get('diagram'):
  d=figures[p['diagram']];scale=min(CW/d.width,340/d.height);dx=X+(CW-d.width*scale)/2
  box(X,y,CW,d.height*scale,white,L,9)
  c.saveState();c.translate(dx,H-y-d.height*scale);c.scale(scale,scale);renderPDF.draw(d,c,0,0);c.restoreState();y+=d.height*scale+10
  y+=paragraph(rich(p['caption']),X+2,y,CW-4,'small')+9
 if p.get('table'):y=table(p['table'],y)
 if p.get('blocks'):
  if 'contracts' in p['title'].lower():y=contracts(p['blocks'],y)
  else:y=card_grid([(b['title'],b['text']) for b in p['blocks']],y,2)
 if p.get('sections'):y=sections(p['sections'],y)
 if p.get('callout'):y=callout(p['callout'],y,'STATUS AND BOUNDARY' if i==1 else 'DESIGN IMPLICATION')
 if i==1:y=cover_flow(y+5)
 if p.get('references'):
  cols=3;gap=18;w=(CW-gap*2)/3;refs=p['references'];per=(len(refs)+2)//3
  for j in range(3):
   yy=y;x=X+j*(w+gap)
   for key,title,url in refs[j*per:(j+1)*per]:
    yy+=paragraph(f'<b>[{key}]</b> <a href="{escape(url)}" color="#073847">{e(title)}</a>',x,yy,w,'small')+10
  y=max(y,yy)+15
  y=table({'headers':['Evidence ID','Repository source and scope'],'widths':[105,665],'rows':[
   ['R2','docs/production-readiness.md - qualification, artifact promotion and production gates'],
   ['R3','docs/integrations/claude-code/JBPA-EXTERNAL-HANDOFF.md - fixed remote adapter contract'],
   ['R4','docs/customer-install-runbook.md - scoped install, upgrade and customer operation procedures']
  ]},y)
  y=callout('Technical content is retained from the product specification, production-readiness notes, remote integration contract and customer runbook. Presentation is rebuilt from the Opportunity Intelligence title panels, cards, tables and architecture references. Diagram sources are generated locally as native vectors.',y,'PROVENANCE')
 qa.append({'page':i,'title':p['title'],'content_bottom':round(y,2),'limit':round(BOTTOM,2),'diagram':p.get('diagram')})
 if y>BOTTOM:print('OVERFLOW',i,p['title'],round(y-BOTTOM,1))
 c.showPage()
c.save()
model={'version':'8.0','date':'06 October 2026','pages':pages};(ROOT/'docs/hla/rebuild/model.json').write_text(json.dumps(model,indent=2)+'\n');(ROOT/'output/hla/rebuild/layout.json').write_text(json.dumps(qa,indent=2)+'\n')
print('Built',out,'pages',len(pages))
if any(q['content_bottom']>BOTTOM for q in qa):raise SystemExit('Reflow required; document not ready for delivery.')
