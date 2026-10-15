#!/usr/bin/env python3
"""Editorial technical HLA: no narrative tables, decorative cards or title panels."""
from pathlib import Path
from html import escape
import json,base64
ROOT=Path(__file__).resolve().parents[2]
model=json.loads((ROOT/'docs/hla/model.json').read_text())
def esc(t):return escape(str(t)).replace('\n','<br/>')
def prose(t):
 out=esc(t)
 for label in ['WHY:','VALUE:','REUSE:','TRADEOFF:']:out=out.replace(label,'<strong>'+label+'</strong>')
 return out
logo='data:image/png;base64,'+base64.b64encode((ROOT/'docs/hla/assets/jitterbit-logo-icon.png').read_bytes()).decode()
css='''
@page{size:A4 landscape;margin:12mm 14mm}
*{box-sizing:border-box}html,body{margin:0;background:white;color:#243746;font-family:Arial,Helvetica,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-size:10.5pt;line-height:1.48}.sheet{width:269mm;min-height:185mm;display:flex;flex-direction:column;break-after:page}.sheet:last-child{break-after:auto}
.brandbar{height:34px;display:flex;align-items:center;justify-content:space-between;margin-bottom:17px}.brand{display:flex;align-items:center;gap:7px}.brand img{width:27px;height:27px;object-fit:contain}.brand span{font-size:22pt;color:#153f50;font-weight:700;letter-spacing:-.8px}.meta{font-size:8pt;letter-spacing:.04em;color:#617985;text-transform:uppercase}
.kicker{font-size:8pt;letter-spacing:.08em;font-weight:700;color:#FF6529;margin-bottom:6px}h1{font-size:25pt;line-height:1.12;color:#073847;letter-spacing:-.35px;margin:0 0 8px}.subtitle{font-size:10pt;line-height:1.4;color:#546c78;padding-bottom:13px;border-bottom:1.5px solid #FF6529;margin:0 0 16px}
main{flex:1}p{margin:0 0 11px}h2{color:#073847;font-size:13pt;margin:11px 0 8px;line-height:1.2}h3{color:#073847;font-size:11.3pt;margin:0 0 7px;line-height:1.25}.columns{display:grid;grid-template-columns:1fr 1fr;gap:10px 26px;align-items:start}.definition{break-inside:avoid}.definition p{font-size:10pt;line-height:1.43;margin:0 0 7px}.page-ref{white-space:nowrap;font-size:9pt;color:#58727E;margin-left:10px}.field{font-size:8.1pt;text-transform:uppercase;letter-spacing:.045em;font-weight:700;color:#617985;margin-right:5px}.narrative{margin-bottom:12px}.narrative p{font-size:10pt;line-height:1.43;margin-bottom:9px}.outcomes{display:grid;grid-template-columns:repeat(3,1fr);gap:26px;margin:22px 0}.outcomes h3{font-size:11.5pt}.outcomes p{font-size:10pt}
.diagram svg{display:block;width:100%;height:auto;max-height:440px}.diagram-caption{font-size:9.3pt;line-height:1.4;color:#546c78;margin:11px 0 0}.note{font-size:9.5pt;line-height:1.45;color:#435b66;margin:14px 0 0;padding-left:12px;border-left:3px solid #FF6529}.refs{columns:3;column-gap:22px;font-size:9pt}.refs p{break-inside:avoid;margin:0 0 10px}.refs a{color:#15546a;text-decoration:none}.code{white-space:pre-wrap;overflow-wrap:anywhere;font-size:8.8pt;font-family:Consolas,monospace;line-height:1.5;margin:0}.footer{display:flex;justify-content:space-between;font-size:7.4pt;color:#617985;border-top:1px solid #C7D4DA;padding-top:8px;margin-top:12px}
@media screen{html{background:#dce6e9}.sheet{background:white;margin:18px auto}}
'''
html=['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>JBPA Management HLA v6.0</title><style>'+css+'</style></head><body>']
for i,p in enumerate(model['pages'],1):
 html.append(f'<article class="sheet wide" data-page="{i}" data-title="{esc(p["title"])}"><header><div class="brandbar"><div class="brand"><img src="{logo}" alt=""><span>Jitterbit</span></div><span class="meta">JBPA management / HLA v6.0</span></div><div class="kicker">{i:02d} / TECHNICAL ARCHITECTURE</div><h1>{esc(p["title"])}</h1><p class="subtitle">{esc(p["subtitle"])}</p></header><main>')
 if p.get('intro'):html.extend('<p>'+prose(t)+'</p>' for t in p['intro'])
 if p.get('cards'):html.append('<div class="outcomes">'+''.join(f'<section><h3>{esc(a)}</h3><p><strong>{esc(b)}</strong></p><p>{esc(c)}</p></section>' for a,b,c in p['cards'])+'</div>')
 if p.get('diagram'):
  html.append('<div class="diagram">'+(ROOT/f'output/hla/diagrams/{p["diagram"]}.svg').read_text()+'</div>')
  if p.get('caption'):html.append('<p class="diagram-caption">'+prose(p['caption'])+'</p>')
 if p.get('table'):
  t=p['table'];items=[]
  for row in t['rows']:
   if 'reading guide' in p['title'].lower():
    items.append(f'<section class="definition"><h3>{esc(row[0])}<span class="page-ref">{esc(row[2])}</span></h3><p>{prose(row[1])}</p></section>');continue
   body=''.join(f'<p><span class="field">{esc(t["headers"][j])}</span>{prose(v)}</p>' for j,v in enumerate(row[1:],1))
   items.append(f'<section class="definition"><h3>{esc(row[0])}</h3>{body}</section>')
  html.append('<div class="columns">'+''.join(items)+'</div>')
 if p.get('blocks'):
  code='contracts' in p['title'].lower()
  html.append('<div class="columns">'+''.join(f'<section class="definition"><h3>{esc(b["title"])}</h3>'+ (f'<pre class="code">{escape(b["text"])}</pre>' if code else '<p>'+prose(b['text'])+'</p>')+'</section>' for b in p['blocks'])+'</div>')
 if p.get('sections'):html.extend('<section class="narrative"><h2>'+esc(s['title'])+'</h2><p>'+prose(s['text'])+'</p></section>' for s in p['sections'])
 if p.get('callout'):html.append('<p class="note">'+prose(p['callout'])+'</p>')
 if p.get('references'):
  html.append('<div class="refs">'+''.join(f'<p><strong>[{k}]</strong> <a href="{escape(url)}">{esc(t)}</a></p>' for k,t,url in p['references'])+'</div>')
  html.append('<section class="narrative"><h2>Evidence and presentation provenance</h2><p>Repository sources: product specification, production readiness, remote integration contract, customer runbook and existing caller. Jitterbit brand assets and typography originate in Opportunity Intelligence. Engineering diagrams are rebuilt from explicit grids, interfaces, data contracts and enforcement rules.</p></section>')
 html.append(f'</main><footer class="footer"><span>Proposed product architecture | 06 October 2026</span><span>{i} / {len(model["pages"])}</span></footer></article>')
html.append('</body></html>');(ROOT/'docs/hla/JBPA_Management_HLA.html').write_text('\n'.join(html))
print('Rebuilt narrative layout:',len(model['pages']),'sections; no narrative tables or decorative containers')
