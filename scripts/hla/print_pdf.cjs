let playwright;
try {playwright=require('playwright');} catch(e) {playwright=require('/Users/dharish.sewraj/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');}
const {chromium}=playwright;
const path=require('path');const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--allow-file-access-from-files']});
 const page=await browser.newPage();await page.goto('file://'+path.resolve('docs/hla/JBPA_Management_HLA.html'));await page.emulateMedia({media:'print'});await page.evaluate(()=>document.fonts.ready);
 const layout=await page.evaluate(()=>[...document.querySelectorAll('.sheet')].map(e=>({page:+e.dataset.page,title:e.dataset.title,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,footerBottom:e.querySelector('footer').getBoundingClientRect().bottom-e.getBoundingClientRect().top,wide:e.classList.contains('wide')})));
 fs.writeFileSync('tmp/pdfs/hla-v6/layout.json',JSON.stringify(layout,null,2));
 const overflow=layout.filter(e=>e.height>(e.wide?703:1009));
 if(overflow.length){await browser.close();throw new Error('Page overflow: '+JSON.stringify(overflow));}
 console.log('Layout checked: '+layout.length+' sheets');
 await page.pdf({path:'tmp/pdfs/hla-v6/printed.pdf',preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
