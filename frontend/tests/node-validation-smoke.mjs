// Synthetic response fixtures only; no SSH, node job or customer mutation.
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {baseUrl,responseFor,demoToken} from './accessibility-fixtures.mjs';
import {renderedText,renderedFocus} from './rendered-contrast.mjs';
import {zoomBrowser} from './browser-zoom.mjs';
const zoom=process.env.PV_NODE_VALIDATION_ZOOMS?await zoomBrowser():null;
const browser=zoom?zoom.context:await chromium.launch({headless:true,channel:'chromium'}),results=[];
const quick=Boolean(process.env.PV_NODE_VALIDATION_QUICK);
const widths=(process.env.PV_NODE_VALIDATION_WIDTHS||'390,768,1440').split(',').map(Number);
const zooms=(process.env.PV_NODE_VALIDATION_ZOOMS||'1').split(',').map(Number);
let measurementFixtures=0;
const settledDialog = dialog => dialog.evaluate(async el=>{
 await document.fonts.ready;
 // A screenshot finishes finite animations. Capture coordinates at that same
 // settled paint, rather than sampling the background at an old modal position.
 await Promise.all(el.getAnimations({subtree:true}).filter(a=>Number.isFinite(a.effect.getComputedTiming().endTime)).map(a=>a.finished.catch(()=>{})));
});
const languages=quick?['en']:['en','fa'],themes=quick?['light']:['dark','light'];
try{for(const language of languages)for(const theme of themes)for(const width of widths)for(const factor of zooms){
 const forced=process.env.PV_NODE_VALIDATION_FORCED==='1';
 const page=zoom?await browser.newPage():await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce',colorScheme:theme,forcedColors:forced?'active':'none'});
 if(zoom)await page.setViewportSize({width,height:1000});
 await page.addInitScript(({language,theme,token})=>{localStorage.setItem('pvnetwork_language',language);localStorage.setItem('ov-dashboard-theme',theme);localStorage.setItem('authToken',token);localStorage.setItem('userRole','main_admin');},{language,theme,token:demoToken()});
 const secret='synthetic-ssh-secret-not-for-error-output';let posts=0,shape='array',manual=false;
 await page.route('**/*',route=>{
  const request=route.request(),url=new URL(request.url());if(url.origin!==new URL(baseUrl).origin)return route.abort();
  if(request.method()==='POST'&&(url.pathname==='/api/nodes/deploy/'||url.pathname==='/api/nodes/')){
   posts++;const port=manual?'port':'ssh_port';
   const bodies={array:{detail:[{loc:['body',port],type:'greater_than_equal',msg:'Input should be greater than or equal to 1',input:secret,ctx:{sensitive:secret}},{loc:['body','controller_url'],msg:'Use a valid controller HTTPS origin',input:secret}]},string:{detail:'Trusted host verification required'},object:{detail:{message:'Readable node deployment rejection',input:secret,ctx:{sensitive:secret}}},unknown:{detail:{input:secret,ctx:{sensitive:secret}},msg:'Safe request fallback'}};
   return route.fulfill({status:422,json:bodies[shape]});
  }
  if(url.pathname.startsWith('/api/'))return route.fulfill({json:responseFor(url.href)});
  return route.continue();
 });
 await page.goto(baseUrl+'/nodes',{waitUntil:'networkidle'});
 if(zoom){await zoom.setZoom(page,factor);assert(Math.abs(await page.evaluate(()=>innerWidth)-width/factor)<2,'Apply actual browser zoom');if(factor===4)await page.addStyleTag({content:'*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}'});}
 const opener=page.locator('.view-header .btn').first();await opener.click();
 let form=page.getByRole('dialog');await form.locator('#name').fill('Demo validation node');await form.locator('#address').fill('node.example.invalid');await form.locator('#controller_url').fill('https://controller.example.invalid');
 for(const kind of ['array','string','object','unknown']){
  shape=kind;await form.locator('#ssh_password').fill(secret);await form.locator('.modal-footer button').last().click();
  const consoleDialog=page.getByRole('dialog',{name:/Node deployment|نصب نود/i}),alert=consoleDialog.getByRole('alert');await alert.waitFor();
  const message=await alert.innerText();assert(!message.includes('[object Object]'),'Structured validation must produce field messages, not [object Object]');assert(!message.includes(secret),'Do not serialize input or ctx into an error');
  if(kind==='array'){
   assert.match(message,/Input should be greater than or equal to 1/);assert.match(message,/Use a valid controller HTTPS origin/);
   const label=language==='fa'?'پورت SSH':'SSH Port';assert(message.includes(label),'Include the translated field label: '+message);
   assert(await consoleDialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Long field messages must wrap');
   if(!forced&&!zoom){
    if(!quick&&language==='en'&&theme==='light'&&width===390){
     await consoleDialog.evaluate(el=>el.animate([{transform:'translateX(120px)'},{transform:'translateX(0)'}],{duration:1500}));
     const moving=await renderedText(page);assert(moving.some(x=>!x.manual&&x.ratio<x.minimum-.01),'Negative control must expose stale animation coordinates');measurementFixtures++;
    }
    await settledDialog(consoleDialog);
    const text=await renderedText(page);assert.deepEqual(text.filter(x=>!x.manual&&x.ratio<x.minimum-.01),[],`Rendered error contrast (${language}/${theme}/${width})`);measurementFixtures++;
   }
   if(forced){assert(await page.evaluate(()=>matchMedia('(forced-colors:active)').matches));await page.keyboard.press('Tab');const back=consoleDialog.getByRole('button');await back.focus();const focus=await renderedFocus(page);assert(focus.visible&&focus.ratio>=3,JSON.stringify(focus));}
  }else assert.match(message,kind==='string'?/Trusted host verification required/:kind==='object'?/Readable node deployment rejection/:/Safe request fallback/);
  assert(await consoleDialog.evaluate(el=>el.open&&el.contains(document.activeElement)),'Keep native focus containment');
  assert(!await consoleDialog.getByRole('log').innerText().then(text=>text.includes(secret)));
  if(kind==='array'&&process.env.PV_NODE_VALIDATION_SCREENSHOTS){await mkdir(process.env.PV_NODE_VALIDATION_SCREENSHOTS,{recursive:true});await consoleDialog.screenshot({path:path.join(process.env.PV_NODE_VALIDATION_SCREENSHOTS,`validation-${language}-${theme}-${width}.png`)});}
  await consoleDialog.getByRole('button',{name:/Back to form|بازگشت به فرم/i}).click();form=page.getByRole('dialog');await form.locator('#ssh_password').waitFor();assert.equal(await form.locator('#ssh_password').inputValue(),'');assert.equal(await form.locator('#ssh_fingerprint').inputValue(),'');
 }
 await page.keyboard.press('Escape');assert(await opener.evaluate(el=>el===document.activeElement),'Restore the original invoker');
 await opener.click();form=page.getByRole('dialog');manual=true;shape='array';await form.locator('#node-install-method').selectOption('manual');await form.locator('#name').fill('Demo manual node');await form.locator('#address').fill('node.example.invalid');await form.locator('#key').fill(secret);await form.locator('.modal-footer button').last().click();
 const manualMessage=await form.locator('.error-message').innerText();assert.match(manualMessage,/Input should be greater than or equal to 1/);assert(!manualMessage.includes('[object Object]')&&!manualMessage.includes(secret));
 await page.keyboard.press('Escape');assert(await opener.evaluate(el=>el===document.activeElement));assert.equal(posts,5);
 results.push({language,theme,width,zoom:factor,forcedColors:forced,responseShapes:4,manualRegistration:true,fieldMessages:true,secretInputAndContextExcluded:true,focusAndSecretClearing:true});await page.close();
}}finally{if(zoom)await zoom.close();else await browser.close();}
if(process.env.PV_NODE_VALIDATION_REPORT){await mkdir(path.dirname(process.env.PV_NODE_VALIDATION_REPORT),{recursive:true});await writeFile(process.env.PV_NODE_VALIDATION_REPORT,JSON.stringify({cases:results.length,results,measurementFixtures,failures:0},null,2));}
console.log('NODE_VALIDATION='+JSON.stringify({cases:results.length,responseShapes:4,measurementFixtures,failures:0}));
