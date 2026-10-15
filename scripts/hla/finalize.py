#!/usr/bin/env python3
"""Validate Chrome pagination and publish the navigable HLA PDF."""
from pathlib import Path
import json, hashlib
from pypdf import PdfReader,PdfWriter
ROOT=Path(__file__).resolve().parents[2]
model=json.loads((ROOT/'docs/hla/model.json').read_text());source=ROOT/'tmp/pdfs/hla-v6/printed.pdf'
r=PdfReader(source);expected=len(model['pages'])
if len(r.pages)!=expected:raise SystemExit(f'Pagination failed: {len(r.pages)} pages, expected {expected}')
for i,(page,spec) in enumerate(zip(r.pages,model['pages']),1):
 text=page.extract_text()
 if f'{i} / {expected}' not in text:raise SystemExit(f'Footer mismatch on page {i}')
 if len(text)<500:raise SystemExit(f'Unexpected empty/orphan page {i}')
w=PdfWriter();w.clone_document_from_reader(r)
for i,p in enumerate(model['pages']):w.add_outline_item(p['title'],i)
w.add_metadata({'/Title':'JBPA Management Platform - High-Level Architecture v6.0','/Author':'Jitterbit','/Subject':'Proposed customer-deployable architecture; production qualification pending'})
out=ROOT/'output/pdf'/f'JBPA_Management_High_Level_Architecture_v{model["version"].split(".")[0]}.pdf'
with out.open('wb') as f:w.write(f)
manifest={'version':'6.0','pages':expected,'pdf':str(out.relative_to(ROOT)),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_html':'docs/hla/JBPA_Management_HLA.html','renderer':'HTML/CSS + headless Chrome','brand_references':['Opportunity Intelligence brand assets, palette and typography; rebuilt engineering document layout'],'status':'PROPOSED_DESIGN','diagrams':[f'output/hla/diagrams/{name}.svg' for name in sorted({p['diagram'] for p in model['pages'] if p.get('diagram')})],'visual_qa':'PENDING'}
(ROOT/'output/hla/manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
