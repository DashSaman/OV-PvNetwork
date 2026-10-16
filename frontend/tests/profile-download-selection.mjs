import { zoomBrowser } from './browser-zoom.mjs';
import { readFile } from 'node:fs/promises';

const base=(process.env.PV_UI_BASE_URL||'http://127.0.0.1:4173/panel').replace(/\/$/,'');
if(!/^http:\/\/127\.0\.0\.1:\d+\/panel$/.test(base))throw new Error('Owned loopback preview required');
const widths=process.env.PV_DOWNLOAD_PROBE?[1440]:[360,375,390,430,768,1024,1366,1440,1920];
const zooms=process.env.PV_DOWNLOAD_PROBE?[1]:[1,1.25,1.5];
const fixture='client\n# synthetic download-selection fixture; no keys or credentials\n';
const nodes=[{id:11,name:'Demo Offline',address:'offline.example.invalid',status:false},
 {id:41,name:'Demo Europe',address:'eu.example.invalid',status:true},
 {id:99,name:'Demo USA',address:'us.example.invalid',status:true}];
const user={id:1,uuid:'demo-user-001',name:'demo-user',owner:'demo-admin',total:0,used:0,
 expiry_date:'2030-01-01',is_active:true,device_limit:1,node_ids:[41,99]};
const browser=await zoomBrowser();let cases=0,downloads=0;
try{
 for(const language of ['en','fa'])for(const theme of ['light','dark'])for(const width of widths)for(const zoom of zooms){
  const page=await browser.context.newPage();await page.setViewportSize({width,height:1000});
  await page.addInitScript(({language,theme})=>{
   localStorage.setItem('authToken','demo.'+btoa(JSON.stringify({exp:Math.floor(Date.now()/1000)+3600,type:'main_admin'}))+'.signature');
   localStorage.setItem('userRole','main_admin');localStorage.setItem('pvnetwork_language',language);localStorage.setItem('ov-dashboard-theme',theme);
  },{language,theme});
  let mode='success';const requests=[];
  await page.route('**/api/**',async route=>{
   const path=new URL(route.request().url()).pathname;let data={};
   if(path==='/api/users/'||path==='/api/users')data=[user];
   if(path==='/api/nodes/'||path==='/api/nodes'){
    if(mode==='failed')return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetic unavailable node list'})});
    data=mode==='empty'?[]:nodes;
   }
   if(path.includes('/presence'))data={online_users:0,rates:{},counts:{}};
   if(path.includes('/nodes/health'))data=[];
   if(path.includes('/nodes/ovpn/')){
    requests.push(path);return route.fulfill({status:200,contentType:'application/x-openvpn-profile',body:fixture});
   }
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:true,data})});
  });
  await page.goto(base+'/users');await browser.setZoom(page,zoom);
  const open=async()=>{
   await page.locator('.actions-dropdown-trigger').first().click();
   await page.getByRole('menuitem',{name:/download|دانلود/i}).click();
   await page.locator('.modal').waitFor({state:'visible'});
  };
  for(const selected of [null,'99']){
   await open();await page.locator('#node-select option').first().waitFor({state:'attached'});
   if(selected)await page.locator('#node-select').selectOption(selected);
   else if(await page.locator('#node-select').inputValue()!=='41')throw new Error('First active node is not the selected ID');
   const result=page.waitForEvent('download',{timeout:5000});await page.locator('.modal .btn-success').click();
   const download=await result;const data=await readFile(await download.path(),'utf8');
   if(data!==fixture||download.suggestedFilename()!==`demo-user-${selected?'Demo USA':'Demo Europe'}.ovpn`)throw new Error('Unexpected browser download');
   if(requests.at(-1)!==`/api/nodes/ovpn/demo-user-001/${selected||'41'}/`)throw new Error('Wrong per-node profile request');
   await page.locator('.modal').waitFor({state:'hidden'});downloads++;
  }
  // Error/empty lists are distinct non-success paths; sample them in both languages/themes.
  if(width===widths[0]&&zoom===1)for(const failure of ['empty','failed']){
   mode=failure;const before=requests.length;await open();
   await page.waitForFunction(()=>!document.querySelector('#node-select')&&document.querySelector('.modal form p'));
   await page.locator('.modal .btn-success').click();
   await page.locator('.modal .error-message').waitFor({state:'visible'});
   if(requests.length!==before)throw new Error('Unavailable node list sent a profile request');
   await page.locator('.modal .btn-secondary').click();mode='success';
  }
  cases++;await page.close();
 }
 console.log(JSON.stringify({profile_download_selection:'PASS',cases,downloads,default_and_explicit_node_IDs:true,empty_and_failed_lists_no_request:true}));
}finally{await browser.close();}
