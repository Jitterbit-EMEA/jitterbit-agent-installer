#!/usr/bin/env python3
"""Structured engineering SVGs: fixed grids, explicit ports, orthogonal routes."""
from pathlib import Path
from html import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import json,math
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'output/hla/diagrams'
OUT.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('Arial','/System/Library/Fonts/Supplemental/Arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialBold','/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
T='#073847';O='#FF6529';G='#58727E';L='#C7D4DA';P='#F5F8FA'
class Drawing:
 def __init__(self,name,h=520):self.name=name;self.h=h;self.parts=[];self.nodes=[];self.routes=[]
 def rect(self,x,y,w,h,fill='white',stroke=L,r=3,dash=False):self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"'+(' stroke-dasharray="6 4"' if dash else '')+'/>')
 def txt(self,x,y,s,size=15,color=T,bold=False,anchor='start'):
  self.parts.append(f'<text x="{x}" y="{y}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" fill="{color}">{escape(s)}</text>')
 def wrap(self,s,w,size=15,bold=False):
  out=[]
  for line in s.split('\n'):
   a=''
   for word in line.split():
    b=(a+' '+word).strip()
    if a and pdfmetrics.stringWidth(b,'ArialBold' if bold else 'Arial',size)>w:out.append(a);a=word
    else:a=b
   out.append(a)
  return out
 def lines(self,x,y,items,w,size=14.5,color=G,bold=False):
  yy=y
  for item in items:
   for line in self.wrap(item,w,size,bold):self.txt(x,yy,line,size,color,bold);yy+=19
  return yy
 def zone(self,x,y,w,h,title,sub=''):
  self.rect(x,y,w,h,'white',L,4);self.parts.append(f'<line x1="{x}" y1="{y+38}" x2="{x+w}" y2="{y+38}" stroke="{L}"/>');self.txt(x+13,y+25,title,15,T,True)
  if sub:self.txt(x+13,y+h-12,sub,13,G)
 def node(self,id,x,y,title,items,w=200,h=96,jb=False,entity=False):
  self.rect(x,y,w,h,'white',T if jb else L,3)
  self.parts.append(f'<rect x="{x}" y="{y}" width="4" height="{h}" fill="{O if jb else T}"/>')
  self.txt(x+14,y+23,title,16.5,T,True)
  end=self.lines(x+14,y+45,items,w-28,14.5,G)
  if end-19>y+h-9:raise ValueError('Node overflow '+id)
  self.nodes.append({'id':id,'x':x,'y':y,'width':w,'height':h})
 def edge(self,pts,label=None,labelpos=None,dash=False,color=O,number=None):
  self.parts.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in pts)+f'" fill="none" stroke="{color}" stroke-width="1.8"'+(' stroke-dasharray="5 4"' if dash else '')+f' marker-end="url(#{"teal" if color==T else "orange"})"/>')
  if label and labelpos:
   x,y=labelpos;lines=self.wrap(label,160,13)
   for i,s in enumerate(lines):self.txt(x,y+16*i,s,13,G)
  if number:
   x,y=pts[0];self.rect(x-9,y-9,18,18,'white',color,9);self.txt(x,y+4,str(number),11,T,True,'middle')
  self.routes.append(pts)
 def note(self,x,y,title,lines,w=300):
  self.txt(x,y,title,15,T,True);self.lines(x,y+24,lines,w,14.5,G)
 def export(self):
  for n in self.nodes:
   assert n['x']>=0 and n['y']>=0 and n['x']+n['width']<=1100 and n['y']+n['height']<=self.h,n
  svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 {self.h}" role="img" aria-label="{self.name}"><defs>'
  for id,c in [('orange',O),('teal',T)]:svg+=f'<marker id="{self.name}-{id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="{c}"/></marker>'
  svg+='</defs>'+''.join(self.parts).replace('url(#teal)',f'url(#{self.name}-teal)').replace('url(#orange)',f'url(#{self.name}-orange)')+'</svg>'
  (OUT/(self.name+'.svg')).write_text(svg)
  return {'diagram':self.name,'canvas':[1100,self.h],'nodes':self.nodes,'routes':len(self.routes),'minimum_label_size':13}
qa=[]
# 1. Runtime deployment and trust boundaries.
s=Drawing('deployment-topology',520)
s.zone(5,5,250,495,'JITTERBIT CONTROL PLANE')
s.zone(295,5,500,495,'DEDICATED MANAGEMENT HOST','API / DB ports remain internal; no privileged containers')
s.zone(830,5,265,495,'TARGET HOST BOUNDARY','Existing SSH; no new listening service')
for id,y,title,body in [('mcp',55,'MCP server',['Tool catalog + schemas','Client authentication']),('apim',165,'API Manager',['POST jobs / GET status','Protected API facade']),('studio',275,'Studio operations',['Submit / relay / dispatch','Management PA group']),('mq',385,'JBMQ',['Requests + delivery DLQ','Get / ACK / NACK'])]:s.node(id,30,y,title,body,jb=True)
s.node('proxy',325,105,'NGINX',['Inbound HTTPS :443','TLS / request limits'])
s.node('api',560,105,'FastAPI / Uvicorn',['Internal API :8080','Authorize + persist jobs'])
s.node('worker',325,295,'Python worker',['Pinned JBPA caller','SSH identities only here'])
s.node('db',560,295,'PostgreSQL',['Internal DB :5432','Jobs / outbox / results'])
s.node('host-contract',865,105,'Host access contract',['Canonical host identity','Pinned key + login'])
s.node('target',865,295,'Named target VM',['SSH + fixed sudo contract','PA services + evidence'])
s.edge([(130,151),(130,165)],color=T);s.edge([(130,261),(130,275)],color=T)
s.edge([(165,371),(165,385)],color=T);s.edge([(90,385),(90,371)],color=T)
s.edge([(230,323),(275,323),(275,153),(325,153)],'TLS\n:443',(264,215))
s.edge([(525,153),(560,153)])
s.edge([(660,201),(660,295)],'DB :5432',(672,255),color=T)
s.edge([(525,343),(560,343)],color=T)
s.edge([(425,391),(425,432),(845,432),(845,343),(865,343)],'SSH / pinned host key',(612,422),color=T)
s.edge([(965,201),(965,295)],'Validated access',(977,255),dash=True,color=T)
qa.append(s.export())
# 2. Admission, transaction and publication recovery.
s=Drawing('admission-outbox',520)
s.txt(25,24,'ADMISSION: BUSINESS REQUEST -> DURABLE JOB ID',15,T,True)
items=[('request',30,'APIM / Studio',['target / action / version','Idempotency-Key']),('validate',245,'Validate request',['Caller + target scope','Canonical request hash']),('parent',460,'Parent API',['POST /v1/jobs','Create or retrieve job']),('commit',675,'PG transaction',['Job + outbox atomically','Pending dispatch']),('accept',890,'Accepted reference',['jobId + observed state','No install-success claim'])]
for id,x,t,b in items:s.node(id,x,60,t,b,w=180)
for i in range(4):s.edge([(210+215*i,108),(245+215*i,108)],number=i+1)
s.txt(25,268,'PUBLICATION AND RECOVERY',15,T,True)
s.node('receipt',30,310,'Client receipt',['202 / jobId / state','Later status tool call'],w=180)
s.node('binding',245,310,'Idempotency guard',['Same key -> same job','Changed request -> 409'],w=180)
s.node('relay',460,310,'Studio outbox relay',['Claim pending reference','Retry interrupted send'],w=180,jb=True)
s.node('publish',675,310,'Studio publish',['jobId / schemaVersion','Confirm publication'],w=180,jb=True)
s.node('queue',890,310,'JBMQ requests',['Reference; no secrets','Dispatch is independent'],w=180,jb=True)
s.edge([(335,156),(335,310)],'Unique binding',(348,229),dash=True,color=T)
s.edge([(765,156),(765,310)],'Durable outbox',(778,230),color=T)
s.edge([(640,358),(675,358)],dash=True)
s.edge([(855,358),(890,358)])
s.edge([(1070,108),(1086,108),(1086,465),(120,465),(120,406)],'Return accepted job',(810,454),dash=True,color=T)
s.note(30,494,'Queue ACK is not installation success.',[],700)
qa.append(s.export())
# 3. Explicit dispatch + independent SSH protocol, fixed lane geometry.
s=Drawing('execution-protocol',520);xs=[70,260,450,640,830,1020]
roles=[('Studio','JBMQ consumer'),('JBMQ','Reference delivery'),('Parent API','Execution acceptance'),('PostgreSQL','Durable authority'),('Worker','Job / host owner'),('Target VM','Fixed JBPA action')]
for x,(a,b) in zip(xs,roles):
 s.txt(x,23,a,16,T,True,'middle');s.txt(x,43,b,12.5,G,False,'middle')
 s.parts.append(f'<line x1="{x}" y1="58" x2="{x}" y2="475" stroke="{L}" stroke-dasharray="3 5"/>')
s.rect(5,60,1090,23,P,P,0);s.txt(17,77,'A  DISPATCH ACCEPTANCE - short calls; ACK only after the database commit',13,T,True)
msgs=[(0,1,'Get reference'),(1,0,'jobId'),(0,2,'POST /dispatch'),(2,3,'Commit READY'),(3,2,'READY durable'),(2,0,'Accepted / existing'),(0,1,'ACK after commit')]
for k,(a,b,t) in enumerate(msgs):
 y=102+k*27;s.edge([(xs[a],y),(xs[b],y)],dash=k in [1,4,5],color=T,number=k+1);s.txt((xs[a]+xs[b])/2,y-8,t,13.5,T,False,'middle')
s.rect(5,300,1090,23,P,P,0);s.txt(17,317,'B  REMOTE EXECUTION - independent of the original MCP / HTTP request',13,T,True)
for k,(a,b,t) in enumerate([(4,3,'Claim job + host'),(3,4,'Ownership + attempt'),(4,5,'SSH fixed action'),(5,4,'Result + evidence'),(4,3,'Commit outcome')]):
 y=346+k*28;s.edge([(xs[a],y),(xs[b],y)],dash=k in [1,3],color=T,number=k+8);s.txt((xs[a]+xs[b])/2,y-8,t,13.5,T,False,'middle')
s.txt(17,503,'Uncertain outcome -> NEEDS_RECONCILIATION. Retain host ownership; inspect the original attempt before replay.',14,T,True)
qa.append(s.export())
# 4. Proposed data ownership and cardinalities.
s=Drawing('job-data-ownership',520)
s.zone(370,5,710,235,'ATOMIC ACCEPTANCE BOUNDARY: job + publication outbox')
s.node('input',20,90,'Business request',['caller / deployment scope','target / action / version','idempotency key + hash'],w=280,h=125)
s.node('jobs',410,70,'jobs',['PK job_id','UQ caller_scope + key','request_hash (immutable)','target_id / canonical_host','state / attempt_id','pinned_release / result_ref'],w=250,h=155)
s.node('outbox',790,70,'dispatch_outbox',['FK job_id (one job)','claim / delivery attempt','publication confirmation'],w=270,h=125)
s.node('owner',20,320,'host_execution_ownership',['PK canonical_host_id','FK active_job + attempt','worker / lease / reconcile'],w=280,h=125)
s.node('events',790,320,'job_events + audit',['FK job_id; ordered sequence','attempt / transition / time','sanitized decision evidence'],w=270,h=125)
s.edge([(300,150),(355,150),(355,148),(410,148)],'Validate',(318,137),color=T)
s.edge([(660,128),(790,128)],'1 : 1',(713,116),color=T)
s.edge([(660,184),(720,184),(720,382),(790,382)],'1 : many',(731,290),color=T)
s.edge([(300,382),(355,382),(355,195),(410,195)],'1 active mutation',(30,302),color=T)
s.note(410,305,'Execution-state contract',['ACCEPTED_PENDING_DISPATCH -> READY','RUNNING -> verified terminal outcome','Unknown -> NEEDS_RECONCILIATION'],270)
s.txt(20,496,'Short DB transactions establish ownership. A lease expiry does not establish that the remote process stopped.',14,T,True)
qa.append(s.export())
# 5. Recovery decision, evidence and target fencing.
s=Drawing('recovery-control',510)
s.node('failure',25,140,'Interrupted attempt',['SSH / worker / DB loss','jobId + original attempt','Remote may continue'],h=125)
s.node('observe',300,140,'Observe original state',['Read result + process','Package + service state','Expected Harmony identity'],h=125)
s.parts.append(f'<polygon points="680,124 795,202 680,280 565,202" fill="white" stroke="{T}" stroke-width="1.4"/>')
s.txt(680,193,'Original outcome',16,T,True,'middle');s.txt(680,216,'resolved?',16,T,True,'middle')
s.node('resolved',865,140,'Resolved outcome',['SUCCEEDED or FAILED','Persist verified evidence','Then release ownership'],h=125)
s.node('hold',580,345,'Reconciliation',['Keep host ownership','Keep original attempt ID','No blind mutation replay'],h=125)
s.edge([(225,202),(300,202)],color=T)
s.edge([(500,202),(565,202)],color=T)
s.edge([(795,202),(865,202)],'Yes',(813,191),color=T)
s.edge([(680,280),(680,345)],'No',(692,320),color=T)
s.edge([(580,407),(540,407),(540,305),(400,305),(400,265)],'Re-check evidence',(411,294),dash=True,color=T)
s.note(25,345,'Safety invariants',['Timeout is not proof of no change.','Lease expiry is not replay permission.','Reinstall and Harmony deletion','remain separately authorized.'],420)
qa.append(s.export())
# 6. Fleet resolution is independent of management PA scheduling.
s=Drawing('fleet-target-resolution',520)
s.zone(5,5,260,495,'MANAGEMENT AGENT GROUP')
s.node('pa-a',35,95,'Management PA A',['Runs a Studio operation','Same central API URL'],jb=True)
s.node('pa-b',35,305,'Management PA B',['Runs a Studio operation','Same central API URL'],jb=True)
s.node('parent',345,200,'Parent job service',['targetId + inventory rev','Caller + action scope','Persistent job identity'],h=125)
s.node('inventory',615,70,'Inventory revision',['qa-pa-03 -> canonical VM-003','Pinned endpoint / host key','SSH identity reference'],w=250,h=125)
s.node('worker',615,295,'Worker resolves target',['Recorded mapping revision','Canonical host lock','Fixed JBPA caller'],w=250,h=125)
s.node('target',905,295,'VM-003',['Existing SSH','Agent lifecycle','Original result evidence'],w=175,h=125)
s.edge([(235,143),(285,143),(285,245),(345,245)],color=T)
s.edge([(235,353),(285,353),(285,280),(345,280)],color=T)
s.edge([(545,263),(580,263),(580,357),(615,357)],'Stored job',(552,251),color=T)
s.edge([(740,295),(740,195)],'Resolve / pin',(753,249),color=T)
s.edge([(865,357),(905,357)],color=T)
s.txt(345,464,'The management PA is the execution agent, not the selected lifecycle target.',14,T,True)
s.txt(345,488,'Aliases converge on canonical host ownership; accepted jobs cannot silently change hosts.',14,G)
qa.append(s.export())
# 7. Retained result retrieval and safe response projection.
s=Drawing('result-boundary',510)
for id,x,title,body in [('client',10,'AI / user',['Retained jobId','New status request']),('tool',230,'MCP tool',['jbpa_get_job','Structured arguments']),('facade',450,'APIM / Studio',['Protected status API','Private parent call']),('parent',670,'Parent API',['GET /v1/jobs/{id}','Authorize permitted job']),('db',890,'PostgreSQL',['Retained state / outcome','Authoritative job record'])]:s.node(id,x,80,title,body,w=200)
for i in range(4):s.edge([(210+220*i,128),(230+220*i,128)],color=T)
s.node('dto',670,300,'Safe result contract',['jobId / target / action / state','requested + resolved version','sanitized outcome / evidence ID','No secrets or unrestricted logs'],w=420,h=155)
s.edge([(770,176),(770,300)],'Project permitted result',(782,245),color=T)
s.edge([(670,378),(600,378),(600,225),(110,225),(110,176)],'Same response path',(140,213),dash=True,color=T)
s.note(10,310,'Client behavior',['RUNNING / pending: retrieve later.','Terminal: explain validated outcome.','Unknown ID: return not-found.','No polling support: user asks later.'],570)
s.txt(10,490,'Result retrieval neither consumes the delivery queue nor resumes the original completed MCP call.',14,T,True)
qa.append(s.export())
(ROOT/'output/hla/engineering-diagram-qa.json').write_text(json.dumps(qa,indent=2))
print('Created seven technical engineering diagrams')
