#!/usr/bin/env python3
"""Render one readable install storyboard as PNG and editable SVG."""
from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[2]
W=1500;H=2600
T='#073847';O='#FF6529';G='#506875';BG='#EBF0F3';BORDER='#A5BEC3';WHITE='#FFFFFF'
im=Image.new('RGB',(W,H),WHITE);draw=ImageDraw.Draw(im);svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Ten steps from an AI install command through Jitterbit MCP, APIs, JBMQ and the management worker to the result">']
fontdir=Path('/System/Library/Fonts/Supplemental');fonts={}
def font(size,bold=False):
 key=(size,bold)
 if key not in fonts:fonts[key]=ImageFont.truetype(str(fontdir/('Arial Bold.ttf' if bold else 'Arial.ttf')),size)
 return fonts[key]
def rect(x,y,w,h,fill=WHITE,stroke=BORDER,r=13):
 draw.rounded_rectangle((x,y,x+w,y+h),radius=r,fill=fill,outline=stroke,width=2)
 svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
def text(x,y,s,size=25,color=T,bold=False):
 draw.text((x,y),s,font=font(size,bold),fill=color,anchor='lt')
 svg.append(f'<text x="{x}" y="{y+size*.82}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(s)}</text>')
 assert draw.textlength(s,font=font(size,bold))<=W-x-54,(s,'outside drawing')
def wrap(s,width,size=23,bold=False):
 lines=[]
 for line in s.split('\n'):
  current=''
  for word in line.split():
   trial=(current+' '+word).strip()
   if current and draw.textlength(trial,font=font(size,bold))>width:lines.append(current);current=word
   else:current=trial
  lines.append(current)
 return lines

def arrow(y1,y2,color=O):
 x=750;draw.line((x,y1,x,y2-10),fill=color,width=4);draw.polygon([(x,y2),(x-9,y2-14),(x+9,y2-14)],fill=color)
 svg.append(f'<path d="M{x} {y1} V{y2-10}" fill="none" stroke="{color}" stroke-width="4"/><polygon points="{x},{y2} {x-9},{y2-14} {x+9},{y2-14}" fill="{color}"/>')
def phase(y,label):
 rect(65,y,1370,49,T,T,9);text(86,y+12,label,23,WHITE,True);return y+64

def card(y,num,title,route,description,extra=None):
 lines=wrap(description,1160,23);h=110+len(lines)*29+(39 if extra else 0)
 rect(95,y,1310,h,WHITE,BORDER,13)
 draw.rectangle((108,y,1392,y+5),fill=T);svg.append(f'<rect x="108" y="{y}" width="1284" height="5" fill="{T}"/>')
 draw.ellipse((119,y+20,163,y+64),fill=O);svg.append(f'<circle cx="141" cy="{y+42}" r="22" fill="{O}"/>')
 draw.text((141,y+42),str(num),font=font(25,True),fill=WHITE,anchor='mm')
 svg.append(f'<text x="141" y="{y+51}" text-anchor="middle" font-family="Arial" font-size="25" font-weight="700" fill="white">{num}</text>')
 text(185,y+20,title,29,T,True);text(185,y+60,route,24,T,True)
 yy=y+96
 for line in lines:text(185,yy,line,23,G);yy+=29
 if extra:
  text(185,yy+7,extra,23,T,True);yy+=39
 assert yy<=y+h-10,(title,'card overflow')
 return y+h

# One column is intentionally used: no crossing routes or jump to another lane.
rect(0,0,W,7,O,O,0)
text(65,35,'Jitterbit',35,T,True)
text(65,87,'From “install the agent” to a verified result',41,T,True)
text(65,145,'Before step 1: management stack is running; MCP/APIM/Studio and Host 1 setup are validated.',24,G)
rect(65,184,1370,2130,BG,BG,14)
y=205;y=phase(y,'A  SUBMIT THE REQUEST — RECEIVE A JOB ID')
steps=[
(1,'You send the command','AI client: “Install the agent on Host 1.”','The AI uses the validated target, registration profile and selected qualified version.'),
(2,'MCP calls the public installation API','Jitterbit MCP → APIM: POST /installations  [example public route]','APIM authenticates the call and triggers the Submit Installation Studio operation.'),
(3,'Studio calls the management VM','Studio → management API: POST /v1/jobs','Send the target/action/profile/release references and a stable idempotency key.'),
(4,'Management saves the request and replies','FastAPI → PostgreSQL: job + outbox, committed together','Return 202 Accepted with jobId=123 and state=ACCEPTED_PENDING_DISPATCH to Studio.'),
(5,'Studio publishes the reference and returns your receipt','Studio → JBMQ: {schemaVersion: 1, jobId: 123}','After send success: POST /v1/dispatch-outbox/{outboxId}/published. If send is interrupted, the scheduled outbox relay retries.','APIM / MCP → AI: job 123 is accepted. The agent is not installed yet.'),
(6,'A separate Studio dispatcher reads JBMQ','Studio dispatcher → management API: POST /v1/jobs/123/dispatch','The message contains a reference. The management database retains the approved request.'),
(7,'Management accepts execution; Studio acknowledges JBMQ','FastAPI → PostgreSQL: commit READY; then reply to dispatcher','Only after this reply does Studio ACK the queue message. Installation does not hold the queue delivery open.'),
(8,'The worker installs on the named target','Management worker → existing SSH → Host 1 → JBPA installer','Claim job + canonical host, record RUNNING, stage tooling/credentials, run JBPA and verify package, services and Harmony identity.'),
(9,'The worker stores the outcome','Worker → PostgreSQL: persist state, result and evidence reference','SUCCEEDED or FAILED for known outcomes; NEEDS_RECONCILIATION if uncertain. An unknown remote outcome is not blindly retried.'),
(10,'The AI makes a NEW status call and receives the result','MCP → APIM: GET /jobs/123 → Studio → management API: GET /v1/jobs/123','Management reads PostgreSQL and returns a sanitized result through Studio/APIM/MCP. If the AI cannot poll, you ask later with job 123.')]
qa=[]
for num,title,route,desc,*extra in steps:
 if num==6:y+=14;y=phase(y,'B  BACKGROUND DISPATCH AND INSTALLATION — INDEPENDENT OF THE AI CALL')
 if num==10:y+=14;y=phase(y,'C  READ THE RETAINED RESULT — A NEW SHORT API REQUEST')
 if num not in [1,6,10]:arrow(y-23,y-4)
 end=card(y,num,title,route,desc,extra[0] if extra else None);qa.append({'step':num,'top':y,'bottom':end});y=end+28
# Canvas height follows measured card geometry, preserving equal gaps without shrinking type.
footer=y+4;finalH=footer+99
text(65,footer,'ACCEPTED = saved job   •   READY + ACK = delivered for execution   •   SUCCEEDED = verified install',22,T,True)
text(65,footer+36,'Proposed workflow. Public APIM routes are examples; management routes are the agreed API contract.',21,G)
svg.append('</svg>');svg[0]=svg[0].replace(f'height="{H}"',f'height="{finalH}"').replace(f'0 0 {W} {H}',f'0 0 {W} {finalH}')
# Grow the backing image if measured content extends the initial canvas.
if finalH>H:raise ValueError(f'Increase canvas height to {finalH}; current {H}')
out=ROOT/'output/diagrams';out.mkdir(parents=True,exist_ok=True)
im.crop((0,0,W,finalH)).save(out/'install-flow-step-by-step.png')
(out/'install-flow-step-by-step.svg').write_text('\n'.join(svg))
import json
(out/'install-flow-step-by-step-qa.json').write_text(json.dumps({'steps':qa,'width':W,'height':finalH,'publicRoutes':'Illustrative; not deployed','managementRoutes':'Proposed contract'},indent=2)+'\n')
print('Rendered ten-step install picture:',W,'x',finalH)
