const fs=require('fs'),path=require('path');
let pw;try{pw=require('playwright')}catch(e){pw=require('/Users/dharish.sewraj/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')}
(async()=>{
 const installed=path.join(__dirname,'node_modules/mermaid/dist/mermaid.esm.min.mjs');
 const dist=process.env.MERMAID_DIST || (fs.existsSync(installed)?installed:'/private/tmp/jbpa-hla-diagrams/node_modules/mermaid/dist/mermaid.esm.min.mjs');
 const browser=await pw.chromium.launch({executablePath:process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--allow-file-access-from-files']});
 const page=await browser.newPage({viewport:{width:1800,height:1400}});
 const seed=path.resolve('tmp/pdfs/hla-v5/diagram-host.html');fs.writeFileSync(seed,'<!doctype html><html><body></body></html>');await page.goto('file://'+seed);
 await page.evaluate(async(url)=>{const m=await import(url);window.mermaid=m.default;window.mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',fontFamily:'Arial, Helvetica, sans-serif',themeVariables:{fontFamily:'Arial',fontSize:'18px',primaryColor:'#EBF0F3',primaryTextColor:'#073847',primaryBorderColor:'#A5BEC3',lineColor:'#FF6529',secondaryColor:'#F7FAFB',tertiaryColor:'#F7FAFB',clusterBkg:'#F7FAFB',clusterBorder:'#C7D4DA',actorBkg:'#EBF0F3',actorBorder:'#073847',actorTextColor:'#073847',actorLineColor:'#A5BEC3',signalColor:'#073847',signalTextColor:'#073847',noteBkgColor:'#F4F8FA',noteTextColor:'#073847',noteBorderColor:'#C7D4DA'},flowchart:{curve:'linear',nodeSpacing:40,rankSpacing:55,padding:18,htmlLabels:false},sequence:{useMaxWidth:false,actorMargin:65,width:185,height:50,boxMargin:10,messageMargin:28,noteMargin:12,mirrorActors:false,actorFontSize:17,messageFontSize:16,noteFontSize:14}})},'file://'+dist);
 const dims=[];fs.mkdirSync('output/hla/diagrams',{recursive:true});
 const names=new Set(JSON.parse(fs.readFileSync('docs/hla/model.json','utf8')).pages.filter(p=>p.diagram).map(p=>p.diagram+'.mmd'));
 for(const file of fs.readdirSync('docs/hla/diagram-source').filter(x=>names.has(x))){
  const src=fs.readFileSync(path.join('docs/hla/diagram-source',file),'utf8');
  let svg=await page.evaluate(async({src,id})=>(await window.mermaid.render(id,src)).svg,{src,id:'d_'+file.replace('.mmd','')});
  if(['submission.mmd','dispatch.mmd','execution.mmd','results.mmd'].includes(file)){
   svg=await page.evaluate((svg)=>{const doc=new DOMParser().parseFromString(svg,'image/svg+xml');const root=doc.documentElement;const vb=root.getAttribute('viewBox').split(/\s+/).map(Number);root.setAttribute('viewBox',`${vb[0]+vb[2]/2-642.5} -10 1285 517`);root.setAttribute('width','1285');root.setAttribute('height','517');root.setAttribute('style','max-width:1285px;');return new XMLSerializer().serializeToString(root)},svg);
  }
  fs.writeFileSync(path.join('output/hla/diagrams',file.replace('.mmd','.svg')),svg);
  const vb=svg.match(/viewBox="([^"]+)"/);dims.push({file,viewBox:vb&&vb[1]});
 }
 await browser.close();console.log(JSON.stringify(dims,null,2));fs.writeFileSync('tmp/pdfs/hla-v5/diagram-dimensions.json',JSON.stringify(dims,null,2));
})().catch(e=>{console.error(e);process.exit(1)});
