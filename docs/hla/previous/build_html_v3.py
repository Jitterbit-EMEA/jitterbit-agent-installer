#!/usr/bin/env python3
"""Build the HLA using the established white-canvas Jitterbit HTML report style."""
from pathlib import Path
from html import escape
import json, textwrap, base64
ROOT=Path(__file__).resolve().parents[2]
MODEL=json.loads((ROOT/'docs/hla/model.json').read_text());MODEL['version']='3.0'
D=ROOT/'output/hla/diagrams';D.mkdir(parents=True,exist_ok=True)
TEAL='#073847';ORANGE='#FF6529';LINE='#C7D4DA';MUTED='#546c78'

class SVG:
 def __init__(self,w=1080,h=450):
  self.w=w;self.h=h;self.ops=[]
 def rect(self,x,y,w,h,fill='white',stroke=LINE,r=9):self.ops.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>')
 def text(self,x,y,t,size=15,color=TEAL,bold=False,center=False):self.ops.append(f'<text x="{x}" y="{y}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" fill="{color}" font-weight="{700 if bold else 400}" text-anchor="{"middle" if center else "start"}">{escape(t)}</text>')
 def label(self,x,y,t,width,size=14,color=MUTED,bold=False,center=False):
  lines=[]
  for row in t.split('\n'):lines+=textwrap.wrap(row,max(9,int(width/(size*.52)))) or ['']
  for i,l in enumerate(lines):self.text(x,y+i*(size+5),l,size,color,bold,center)
  return len(lines)*(size+5)
 def node(self,x,y,w,h,title,body,dark=False):
  self.rect(x,y,w,h,TEAL if dark else 'white',ORANGE if dark else LINE,8)
  color='white' if dark else TEAL
  used=self.label(x+13,y+24,title,w-26,15,color,True)
  used+=self.label(x+13,y+28+used,body,w-26,13.5,'white' if dark else MUTED)
  if used+28>h+8:raise ValueError(f'Node overflow {title} {used} {h}')
 def path(self,points,color=ORANGE,reply=False,arrow=True):
  ps=' '.join(f'{x},{y}' for x,y in points)
  self.ops.append(f'<polyline points="{ps}" fill="none" stroke="{color}" stroke-width="2"'+(' stroke-dasharray="6 5"' if reply else '')+(f' marker-end="url(#{"teal" if color==TEAL else "orange"})"' if arrow else '')+'/>')
 def export(self,name):
  xml=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(name)}"><defs><marker id="orange" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="{ORANGE}"/></marker><marker id="teal" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="{TEAL}"/></marker></defs>'+''.join(self.ops)+'</svg>'
  (D/(name+'.svg')).write_text(xml);return xml

def solution():
 s=SVG(h=430)
 for x,w,title in [(0,130,'AI INTERFACE'),(150,440,'JITTERBIT HARMONY'),(610,330,'CUSTOMER MANAGEMENT'),(960,120,'TARGETS')]:
  s.rect(x,10,w,388,'#F7FAFB',LINE,10);s.text(x+12,36,title,12,TEAL,True)
 s.node(10,112,110,108,'AI client','Submit\nRead result')
 s.node(165,112,115,108,'MCP','Tool catalog\nAI contract',True)
 s.node(310,112,115,108,'APIM','Protected\nREST APIs',True)
 s.node(455,112,120,108,'Studio','Submit / relay\nDispatch',True)
 s.node(625,112,140,108,'Parent API','Authorize\nPersist job')
 s.node(625,268,140,95,'PostgreSQL','Jobs / outbox\nSafe results')
 s.node(790,268,135,95,'Worker','Fixed JBPA\nSSH adapter')
 s.node(455,268,120,95,'JBMQ','Requests\nDelivery DLQ',True)
 s.node(310,268,115,95,'Dispatcher','Accept job\nThen ACK',True)
 s.node(970,268,100,128,'PA hosts','Existing SSH\nLifecycle\nEvidence')
 for x1,x2 in [(120,165),(280,310),(425,455),(575,625)]:s.path([(x1,160),(x2,160)])
 s.path([(515,220),(515,268)]);s.text(524,248,'enqueue',12)
 s.path([(455,312),(425,312)]);s.text(426,294,'Get',12)
 s.path([(367,363),(367,382),(600,382),(600,190),(625,190)]);s.text(464,377,'execution acceptance',12)
 s.path([(695,220),(695,268)],TEAL);s.text(704,249,'persist',12)
 s.path([(790,312),(765,312)],TEAL);s.text(856,250,'claim / result',12,TEAL,False,True)
 s.path([(925,312),(970,312)],TEAL);s.text(941,292,'SSH',12)
 s.text(12,424,'Proposed design | Solid orange: request delivery | Teal: stored state and remote execution',13,MUTED)
 return s.export('solution')

def seq(kind):
 s=SVG(h=446)
 if kind=='submission':
  names=['AI + MCP','APIM / Studio','Parent API','PostgreSQL','JBMQ'];xs=[95,315,535,755,975]
  msgs=[(0,1,'Submit target + action',False),(1,2,'Create job + request key',False),(2,3,'Commit job + outbox',False),(3,2,'Commit confirmed',True),(2,1,'Stable job ID',True),(1,4,'Publish job reference',False),(1,2,'Record publication',False),(1,0,'202 + observed state',True)]
 elif kind=='execution':
  names=['JBMQ','Studio dispatcher','Parent / DB','Worker','Target host'];xs=[95,315,535,755,975]
  msgs=[(0,1,'Deliver job reference',False),(1,2,'Accept execution',False),(2,1,'READY committed',True),(1,0,'ACK delivery',False),(3,2,'Claim job + host',False),(2,3,'Attempt confirmed',True),(3,4,'SSH: fixed JBPA action',False),(4,3,'Structured outcome',True),(3,2,'Persist final result',False)]
 else:
  names=['AI + MCP','APIM / Studio','Parent API','PostgreSQL'];xs=[120,400,680,960]
  msgs=[(0,1,'Get job by ID',False),(1,2,'Authorized status query',False),(2,3,'Read stored job',False),(3,2,'State + safe result',True),(2,1,'Current state/result',True),(1,0,'Explain outcome',True)]
 for x,n in zip(xs,names):
  s.rect(x-89,7,178,43,TEAL,TEAL,6);s.text(x,34,n,15,'white',True,True)
  s.path([(x,52),(x,420)],LINE,True,False)
 gap=38 if len(msgs)==9 else 42 if len(msgs)==8 else 55
 for i,(a,b,label,reply) in enumerate(msgs,1):
  y=83+(i-1)*gap;s.path([(xs[a],y+13),(xs[b],y+13)],TEAL if reply else ORANGE,reply)
  s.text((xs[a]+xs[b])/2,y-1,f'{i}. {label}',14.5,TEAL,False,True)
 s.text(10,443,'Time flows downward. Solid arrow: request/action. Dashed arrow: response. All calls are correlated by job ID.',12.5,MUTED)
 return s.export(kind)

def deployment():
 s=SVG(h=430)
 s.rect(180,15,665,373,'#F7FAFB',LINE,10);s.text(198,43,'DEDICATED MANAGEMENT HOST / CONTAINER NETWORKS',13,TEAL,True)
 s.node(0,105,150,110,'Management PA','Same API URL\nPrivate network',True)
 s.node(210,105,210,100,'NGINX','HTTPS :443\nCertificate / TLS')
 s.node(595,105,220,100,'FastAPI / Uvicorn','Internal :8080\nShort API calls')
 s.node(210,280,210,90,'PostgreSQL','Internal :5432\nPersistent job data')
 s.node(595,280,220,90,'Python worker','Pinned caller\nSSH identities')
 s.node(905,280,175,90,'Target hosts','Existing SSH\nNo added service')
 s.path([(150,157),(210,157)]);s.text(153,141,'HTTPS',12)
 s.path([(420,157),(595,157)]);s.text(508,141,'internal HTTP',13,MUTED,False,True)
 s.path([(705,205),(705,245),(315,245),(315,280)],TEAL);s.text(475,237,'persist / query',13)
 s.path([(595,325),(420,325)],TEAL);s.text(505,307,'claim / result',13,MUTED,False,True)
 s.path([(815,325),(905,325)],TEAL);s.text(860,308,'SSH',13,MUTED,False,True)
 s.text(195,418,'Only HTTPS is published. API/DB ports stay internal. Backups and secret recovery are off-host.',13,MUTED)
 return s.export('deployment')
DIAG={'solution':solution(),'submission':seq('submission'),'execution':seq('execution'),'results':seq('results'),'deployment':deployment()}

def esc(t):return escape(t).replace('\n','<br>')
def prose(text):
 # Preserve the existing narrative and emphasize decision labels, not entire cells.
 t=esc(text)
 for key in ['WHY:','VALUE:','REUSE:','TRADEOFF:']:t=t.replace(key,f'<strong>{key}</strong>')
 return t

def section(s):return f'<section class="report-section"><h2>{esc(s["title"])}</h2><p>{prose(s["text"])}</p></section>'
def table(t):
 return '<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in t['headers'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in t['rows'])+'</tbody></table>'
logo='data:image/jpeg;base64,'+base64.b64encode((ROOT/'docs/hla/assets/jitterbit-logo-long.jpeg').read_bytes()).decode()
css='''
@page standard {size:A4; margin:14mm 14mm 15mm;}
@page wide {size:A4 landscape; margin:12mm 14mm 12mm;}
*{box-sizing:border-box} html,body{margin:0;background:#fff;color:#243746;font-family:Arial,Helvetica,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-size:10.5pt;line-height:1.42}.sheet{page:standard;width:182mm;min-height:266mm;break-after:page;display:flex;flex-direction:column;position:relative}.sheet:last-child{break-after:auto}.sheet.wide{page:wide;width:269mm;min-height:185mm}
.brandbar{display:flex;justify-content:space-between;align-items:center;margin:0 0 14px;min-height:36px;background:#fff}.brandbar img{width:144px;height:auto;display:block}.meta{font-size:7.4pt;color:#546c78;font-weight:700;letter-spacing:.045em;text-transform:uppercase;text-align:right;max-width:260px}
.title-panel{padding:15px 17px 16px;border:1px solid #C7D4DA;border-left:5px solid #FF6529;border-radius:9px;background:linear-gradient(135deg,#fff 0%,#f7fafb 58%,#EBF0F3 100%);margin-bottom:20px}.eyebrow{font-size:7.5pt;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:#546c78;margin-bottom:6px}
h1{color:#073847;font-size:23pt;line-height:1.13;letter-spacing:-.3px;margin:0 0 8px}.subtitle{margin:0;font-size:9.5pt;line-height:1.4;color:#546c78}
main{flex:1}p{margin:0 0 12px}h2{font-size:12pt;line-height:1.25;color:#073847;border-bottom:2px solid #FF6529;padding-bottom:6px;margin:17px 0 10px;break-after:avoid}.report-section:first-child h2{margin-top:0}.report-section{break-inside:avoid}
table{width:100%;border-collapse:collapse;margin:0 0 17px;font-size:9.2pt;line-height:1.4;table-layout:fixed}th{background:#073847;color:white;font-size:9pt;font-weight:700;text-align:left;padding:10px 11px}td{padding:10px 11px;vertical-align:top;border-bottom:1px solid #d4e0e4}tbody tr:nth-child(even){background:#f4f8fa}tr{break-inside:avoid}
.callout{border:1px solid #C7D4DA;border-left:5px solid #FF6529;border-radius:8px;padding:13px 15px;background:#f4f8fa;margin:16px 0;font-size:10pt;line-height:1.45;break-inside:avoid}
.cards{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;align-items:stretch}.card{border:1px solid #C7D4DA;border-radius:9px;padding:16px 17px;background:linear-gradient(180deg,#fff,#f8fbfc);break-inside:avoid}.card h2{border:0;margin:0 0 10px;padding:0;font-size:12pt}.card p{font-size:10.3pt;margin:0;line-height:1.47}.card p strong{color:#073847}
.diagram{padding:12px 5px;border:1px solid #C7D4DA;border-radius:10px;background:#fff;margin:0 0 13px}.diagram svg{display:block;width:100%;height:auto;max-height:425px}.caption{font-size:10pt;line-height:1.4;color:#435b66;border-left:4px solid #FF6529;padding:4px 0 4px 12px;margin-bottom:14px}
.footer{display:flex;justify-content:space-between;border-top:1px solid #C7D4DA;padding-top:9px;margin-top:20px;font-size:7.3pt;color:#617985}
.cover{justify-content:space-between}.cover .brandbar img{width:225px}.cover .hero{margin-top:45px}.cover h1{font-size:34pt;line-height:1.08;margin-top:14px;margin-bottom:20px}.cover .lead{font-size:14pt;line-height:1.5;color:#15546a}.cover .cards{grid-template-columns:1fr;margin:28px 0}.cover .card{padding:17px 19px}.cover .card h2{font-size:12pt}.cover-tag{display:inline-block;padding:8px 12px;background:#eef3f6;border-left:5px solid #FF6529;font-size:9pt;font-weight:700;letter-spacing:.04em;color:#073847;text-transform:uppercase}.cover .footer{border-top:3px solid #FF6529;padding-top:15px}
.refs{display:grid;grid-template-columns:1fr 1fr;gap:9px 20px;font-size:9.5pt;margin-bottom:22px}.refs a{color:#15546a;text-decoration:none}.code-card p{font-family:Consolas,monospace;font-size:9.1pt;line-height:1.45}.wide .title-panel{margin-bottom:16px}.wide h1{font-size:24pt}
.wide .brandbar{min-height:28px;margin-bottom:10px}.wide .brandbar img{width:118px}.wide .title-panel{padding:10px 14px;margin-bottom:12px}.wide h1{font-size:22pt;margin-bottom:6px}.wide .subtitle{font-size:9pt;line-height:1.35}.wide .caption{font-size:9.5pt;margin-bottom:8px}.wide .footer{margin-top:10px;padding-top:7px}.wide .diagram svg{max-height:400px}
@media screen{body{background:#dde5ea}.sheet{background:white;margin:18px auto;padding:0;box-shadow:0 3px 12px #b8c5cc}}
'''
html=['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>JBPA Management HLA v3.0</title><style>'+css+'</style></head><body>']
total=len(MODEL['pages'])
for i,p in enumerate(MODEL['pages'],1):
 kind=p['kind'];wide=kind in ['diagram','columns'];cover=kind=='cover'
 cls='sheet'+(' wide' if wide else '')+(' cover' if cover else '')
 html.append(f'<article class="{cls}" data-page="{i}" data-title="{esc(p["title"])}">')
 html.append(f'<div class="brandbar"><img src="{logo}" alt="Jitterbit"><div class="meta">JBPA management<br>High-level architecture</div></div>')
 if cover:
  html.append('<main><div class="hero"><span class="cover-tag">Customer-deployable architecture</span><h1>JBPA Management<br>Platform</h1><p class="lead">A dependable path from AI request to governed delivery, isolated execution and a durable result.</p></div><div class="cards">')
  for title,body in [('Purpose','Automate Private Agent lifecycle actions on named, supported hosts.'),('Architecture','Jitterbit MCP, API Manager, Studio and JBMQ connect to a dedicated management API, worker and PostgreSQL database.'),('Customer reuse','One versioned Linux container package, with customer-specific configuration and a matching Harmony integration kit.')]:html.append(f'<div class="card"><h2>{title}</h2><p>{body}</p></div>')
  html.append('</div><div class="callout"><strong>Design v3.0 | 06 October 2026</strong><br>Proposed production architecture. Current implementation and qualification boundaries remain explicit.</div></main>')
 else:
  html.append(f'<header class="title-panel"><div class="eyebrow">Architecture / {i:02d}</div><h1>{esc(p["title"])}</h1><p class="subtitle">{esc(p["subtitle"])}</p></header><main>')
  if kind=='diagram':html.append('<div class="diagram">'+DIAG[p['diagram']]+'</div><p class="caption">'+esc(p['caption'])+'</p>')
  elif kind=='columns':html.append('<div class="cards">'+''.join(f'<section class="card {"code-card" if "Appendix" in p["title"] and j<3 else ""}"><h2>{esc(b["title"])}</h2><p>{prose(b["text"])}</p></section>' for j,b in enumerate(p['blocks']))+'</div>')
  elif kind=='references':
   html.append('<div class="refs">'+''.join(f'<div><strong>[{k}]</strong> <a href="{escape(url)}">{esc(t)}</a></div>' for k,t,url in p['references'])+'</div>')
   html.append(section({'title':'Repository and visual provenance','text':'R1: docs/jbpa-management-product.md. R2: docs/production-readiness.md. R3: docs/integrations/skills/README.md. R4: docs/customer-start-here.md. R5: tools/handoff/customer_remote.py. This revision follows the white-canvas HTML report conventions used by the RATP, GSMA and Opportunity Intelligence projects. Original assets and references were not modified.'}))
   html.append('<p>Technology sources and upstream licenses were reviewed during authoring. Version-specific dependencies and redistribution obligations must be checked against the shipped SBOM. The diagrams are editable SVGs embedded directly into this document.</p>')
  else:
   if p.get('table'):html.append(table(p['table']))
   if p.get('sections'):html.extend(section(s) for s in p['sections'])
   if p.get('callout'):html.append('<div class="callout">'+esc(p['callout']).replace('v2.0','v3.0')+'</div>')
  html.append('</main>')
 html.append(f'<footer class="footer"><span>Jitterbit | Proposed design v3.0 | 06 October 2026</span><span>{i} / {total}</span></footer></article>')
html.append('</body></html>')
(ROOT/'docs/hla/JBPA_Management_HLA.html').write_text('\n'.join(html))
print('Built HTML and five editable diagrams')
