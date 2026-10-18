// Actual rendered backgrounds supplement axe's unresolved gradients/pseudo layers.
// Synthetic loopback fixtures; this does not run a screen reader or certify WCAG.
import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {baseUrl,responseFor,demoToken,routes} from './accessibility-fixtures.mjs';
import {renderedText,controlEdges,renderedFocus,renderedGradientText} from './rendered-contrast.mjs';
if(!/^http:\/\/127\.0\.0\.1:\d+\/panel$/.test(baseUrl))throw Error('Owned loopback preview required');
const browser=await chromium.launch({headless:true,channel:'chromium'}),results=[],failures=[],manual=[];
const widths=(process.env.PV_MANUAL_WIDTHS||'390,1440').split(',').map(Number);
const languages=(process.env.PV_MANUAL_LANGUAGES||'en,fa').split(',');
const scanRoutes=process.env.PV_MANUAL_ROUTES?process.env.PV_MANUAL_ROUTES.split(','):routes;
if(scanRoutes.some(route=>!routes.includes(route)))throw Error('Unknown manual-review route');
const cases=[['node-archive','/nodes',/Node backup.*restore|بکاپ.*بازیابی نود/i],['add-user','/users',null],['edit-user','/users',/^(edit|ویرایش)$/i],['renew-user','/users',/renew|تمدید/i],['download','/users',/download|دانلود/i],['domain-history','/users',/domain history/i],['add-node','/nodes',null]];
const healthRows=['healthy','degraded','offline','disabled'].map((health,index)=>({id:index+1,name:`Demo node ${index+1}`,address:`node-${index+1}.example.invalid`,health,weight:100,score:80,cpu_usage:12,memory_usage:24,api_latency_ms:5,central_online_users:0,central_active_sessions:0,drain:index===1}));
function populatedResponse(url){
 const pathname=new URL(url).pathname;
 if(/^\/api\/nodes\/health\/?$/.test(pathname))return {success:true,data:healthRows};
 if(pathname==='/api/operations/audit')return {success:true,data:[true,false].map((success,index)=>({id:index+1,created_at:1790000000,actor:'demo-admin',action:'demo.check',resource:'synthetic',success,ip_address:'192.0.2.1'}))};
 return responseFor(url);
}
// Real-browser controls ensure the measurement itself can fail, including a
// contrasting fill, alpha text, a pseudo layer and a clipped invisible label.
const calibration=await browser.newPage({viewport:{width:800,height:600}});
await calibration.setContent('<style>body{background:white}p{font:16px Arial;position:relative}#good{color:black}#bad{color:#999}#alpha{color:black;opacity:.35}#gradient{color:white;background:linear-gradient(90deg,#fff,#eee)}#pseudo{color:#999}#pseudo::before{content:"";position:absolute;inset:0;background:#fff;z-index:-1}</style><p id="good">Good text</p><p id="bad">Low contrast</p><p id="alpha">Alpha text</p><p id="gradient">Gradient text</p><p id="pseudo">Pseudo text</p><div style="height:0;overflow:hidden"><p id="clipped">Clipped text</p></div><input id="low-edge" style="background:#111;border:1px solid #222"><input id="fill-edge" style="background:white;border:1px solid #222"><style>input{margin:15px;padding:10px}body{background:#111}p{background:white}</style>');
const proof=await renderedText(calibration),byId=id=>proof.find(x=>x.selector==='#'+id);
if(byId('good').ratio<20||['bad','alpha','gradient','pseudo'].some(id=>byId(id).ratio>=4.5)||byId('clipped'))throw Error('Rendered text measurement negative controls failed');
const edgeProof=await controlEdges(calibration,'input');
if(edgeProof[0].ratio>=3||edgeProof[1].ratio<3)throw Error('Rendered boundary/fill measurement negative controls failed');
await calibration.close();
const gradientCalibration=await browser.newPage({viewport:{width:800,height:600}});
await gradientCalibration.setContent('<style>body{background:#050505}.gradient{font:48px Arial;width:400px;background-clip:text!important;-webkit-background-clip:text!important;-webkit-text-fill-color:transparent}</style><div id="gradient-good" class="gradient" style="background:linear-gradient(90deg,#fff,#93c5fd)">Good gradient</div><div id="gradient-bad" class="gradient" style="background:linear-gradient(90deg,#050505,#333)">Bad gradient</div>');
if((await renderedGradientText(gradientCalibration,'#gradient-good')).ratio<3||(await renderedGradientText(gradientCalibration,'#gradient-bad')).ratio>=3)throw Error('Gradient raster bounds negative controls failed');
await gradientCalibration.close();
try{for(const language of languages)for(const theme of ['dark','light'])for(const width of widths){
 const page=await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'});
 await page.addInitScript(({language,theme,token})=>{localStorage.setItem('pvnetwork_language',language);localStorage.setItem('ov-dashboard-theme',theme);localStorage.setItem('authToken',token);localStorage.setItem('userRole','main_admin');},{language,theme,token:demoToken()});
 await page.route('**/*',route=>{const url=new URL(route.request().url());if(url.origin!==new URL(baseUrl).origin)return route.abort();if(url.pathname.startsWith('/api/'))return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(populatedResponse(url.href))});return route.continue();});
 const navigate=async route=>{await page.goto(baseUrl+route,{waitUntil:'networkidle'});if(page.url().replace(/\/$/,'')!==(baseUrl+route).replace(/\/$/,''))throw Error('Wrong actual route');};
 async function inspect(label){
  const text=await renderedText(page),edges=await controlEdges(page,'input:not([type=checkbox]):not([type=radio]),select,textarea');
  const record={label:`${language}/${theme}/${width}/${label}`,text,edges};results.push(record);
  if(text.some(x=>x.manual&&x.selector==='div.ov-hero-value')){record.gradientText=await renderedGradientText(page,'.ov-hero-value');if(record.gradientText.ratio<3)failures.push({label:record.label,type:'gradient-text',...record.gradientText});}
  for(const x of text)if(x.manual)manual.push({label:record.label,...x});else if(x.ratio<x.minimum-.01)failures.push({label:record.label,type:'text',...x});
  for(const x of edges)if(x.border&&x.ratio!==null&&x.ratio<3)failures.push({label:record.label,type:'control-boundary',...x});
 }
 async function scrollInspect(label){
  for(const fraction of [.5,1]){
   await page.evaluate(fraction=>{for(const el of new Set([document.scrollingElement,...document.querySelectorAll('*')])){if(!el||el.clientHeight<100)continue;const s=getComputedStyle(el);if(el===document.scrollingElement||/auto|scroll/.test(s.overflowY))el.scrollTop=(el.scrollHeight-el.clientHeight)*fraction;if(/auto|scroll/.test(s.overflowX))el.scrollLeft=(s.direction==='rtl'?-1:1)*(el.scrollWidth-el.clientWidth)*fraction;}},fraction);
   await inspect(`${label}/scroll-${fraction}`);
  }
 }
 for(const route of scanRoutes){await navigate(route);await inspect(route);if(route==='/nodes'&&await page.getByRole('spinbutton',{name:/weight|وزن/i}).count()!==4)failures.push({label:`${language}/${theme}/${width}/node-weights`,type:'accessible-name',expected:4});await scrollInspect(route);}
 for(const [name,route,action] of process.env.PV_MANUAL_DIALOGS==='0'?[]:cases){await navigate(route);if(action){await page.locator('.actions-dropdown-trigger').first().click();await page.getByRole('menuitem',{name:action}).click();}else await page.locator('.view-header .btn').first().click();await page.locator('dialog').waitFor();await inspect(name);if(name==='node-archive'){await page.keyboard.press('Tab');const focus=await renderedFocus(page);results.at(-1).gradientFocus=focus;if(!focus.visible||focus.ratio<3)failures.push({label:`${language}/${theme}/${width}/gradient-focus`,...focus});}await page.keyboard.press('Escape');}
 await page.close();
}}finally{await browser.close();}
const summary={measurementFixtures:10,states:results.length,textObservations:results.reduce((n,r)=>n+r.text.length,0),boundaries:results.reduce((n,r)=>n+r.edges.filter(x=>x.border&&x.ratio!==null).length,0),gradientFocus:results.filter(r=>r.gradientFocus).length,gradientTextBounds:results.filter(r=>r.gradientText).length,failures:failures.length,manual:manual.length,firstFailures:failures.slice(0,8)};
if(process.env.PV_MANUAL_REPORT){const file=process.env.PV_MANUAL_REPORT;await mkdir(path.dirname(file),{recursive:true});await writeFile(file,JSON.stringify({summary,failures,manual,results},null,2));}
console.log('RENDERED_ACCESSIBILITY='+JSON.stringify(summary));if(failures.length)process.exitCode=1;
