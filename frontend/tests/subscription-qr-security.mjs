// Real Jinja -> HTML decoding -> browser events -> vendored QR SVG regression.
import { zoomBrowser } from './browser-zoom.mjs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile, unlink, rmdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

const root=path.resolve(import.meta.dirname,'../..');
const folder=await mkdtemp(path.join(tmpdir(),'pvnetwork-qr-'));
const fixture=path.join(folder,'demo.html');
const failures=[];let cases=0;
let browser,server;
try {
 execFileSync(process.env.PV_PYTHON||'python3',[path.join(root,'tests/render_subscription_qr_fixture.py'),fixture]);
 const html=await readFile(fixture);
 const library=await readFile(path.join(root,'frontend/sub_clients/qr/qrcode.js'));
 server=createServer((request,response)=>{
  if(request.url==='/demo'){response.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});response.end(html);}
  else if(request.url==='/sub-assets/qr/qrcode.js'){response.writeHead(200,{'Content-Type':'application/javascript'});response.end(library);}
  else{response.writeHead(404);response.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin=`http://127.0.0.1:${server.address().port}`;
 browser=await zoomBrowser();
 for(const language of ['en','fa']) for(const theme of ['dark','light'])
  for(const zoom of [1,1.25,1.5]) for(const width of [390,1440]) {
   const page=await browser.context.newPage();const errors=[];
   const label=`${language} ${theme} ${width} zoom=${zoom}`;
   await page.setViewportSize({width,height:900});
   await page.addInitScript(({language,theme})=>{
    localStorage.setItem('pn_lang',language);localStorage.setItem('pn_theme',theme);
   },{language,theme});
   await page.route('**/*',route=>{
    const url=route.request().url();
    return url.startsWith(origin+'/')||url.startsWith('data:')?route.continue():route.abort();
   });
   page.on('pageerror',error=>errors.push(error.message));
   try {
    await page.goto(origin+'/demo',{waitUntil:'domcontentloaded'});
    await browser.setZoom(page,zoom);
    const button=page.locator('.node-qr').first();
    const expected=await button.evaluate(el=>({url:el.dataset.qrLink,name:el.dataset.qrName}));
    if(!expected.url||!expected.name)throw new Error('Dynamic QR data missing');
    for(const action of ['click','Enter','Space']) {
     if(action==='click')await button.click();
     else{await button.focus();await button.press(action);}
     const overlay=page.locator('#qrOverlay');await overlay.waitFor({state:'visible'});
     if(await page.evaluate(()=>window.pvnDemoXss===1))throw new Error('Node label executed as JavaScript');
     if(await page.locator('#qrCaption').textContent()!==expected.url)throw new Error('QR URL changed');
     if(!(await page.locator('#qrTitle').textContent()).includes(expected.name))throw new Error('QR display name changed');
     if(!await page.locator('#qrHolder svg').count())throw new Error('Vendored QR did not produce SVG');
     await page.keyboard.press('Escape');await overlay.waitFor({state:'hidden'});
     if(page.url()!==origin+'/demo')throw new Error('QR action followed the download anchor');
    }
    if(errors.length)throw new Error(errors.join('; '));
    cases++;
   } catch(error){failures.push(label+': '+error.message);}
   finally{await page.close();}
  }
} finally {
 await browser?.close();
 if(server)await new Promise(resolve=>server.close(resolve));
 await unlink(fixture).catch(error=>{if(error.code!=='ENOENT')throw error;});
 await rmdir(folder);
}
if(failures.length){console.error('SUBSCRIPTION_QR_SECURITY=FAIL\n'+failures.join('\n'));process.exitCode=1;}
else console.log(`SUBSCRIPTION_QR_SECURITY=PASS cases=${cases} actions=click,Enter,Space real_svg=true native_zooms=1,1.25,1.5`);
