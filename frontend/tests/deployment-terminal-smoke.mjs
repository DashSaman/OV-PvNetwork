// Synthetic SSH jobs only: never connects to a node or trusts an observed key.
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {baseUrl,responseFor,demoToken} from './accessibility-fixtures.mjs';
import {renderedText,renderedFocus} from './rendered-contrast.mjs';
import {zoomBrowser} from './browser-zoom.mjs';
const zoom=process.env.PV_DEPLOY_NATIVE_ZOOM?await zoomBrowser():null;
const browser=zoom?zoom.context:await chromium.launch({headless:true,channel:'chromium'}),results=[];
const widths=(process.env.PV_DEPLOY_WIDTHS||'390,768,1440').split(',').map(Number);
try{for(const language of ['en','fa'])for(const theme of ['dark','light'])for(const width of widths){
 const forced=process.env.PV_DEPLOY_FORCED_COLORS==='active';
 const page=zoom?await browser.newPage():await browser.newPage({viewport:{width,height:Number(process.env.PV_DEPLOY_HEIGHT||900)},reducedMotion:'reduce',colorScheme:theme,forcedColors:forced?'active':'none'});
 if(zoom)await page.setViewportSize({width:1280,height:1000});
 await page.addInitScript(({language,theme,token})=>{localStorage.setItem('pvnetwork_language',language);localStorage.setItem('ov-dashboard-theme',theme);localStorage.setItem('authToken',token);localStorage.setItem('userRole','main_admin');},{language,theme,token:demoToken()});
 let state='running',payload,pollCount=0,postFailure=false;
 await page.route('**/*',route=>{
  const url=new URL(route.request().url());if(url.origin!==new URL(baseUrl).origin)return route.abort();
  if(url.pathname==='/api/nodes/deploy/'&&route.request().method()==='POST'){
   payload=route.request().postDataJSON();if(postFailure)return route.fulfill({status:400,json:{detail:'Synthetic request denied'}});return route.fulfill({json:{success:true,data:{job_id:'demo-deployment'}}});
  }
  if(url.pathname==='/api/nodes/deploy/demo-deployment/'){
   pollCount++;return route.fulfill({json:{success:true,data:{state,progress:state==='running'?10:100,created_at:Math.floor(Date.now()/1000),error:state==='failed'?'Unknown SSH host key for node.example.invalid. Verify it and retry.':null,logs:[{time:Math.floor(Date.now()/1000),level:state==='failed'?'error':'ok',message:state==='failed'?'Verify the SSH fingerprint through a trusted channel.':'Validating deployment request'}]}}});
  }
  if(url.pathname.startsWith('/api/'))return route.fulfill({json:responseFor(url.href)});
  return route.continue();
 });
 await page.goto(baseUrl+'/nodes',{waitUntil:'networkidle'});
 if(zoom){await zoom.setZoom(page,4);await page.addStyleTag({content:'*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}'});assert.equal(await page.evaluate(()=>innerWidth),320,'Native 400% must produce 320 CSS px');}
 const opener=page.locator('.view-header .btn').first();await opener.click();
 const form=page.getByRole('dialog');await form.locator('#name').fill('Demo existing node');await form.locator('#address').fill('node.example.invalid');
 await form.locator('#ssh_password').fill('synthetic-password');await form.locator('#controller_url').fill('https://controller.example.invalid');
 const firstPoll=page.waitForResponse(response=>response.url().endsWith('/api/nodes/deploy/demo-deployment/'));
 await form.locator('.modal-footer button').last().click();await firstPoll;
 const consoleDialog=page.getByRole('dialog',{name:/Node deployment|نصب نود/i});
 await consoleDialog.waitFor();assert.equal(await consoleDialog.count(),1,'Deployment must remain a named native modal');
 assert(await consoleDialog.evaluate(el=>el.tagName==='DIALOG'&&el.open&&el.contains(document.activeElement)),'Deployment focus must be in the modal');
 assert.equal(payload.ssh_fingerprint,null,'Never auto-trust a key from a failed request');
 assert.equal(payload.mode,'fresh');assert.equal(payload.ssh_password,'synthetic-password');
 await page.keyboard.press('Escape');assert(await consoleDialog.isVisible(),'Running job cannot be dismissed');
 for(let i=0;i<4;i++)await page.keyboard.press('Tab');
 assert(await consoleDialog.evaluate(el=>el.contains(document.activeElement)),'Tab must not reach background controls');
 const cdp=await page.context().newCDPSession(page),ax=await cdp.send('Accessibility.getFullAXTree');
 assert.equal(ax.nodes.filter(n=>!n.ignored&&n.role?.value==='dialog').length,1);
 assert(ax.nodes.some(n=>!n.ignored&&n.role?.value==='log'),'Deployment log must be exposed in the actual browser AX tree');
 assert.equal(await consoleDialog.getByRole('log').count(),1,'Progress output must expose log semantics');
 state='failed';await consoleDialog.getByRole('alert').waitFor();
 assert.match(await consoleDialog.getByRole('alert').innerText(),/Unknown SSH host key/);
 if(process.env.PV_DEPLOY_SCREENSHOTS){await mkdir(process.env.PV_DEPLOY_SCREENSHOTS,{recursive:true});await page.screenshot({path:path.join(process.env.PV_DEPLOY_SCREENSHOTS,`deployment-${language}-${theme}-${width}.png`)});}
 // Computed webkitTextFillColor retains author RGB under forced-color painting;
 // the normal-color raster helper cannot infer those used system ink colors.
 const text=zoom||forced?[]:await renderedText(page),lowText=text.filter(x=>!x.manual&&x.ratio<x.minimum-.01);assert.equal(lowText.length,0,'Console rendered text contrast: '+JSON.stringify(lowText.slice(0,4)));
 if(forced){assert(await page.evaluate(()=>matchMedia('(forced-colors:active)').matches));assert(await consoleDialog.evaluate(el=>[el,...el.querySelectorAll('*')].every(n=>getComputedStyle(n).forcedColorAdjust==='auto')),'Keep user-agent palette adjustment enabled');}
 const back=consoleDialog.getByRole('button',{name:/Back to form|بازگشت به فرم/i});await back.focus();if(forced){const focus=await renderedFocus(page);assert(focus.visible&&focus.ratio>=3,'Forced-color button focus');assert(await back.evaluate(el=>parseFloat(getComputedStyle(el).borderTopWidth)>=1),'Forced-color button boundary');}await page.keyboard.press('Enter');
 const retry=page.getByRole('dialog');await retry.locator('#ssh_password').waitFor();
 assert.equal(await retry.locator('#ssh_password').inputValue(),'','SSH secret must be cleared after submission');
 assert(await retry.evaluate(el=>el.contains(document.activeElement)),'Return-to-form focus must stay in its modal');
 assert(await retry.locator('#ssh_fingerprint').getAttribute('aria-describedby'),'First-contact trust needs an associated explanation');
 assert.equal(await retry.locator('#ssh_fingerprint').inputValue(),'','Reported fingerprints must not be copied into the trust input automatically');
 postFailure=true;await retry.locator('#ssh_password').fill('synthetic-retry');await retry.locator('.modal-footer button').last().click();
 await consoleDialog.getByRole('alert').waitFor();assert.match(await consoleDialog.getByRole('alert').innerText(),/Synthetic request denied/);
 await page.keyboard.press('Escape');await retry.locator('#ssh_password').waitFor();assert.equal(await retry.locator('#ssh_password').inputValue(),'','HTTP failures must also clear SSH secrets');
 await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);assert(await opener.evaluate(el=>el===document.activeElement),'Close must return to the original invoker');
 await opener.click();postFailure=false;state='succeeded';await retry.locator('#name').fill('Demo new node');await retry.locator('#address').fill('node.example.invalid');await retry.locator('#ssh_password').fill('synthetic-success');await retry.locator('#controller_url').fill('https://controller.example.invalid');await retry.locator('.modal-footer button').last().click();
 await consoleDialog.getByRole('button').waitFor();assert.equal(await consoleDialog.getByRole('alert').count(),0);assert(await consoleDialog.getByRole('status').innerText());
 assert(await consoleDialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Console must not require horizontal scrolling');
 await consoleDialog.getByRole('button').focus();await page.keyboard.press('Enter');assert.equal(await page.getByRole('dialog').count(),0);assert(await opener.evaluate(el=>el===document.activeElement),'Success must return to the original invoker');
 results.push({language,theme,width,pollCount,textObservations:text.length,namedDialog:true,actualBrowserAX:true,focusContained:true,errorAnnounced:true,secretCleared:true,invokerRestored:true});await page.close();
}}finally{if(zoom)await zoom.close();else await browser.close();}
if(process.env.PV_DEPLOY_REPORT){await mkdir(path.dirname(process.env.PV_DEPLOY_REPORT),{recursive:true});await writeFile(process.env.PV_DEPLOY_REPORT,JSON.stringify({cases:results.length,results},null,2));}
console.log('DEPLOYMENT_TERMINAL='+JSON.stringify({cases:results.length,failures:0}));
