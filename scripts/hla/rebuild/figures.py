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
  self.rect(x,y,w,h,P,L,10);self.txt(x+16,y+24,kicker,11,G,True);self.txt(x+16,y+48,title,17,T,True)
 def node(self,x,y,w,h,title,body,kind='service',num=None):
  dark=False
  self.rect(x,y,w,h,W,'#9FB5BE',7)
  self.nodes.append(Rect(x+1,self.h-y-4,w-2,3,fillColor=HexColor(T),strokeColor=None))
  if num:self.nodes.append(Circle(x+19,self.h-y-20,10,fillColor=HexColor(O),strokeColor=None));self.txt(x+19,y+24,str(num),11,W,True,'middle')
  tx=x+14+(26 if num else 0)
  ts,bs,tl,bl=(14.5,12.5,17,16) if h<=75 else (15,12.5,18,17)
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
 f.zone(18,20,278,450,'CLIENT AND HARMONY','Jitterbit request / delivery')
 f.zone(318,20,578,450,'DEDICATED MANAGEMENT HOST','API, durable state and worker')
 f.zone(918,20,224,450,'NAMED TARGET VM','Existing host access')
 f.txt(340,86,'One Linux deployment: NGINX + FastAPI + PostgreSQL + worker',12,G)
 # Three aligned rows describe the lifecycle; repeated services are action views.
 f.node(40,110,234,96,'Submit action','AI -> MCP -> protected APIM\nStudio calls the parent API',num=1)
 f.node(340,110,252,96,'Accept + authorize','NGINX :443 -> FastAPI :8080\nValidate caller, target and action',num=2)
 f.node(622,110,252,96,'Commit job + outbox','PostgreSQL :5432; private network\nPersist request hash + accepted job ID',num=3)
 f.node(940,110,180,96,'Prerequisites','Provisioned supported VM\nPinned SSH key / sudo\nRelease + registration')
 f.node(40,250,234,108,'Publish + dispatch','Studio relay publishes jobId\nJBMQ buffers the reference\nStudio dispatcher reads / sends',num=4)
 f.node(340,250,252,108,'Commit READY','Parent API accepts dispatch\nPersist READY / prior acceptance\nOnly then may Studio ACK',num=5)
 f.node(622,250,252,108,'Claim + execute','Resolve recorded inventory\nClaim canonical host + attempt\nRun the pinned JBPA SSH caller\nExecution runs in the worker',num=6)
 f.node(940,250,180,108,'Target action','Existing SSH :22\nInstall/upgrade/uninstall\nVerify package, service\nand Harmony identity',num=7)
 f.node(40,385,234,70,'Read job result','New GET through MCP / APIM\nState + sanitized outcome',num=10)
 f.node(340,385,252,70,'Serve job status','FastAPI GET /v1/jobs/{id}\nAuthorize + project safe result',num=9)
 f.node(622,385,252,70,'Store outcome','PostgreSQL result + audit record\nUnknown -> reconciliation hold',num=8)
 f.node(940,385,180,70,'Host boundary','No extra web service\nNo new listening port')
 f.edge([(274,158),(340,158)])
 f.edge([(592,158),(622,158)])
 f.edge([(748,206),(748,226),(157,226),(157,250)],'Outbox via parent API',(386,220,260))
 f.edge([(274,304),(340,304)])
 f.edge([(592,304),(622,304)])
 f.edge([(874,304),(940,304)],'SSH',(895,300,42))
 # Result returns through the original SSH connection; the worker retains it.
 f.edge([(940,335),(874,335)],'Evidence',(880,326,60),True,True)
 f.edge([(748,358),(748,385)],teal=True)
 f.edge([(622,420),(592,420)],teal=True)
 f.edge([(340,420),(274,420)],teal=True)
 f.txt(40,99,'A  ACCEPT AND PUBLISH',11,T,True)
 f.txt(340,239,'B  DISPATCH AND EXECUTE',11,T,True)
 f.txt(40,379,'C  RETAIN AND RETRIEVE',11,T,True)
 f.banner('READING KEY','Follow 01 -> 10. Orange = requests / handoffs; teal = result path. Grey = deployment zones; white = actions.',478)
 return f

def fleet():
 f=Figure('02-target-resolution')
 f.zone(18,20,272,430,'DELIVERY EXECUTION','Jitterbit agent group')
 f.zone(314,20,560,430,'TARGET AUTHORITY','Recorded mapping and canonical host')
 f.zone(896,20,246,430,'TARGET FLEET','Explicit destination')
 f.node(40,112,228,126,'Management agent A','Runs the shared dispatcher\nCalls the same parent URL\nDoes not select the target')
 f.node(40,292,228,126,'Management agent B','Runs the shared dispatcher\nCalls the same parent URL\nMay receive the next operation')
 f.node(336,112,232,126,'Accept requested target','Parent API authorizes target\nRetain job + inventory revision\nReject arbitrary SSH addresses',num=1)
 f.node(620,112,232,126,'Resolve pinned mapping','target: qa-pa-03\ncanonical host: VM-003\nSSH endpoint + pinned host key\nApproved identity and actions',num=2)
 f.node(336,292,232,126,'Claim canonical host','PostgreSQL ownership: VM-003\nAliases share the same lock\nOne active mutation; retain owner\nif the remote outcome is unknown',num=3)
 f.node(620,292,232,126,'Worker executes','Use recorded inventory revision\nLoad the approved SSH identity\nRun the fixed, permitted caller\nSame target from either PA',num=4)
 f.node(918,112,202,126,'Target requirements','Provisioned supported host\nVerified SSH key / sudo\nApproved release + registration\nPermitted maintenance action')
 f.node(918,292,202,126,'VM-003','Named target: qa-pa-03\nPinned SSH destination\nOther VMs have separate locks\nNo PA-host web listener',num=5)
 f.edge([(268,175),(336,175)])
 f.edge([(268,355),(301,355),(301,202),(336,202)])
 f.edge([(568,175),(620,175)])
 f.edge([(736,238),(736,261),(452,261),(452,292)],'Same canonical host key',(486,252,215),teal=True)
 f.edge([(568,355),(620,355)],'Owner',(576,338,50),teal=True)
 f.edge([(852,355),(918,355)],'SSH',(873,338,40))
 f.banner('ROUTING RULE','Management-agent scheduling only delivers the job. Inventory, authorization and ownership determine the target.')
 return f

def sequence(name,actors,steps,summary):
 f=Figure(name);left=116;right=1044;n=len(actors);xs=[left+i*(right-left)/(n-1) for i in range(n)]
 f.rect(18,18,1124,442,P,L,10)
 for i,(title,sub,kind) in enumerate(actors):
  x=xs[i];f.node(x-80,34,160,75,title,sub,kind)
  f.edges.append(Line(x,f.h-113,x,f.h-438,strokeColor=HexColor(L),strokeWidth=1,strokeDashArray=[4,4]))
 dy=290/max(1,len(steps));start=145
 for i,(a,b,title,payload,ret) in enumerate(steps):
  y=start+i*dy;xa=xs[a];xb=xs[b]
  # Small activation rails identify request handling without concealing arrow heads.
  f.nodes.append(Rect(xb-3,f.h-y-13,6,26,fillColor=HexColor('#A5BEC3'),strokeColor=HexColor(T),strokeWidth=.5))
  f.edge([(xa,y),(xb,y)],dashed=ret,teal=ret)
  lx=min(xa,xb)+14;maxw=abs(xb-xa)-28
  f.nodes.append(Circle(48,f.h-y,11,fillColor=HexColor(O),strokeColor=None))
  f.txt(48,y+4,f'{i+1:02d}',11,W,True,'middle')
  f.txt(lx,y-20,title,13.5,T,True)
  f.txt(lx,y-5,payload,12,G)
  for s in [title,payload]:
   if stringWidth(s,'Arial-Bold' if s==title else 'Arial',13.5 if s==title else 12)>maxw:raise ValueError('Sequence label too wide '+s)
 f.txt(38,449,'Read numbered rows from top to bottom. Orange = request / handoff; dashed teal = response.',11,G)
 f.banner('PROTOCOL GUARANTEE',summary)
 return f

def admission():
 return sequence('03-admission',[('MCP / APIM','Submit operation','jb'),('Parent API','Validate + authorize','service'),('PostgreSQL','Atomic transaction','service'),('Studio relay','Outbox publisher','jb'),('JBMQ','Job references','jb')],[
 (0,1,'Submit job','POST /v1/jobs + idempotency key',False),
 (1,2,'Commit acceptance','job / outbox / immutable hash',False),
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
 f.node(778,104,340,159,'host_execution_ownership','PK canonical_host_id\nFK active_job_id + attempt_id\nworker / heartbeat / reconciliation\nOne mutation across target aliases','target')
 f.node(778,299,340,119,'job_events + evidence','FK job_id + attempt_id\nOrdered transitions and access decisions\nSanitized result + protected evidence ID\nNo credentials in API result','target')
 f.edge([(342,164),(404,164)],'1 : 1',(356,145,70),teal=True)
 f.edge([(778,174),(740,174),(740,82),(192,82),(192,104)],'Guards canonical host',(446,77,225),teal=True)
 f.edge([(342,236),(372,236),(372,285),(948,285),(948,299)],'1 : many events',(451,277,205),teal=True)
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
