#!/usr/bin/env python3
"""Use the Opportunity Intelligence renderer's styles directly for the detailed HLA."""
from pathlib import Path
from html import escape
import json,sys,importlib.util,hashlib,base64
ROOT=Path(__file__).resolve().parents[2]
REF=Path('/Users/dharish.sewraj/Documents/Projects/jitterbit-se-opportunity-intelligence')
SCRIPT=REF/'.agents/skills/jitterbit-opportunity-intelligence/scripts/render_pack.py'
sys.path.insert(0,str(SCRIPT.parent));spec=importlib.util.spec_from_file_location('opportunity_report_reference',SCRIPT);report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)
model=json.loads((ROOT/'docs/hla/model.json').read_text());tokens=json.loads((ROOT/'docs/hla/assets/brand-tokens.json').read_text())
css=report.stylesheet(tokens,compact=False,landscape=True)
(ROOT/'docs/hla/assets/opportunity-report.css').write_text(css)
# These rules control pagination and figure fit only. Visual styles above are unmodified.
paging='''
.sheet{width:269mm;min-height:181mm;display:flex;flex-direction:column;break-after:page}.sheet:last-child{break-after:auto}.sheet main{flex:1}.sheet footer{margin-top:12px}.two-col.balanced{align-items:stretch}.architecture-canvas svg{width:100%;height:auto;max-height:380px}.report-header .stage-block{min-width:82px}.code-panel pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:8pt;line-height:1.4;margin:0}.references{columns:3;column-gap:20px;font-size:8.4pt}.references p{break-inside:avoid;margin:0 0 10px}@media screen{html{background:#dce6e9}.sheet{margin:18px auto;padding:0;background:white}}
'''
logo='data:image/png;base64,'+base64.b64encode((ROOT/'docs/hla/assets/jitterbit-logo-icon.png').read_bytes()).decode()
def esc(t):return escape(str(t)).replace('\n','<br/>')
def text(t):
 out=esc(t)
 for label in ['WHY:','VALUE:','REUSE:','TRADEOFF:']:out=out.replace(label,'<strong>'+label+'</strong>')
 return out

def table(t):return report.table(t['headers'],t['rows'])
def sections(items):return ''.join(report.section(s['title'],f'<p>{text(s["text"])}</p>') for s in items)
def blocks(p):
 code='contracts' in p['title'].lower()
 items=[]
 for b in p['blocks']:
  body=f'<pre>{escape(b["text"])}</pre>' if code else f'<p>{text(b["text"])}</p>'
  items.append(f'<section class="panel {"code-panel" if code else ""}"><h2>{esc(b["title"])}</h2>{body}</section>')
 return '<div class="two-col balanced">'+''.join(items)+'</div>'
html=['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>JBPA Management HLA v5.0</title><style>'+css+paging+'</style></head><body>']
for i,p in enumerate(model['pages'],1):
 html.append(f'<article class="sheet wide" data-page="{i}" data-title="{esc(p["title"])}"><header class="report-header"><div class="brandbar"><div class="brand-lockup"><img class="brand-mark" src="{logo}" alt=""><span class="brand-name">Jitterbit</span></div><div class="audience-chip">Technical architecture</div></div><div class="title-panel"><div><div class="kicker">JBPA Management Platform</div><h1>{esc(p["title"])}</h1><p class="subtitle">{esc(p["subtitle"])}</p></div><div class="stage-block"><span>Revision</span><strong>5.0</strong></div></div></header><main>')
 if p.get('intro'):html.extend('<p class="lead">'+text(t)+'</p>' for t in p['intro'])
 if p.get('cards'):html.append(report.cards([(a,b,c) for a,b,c in p['cards']]))
 if p.get('diagram'):
  svg=(ROOT/f'output/hla/diagrams/{p["diagram"]}.svg').read_text()
  html.append('<section class="architecture-report"><div class="architecture-meta"><strong>PROPOSED DESIGN</strong><span>Component boundaries, calls and data ownership are shown for this view.</span></div><div class="architecture-canvas">'+svg+'</div></section>')
  if p.get('caption'):html.append('<p class="section-intro" style="margin-top:10px">'+text(p['caption'])+'</p>')
 if p.get('table'):html.append(table(p['table']))
 if p.get('blocks'):html.append(blocks(p))
 if p.get('sections'):html.append(sections(p['sections']))
 if p.get('callout'):html.append('<section class="report-section"><div class="executive-callout"><p>'+text(p['callout'])+'</p></div></section>')
 if p.get('references'):
  html.append('<div class="references">'+''.join(f'<p><strong>[{k}]</strong> <a href="{escape(url)}">{esc(t)}</a></p>' for k,t,url in p['references'])+'</div>')
  html.append(sections([{'title':'Repository evidence','text':'R1: docs/jbpa-management-product.md. R2: docs/production-readiness.md. R3: docs/integrations/skills/README.md. R4: docs/customer-start-here.md. R5: tools/handoff/customer_remote.py.'},{'title':'Presentation source','text':'The unmodified stylesheet and presentation components come from jitterbit-se-opportunity-intelligence/.agents/skills/jitterbit-opportunity-intelligence/scripts/render_pack.py. The brand tokens and transparent icon come from that project. Mermaid supplies local automatic diagram layout; no architecture content is uploaded.'}]))
 html.append(f'</main><footer><span>JBPA Management | Proposed architecture | 06 October 2026</span><span>{i} / {len(model["pages"])}</span></footer></article>')
html.append('</body></html>');(ROOT/'docs/hla/JBPA_Management_HLA.html').write_text('\n'.join(html))
(ROOT/'output/hla/style-provenance.json').write_text(json.dumps({'source':str(SCRIPT),'stylesheet_function':'stylesheet(tokens, compact=False, landscape=True)','stylesheet_sha256':hashlib.sha256(css.encode()).hexdigest(),'changes':'Unmodified base stylesheet; pagination and diagram fit rules only','logo':'Original transparent icon plus canonical brand-name text'},indent=2))
print('Applied Opportunity Intelligence stylesheet directly to',len(model['pages']),'detailed sections')
