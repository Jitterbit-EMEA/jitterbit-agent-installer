"""Native vector engineering figures for the rebuilt HLA; no legacy geometry."""
from reportlab.graphics.shapes import Drawing, Rect, String, Line, PolyLine, Polygon, Circle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.colors import HexColor
from reportlab.graphics import renderSVG
from pathlib import Path
T='#073847';O='#FF6529';G='#506875';L='#C7D4DA';P='#EBF0F3';W='#FFFFFF';C='#E7F2F2';A='#FFF3EB'
class Figure:
 def __init__(self,name,h=540):self.name=name;self.w=1160;self.h=h;self.d=Drawing(self.w,h);self.edges=[];self.nodes=[];self.texts=[]
 def rect(self,x,y,w,h,fill=W,stroke=L,r=8):
  self.nodes.append(Rect(x,self.h-y-h,w,h,rx=r,ry=r,fillColor=HexColor(fill),strokeColor=HexColor(stroke),strokeWidth=1))
 def txt(self,x,y,t,size=14,color=T,bold=False,anchor='start',layer=None):
  shape=String(x,self.h-y,t,fontName='Arial-Bold' if bold else 'Arial',fontSize=size,fillColor=HexColor(color),textAnchor=anchor)
  (layer if layer is not None else self.texts).append(shape)
 def wrap(self,t,width,size=14,bold=False):
  lines=[]
  for line in t.split('\n'):
   s=''
   for word in line.split():
    n=(s+' '+word).strip()
    if s and stringWidth(n,'Arial-Bold' if bold else 'Arial',size)>width:lines.append(s);s=word
    else:s=n
   lines.append(s)
  return lines
 def body(self,x,y,t,w,size=14,color=G,bold=False,leading=19):
  lines=self.wrap(t,w,size,bold)
  for i,line in enumerate(lines):self.txt(x,y+i*leading,line,size,color,bold)
  return y+len(lines)*leading
 def zone(self,x,y,w,h,kicker,title,fill=P):
  self.rect(x,y,w,h,fill,L,10);self.txt(x+16,y+24,kicker,11,G,True);self.txt(x+16,y+48,title,17,T,True)
 def node(self,x,y,w,h,title,body,kind='service',num=None):
  dark=kind=='jb';fill=T if dark else C if kind=='target' else W
  self.rect(x,y,w,h,fill,O if dark else L,7)
  if num:self.nodes.append(Circle(x+19,self.h-y-20,10,fillColor=HexColor(O if dark else T),strokeColor=None));self.txt(x+19,y+24,str(num),11,W,True,'middle')
  tx=x+14+(26 if num else 0)
  ts,bs,tl,bl=(13.5,11.5,16,14.5) if h<=75 else (15,12.5,18,17)
  end=self.body(tx,y+24,title,w-(tx-x)-12,ts,W if dark else T,True,tl)
  end=self.body(x+14,end+3,body,w-28,bs,W if dark else G,False,bl)
  if end-bl>y+h-9:raise ValueError(f'Node content overflow: {title} {end} > {y+h}')
 def edge(self,pts,label=None,pos=None,dashed=False,teal=False):
  color=T if teal else O
  points=[]
  for x,y in pts:points.extend([x,self.h-y])
  self.edges.append(PolyLine(points,strokeColor=HexColor(color),strokeWidth=2,strokeDashArray=[5,4] if dashed else None))
  x,y=pts[-1];px,py=pts[-2];dx=x-px;dy=y-py;length=(dx*dx+dy*dy)**.5;ux=dx/length;uy=dy/length
  self.edges.append(Polygon([x,self.h-y,x-8*ux+4*uy,self.h-(y-8*uy-4*ux),x-8*ux-4*uy,self.h-(y-8*uy+4*ux)],fillColor=HexColor(color),strokeColor=None))
  if label and pos:self.body(pos[0],pos[1],label,pos[2] if len(pos)>2 else 180,12,G)
 def banner(self,kicker,text,y=478):
  self.rect(18,y,1124,44,T,T,7);self.txt(34,y+17,kicker,10.5,'#A5BEC3',True);self.txt(34,y+34,text,13,W)
 def finish(self,out):
  # Zone backgrounds are inserted before routes. Nodes conceal connector ends cleanly.
  for shape in self.nodes:self.d.add(shape)
  for shape in self.edges:self.d.add(shape)
  for shape in self.texts:self.d.add(shape)
  out.mkdir(parents=True,exist_ok=True);renderSVG.drawToFile(self.d,str(out/(self.name+'.svg')))
  return self.d

def topology():
 f=Figure('01-deployment')
 for args in [(18,20,232,430,'01  EXPERIENCE','AI client',P),(266,20,232,430,'02  HARMONY','Jitterbit control plane',A),(514,20,370,430,'03  MANAGEMENT HOST','Customer Linux containers',P),(900,20,242,430,'04  TARGET FLEET','Named Private Agent VMs',C)]:f.zone(*args)
 f.node(36,102,196,95,'MCP client','Discovers permitted tools\nSubmit job / retrieve result',num=1)
 f.node(284,102,196,95,'MCP server','Tool schemas + descriptions\nAuthenticated REST backend','jb',2)
 f.node(284,234,196,95,'APIM + Studio','API policy / submit operation\nRelay and dispatch operations','jb',3)
 f.node(284,358,196,70,'JBMQ','Durable job-reference delivery','jb',4)
 f.node(536,102,150,95,'NGINX','TLS :443\nHTTPS ingress only')
 f.node(712,102,150,95,'FastAPI','Internal :8080\nJob and status APIs')
 f.node(536,250,150,112,'PostgreSQL','Internal :5432\nJobs / outbox / events\nCanonical host ownership')
 f.node(712,250,150,112,'Worker','Pinned caller release\nInventory + SSH key\nAsync host execution')
 f.node(922,102,198,95,'Access contract','Alias -> canonical host\nPinned access + release','target')
 f.node(922,250,198,105,'Target PA host','Existing SSH :22\nAgent packages / services\nNo added web listener','target',5)
 f.edge([(232,148),(284,148)],'MCP',(243,127,55))
 f.edge([(382,197),(382,234)],'REST',(395,218,65))
 f.edge([(480,279),(503,279),(503,212),(611,212),(611,197)],'HTTPS :443',(519,207,115))
 f.edge([(686,148),(712,148)])
 f.edge([(787,197),(787,221),(611,221),(611,250)],'Commit / query',(624,215,140),teal=True)
 f.edge([(712,302),(686,302)],teal=True)
 f.edge([(862,302),(922,302)],'SSH :22',(866,283,66))
 f.edge([(1021,197),(1021,250)],'Resolve target',(1029,222,100),teal=True)
 f.edge([(348,329),(348,358)],teal=False)
 f.edge([(480,393),(490,393),(490,314),(480,314)],dashed=True,teal=True)
 f.body(536,390,'Studio relay and dispatcher call the parent API.\nWorker and database stay on the private container network.',327,13,G)
 f.banner('PLACEMENT RULE','Management services run together; host selection comes from immutable inventory, not agent-group routing.')
 return f

def fleet():
 f=Figure('02-target-resolution')
 f.zone(18,20,272,430,'DELIVERY EXECUTION','Jitterbit agent group',A);f.zone(314,20,432,430,'TARGET AUTHORITY','Dedicated management service');f.zone(770,20,372,430,'EXECUTION DESTINATION','Explicit target identity',C)
 f.node(40,105,228,92,'Management agent A','Runs the same dispatcher\nMay receive this operation','jb')
 f.node(40,242,228,92,'Management agent B','Runs the same dispatcher\nMay receive the next operation','jb')
 f.node(336,174,180,116,'Parent job API','jobId -> retained job\nAuthorize requested target\nNever accept arbitrary SSH host',num=1)
 f.node(542,104,182,142,'Versioned inventory','target: qa-pa-03\ncanonicalHost: VM-003\nSSH host + pinned key\nApproved identity / actions',num=2)
 f.node(542,292,182,151,'Host ownership','Lock key: VM-003\nAliases share the same owner\nOne mutation per host\nRetain on unknown outcome',num=3)
 f.node(792,105,328,110,'qa-pa-03 -> VM-003','Worker resolves the accepted inventory revision\nPinned SSH endpoint and release policy\nSame named host whichever agent dispatched','target',4)
 f.node(792,293,328,112,'Independent target VMs','qa-pa-04 -> VM-004\nprod-pa-01 -> VM-021\nEach has separate access and ownership','target')
 f.edge([(268,151),(300,151),(300,211),(336,211)])
 f.edge([(268,288),(300,288),(300,253),(336,253)])
 f.edge([(516,211),(529,211),(529,175),(542,175)])
 f.edge([(633,246),(633,292)],'Claim',(645,275,80),teal=True)
 f.edge([(724,175),(792,175)],'Resolve',(735,154,80))
 f.edge([(724,355),(757,355),(757,233),(956,233),(956,215)],'Ownership gates execution',(800,254,280),teal=True)
 f.banner('ROUTING RULE','Any permitted management agent can dispatch a job; the worker always targets the recorded canonical host.')
 return f

def sequence(name,actors,steps,summary):
 f=Figure(name);left=100;right=1060;n=len(actors);xs=[left+i*(right-left)/(n-1) for i in range(n)]
 f.rect(18,18,1124,442,W,L,10)
 for i,(title,sub,kind) in enumerate(actors):
  x=xs[i];f.node(x-64,34,128,75,title,sub,kind)
  f.edges.append(Line(x,f.h-113,x,f.h-438,strokeColor=HexColor(L),strokeWidth=1,strokeDashArray=[4,4]))
 dy=290/max(1,len(steps));start=145
 for i,(a,b,title,payload,ret) in enumerate(steps):
  y=start+i*dy;xa=xs[a];xb=xs[b]
  # Small activation rails identify request handling without concealing arrow heads.
  f.nodes.append(Rect(xb-3,f.h-y-13,6,26,fillColor=HexColor('#A5BEC3'),strokeColor=HexColor(T),strokeWidth=.5))
  f.edge([(xa,y),(xb,y)],dashed=ret,teal=ret)
  lx=min(xa,xb)+14;maxw=abs(xb-xa)-28
  f.txt(lx,y-19,f'{i+1:02d}  '+title,12.5,T,True)
  f.txt(lx,y-5,payload,11.5,G)
  for s in [f'{i+1:02d}  '+title,payload]:
   if stringWidth(s,'Arial-Bold' if s.startswith(f'{i+1:02d}') else 'Arial',12.5 if s.startswith(f'{i+1:02d}') else 11.5)>maxw:raise ValueError('Sequence label too wide '+s)
 f.txt(38,449,'Solid orange = request / handoff   |   Dashed teal = response',11,G)
 f.banner('PROTOCOL GUARANTEE',summary)
 return f

def admission():
 return sequence('03-admission',[('MCP / APIM','Submit operation','jb'),('Parent API','Validate + authorize','service'),('PostgreSQL','Atomic transaction','service'),('Studio relay','Outbox publisher','jb'),('JBMQ','Job references','jb')],[
 (0,1,'Submit job','POST /v1/jobs + idempotency key',False),
 (1,2,'Commit acceptance','job + outbox + immutable request hash',False),
 (2,1,'Commit confirmed','ACCEPTED_PENDING_DISPATCH',True),
 (1,0,'Return receipt','202 + jobId + current state',True),
 (3,1,'Read due outbox','Scoped relay endpoint',False),
 (3,4,'Publish reference','schemaVersion + jobId',False),
 (3,1,'Confirm publication','Retain outbox until confirmed',False)],'A durable job exists before publication. Repeat submission returns the same job; changed input with the same key conflicts.')

def dispatch():
 return sequence('04-dispatch',[('JBMQ','Queue delivery','jb'),('Studio','Dispatcher','jb'),('Parent API','Dispatch endpoint','service'),('PostgreSQL','Durable state','service')],[
 (1,0,'Get message','Consume job reference',False),
 (0,1,'Deliver reference','Delivery may repeat',True),
 (1,2,'Request dispatch','POST /v1/jobs/{id}/dispatch',False),
 (2,3,'Commit readiness','READY or compatible prior acceptance',False),
 (3,2,'State persisted','Duplicate cannot restart an attempt',True),
 (2,1,'Dispatch accepted','Safe to acknowledge delivery',True),
 (1,0,'Acknowledge','Do not wait for installation',False)],'ACK follows durable dispatch acceptance. The queue delivery is complete before long-running host execution begins.')

def execution():
 return sequence('05-execution',[('Worker','Independent process','service'),('PostgreSQL','Host ownership','service'),('JBPA caller','Pinned adapter','service'),('Target VM','Existing SSH','target')],[
 (0,1,'Claim ready job','jobId + attemptId + canonical host',False),
 (1,0,'Ownership acquired','Record inventory / release revision',True),
 (0,2,'Start permitted action','Fixed action and named target',False),
 (2,3,'Run remote lifecycle','Pinned SSH identity / host key',False),
 (3,2,'Return evidence','Validated outcome or uncertainty',True),
 (2,0,'Normalize result','Preserve original attempt identity',True),
 (0,1,'Persist outcome','Terminal result or reconciliation hold',False)],'Installations may take minutes. Unknown outcomes retain host ownership; lease expiry never authorizes a second mutation.')

def data():
 f=Figure('06-data-ownership');f.zone(18,20,710,430,'ATOMIC ACCEPTANCE','Job and publication outbox');f.zone(754,20,388,430,'EXECUTION COORDINATION','Ownership and evidence',C)
 f.node(42,104,300,159,'jobs','PK job_id\nUQ caller_scope + idempotency_key\nImmutable request_hash\ntarget_id / canonical_host_id\nstate / attempt_id / result_ref\nPinned inventory + caller release')
 f.node(404,104,300,159,'dispatch_outbox','FK job_id; one required publication\nclaim / publication_attempt\nnext_due_at / confirmation\nCreated in job acceptance transaction\nRepublish safely after send uncertainty')
 f.node(778,104,340,139,'host_execution_ownership','PK canonical_host_id\nFK active_job_id + attempt_id\nworker / heartbeat / reconciliation\nOne mutation across target aliases','target')
 f.node(778,304,340,139,'job_events + evidence','FK job_id + attempt_id\nOrdered transitions and access decisions\nSanitized result + protected evidence ID\nNo credentials in API result','target')
 f.edge([(342,164),(404,164)],'1 : 1',(356,145,70),teal=True)
 f.edge([(778,174),(740,174),(740,82),(192,82),(192,104)],'Guards canonical host',(446,77,225),teal=True)
 f.edge([(342,236),(372,236),(372,285),(948,285),(948,304)],'1 : many events',(451,277,205),teal=True)
 f.rect(42,299,662,119,W,L,7);f.txt(58,323,'STATE CONTRACT',12,T,True)
 f.body(58,347,'ACCEPTED_PENDING_DISPATCH -> READY -> RUNNING\nKnown outcome -> SUCCEEDED or FAILED\nUnknown remote outcome -> NEEDS_RECONCILIATION',625,14,T)
 f.banner('DATA AUTHORITY','PostgreSQL retains the business record. JBMQ buffers delivery; it is not a result store or historical job database.')
 return f

def recovery():
 f=Figure('07-recovery');f.zone(18,20,1124,430,'INTERRUPTED EXECUTION','Resolve the original attempt before releasing ownership')
 f.node(40,108,226,106,'Interruption detected','SSH / worker / DB loss\nJob + original attempt retained\nRemote action may continue',num=1)
 f.node(308,108,226,106,'Observe original evidence','Read process / result evidence\nInspect package and service state\nVerify expected Harmony identity',num=2)
 # Deliberately aligned decision and branches, with reserved routing gutters.
 f.nodes.append(Polygon([594,f.h-161,688,f.h-108,782,f.h-161,688,f.h-214],fillColor=HexColor(W),strokeColor=HexColor(T),strokeWidth=1.5))
 f.txt(688,154,'Outcome',15,T,True,'middle');f.txt(688,175,'resolved?',15,T,True,'middle')
 f.node(842,108,278,106,'Persist resolved outcome','SUCCEEDED / FAILED\nRetain verified evidence\nThen release host ownership','target',3)
 f.node(556,286,264,118,'Reconciliation hold','NEEDS_RECONCILIATION\nKeep original attempt + host owner\nInspect and re-check evidence\nNo blind mutation replay',num=4)
 f.rect(40,286,442,118,W,L,7);f.txt(56,311,'SAFETY RULES',12,T,True);f.body(56,337,'Timeout is not proof that nothing changed.\nLease expiry does not prove the remote action stopped.\nReinstall / Harmony deletion need separate authorization.',409,14,G)
 f.edge([(266,161),(308,161)])
 f.edge([(534,161),(594,161)])
 f.edge([(782,161),(842,161)],'Yes',(797,143,58))
 f.edge([(688,214),(688,286)],'No',(701,252,50))
 f.edge([(556,345),(515,345),(515,251),(421,251),(421,214)],'Inspect original attempt',(438,239,205),True,True)
 f.banner('RECOVERY GUARANTEE','Only observed evidence resolves the original action. A subsequent mutation has its own authorization and job identity.')
 return f

def result():
 return sequence('08-result',[('AI / user','New status request','service'),('MCP server','jbpa_get_job','jb'),('APIM / Studio','Status operation','jb'),('Parent API','Permission checks','service'),('PostgreSQL','Retained job','service')],[
 (0,1,'Ask for job status','Retained jobId',False),
 (1,2,'Invoke status API','GET job operation',False),
 (2,3,'Read permitted job','GET /v1/jobs/{id}',False),
 (3,4,'Query current record','Caller / target scope',False),
 (4,3,'Return current state','Job + normalized outcome',True),
 (3,2,'Project safe response','jobId / state / versions / result',True),
 (2,1,'Return API response','Preserve state and safe result',True),
 (1,0,'Explain current outcome','Pending, terminal or not-found',True)],'Pending jobs remain retrievable. If the AI cannot poll, the user asks later; no original HTTP or MCP call stays open.')

BUILDERS=[topology,fleet,admission,dispatch,execution,data,recovery,result]
def build_all(out):return {f.name:f.finish(out) for f in [b() for b in BUILDERS]}
