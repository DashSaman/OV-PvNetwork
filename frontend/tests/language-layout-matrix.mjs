import { zoomBrowser } from './browser-zoom.mjs';
import { writeFile } from 'node:fs/promises';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4173/panel').replace(/\/$/, '');
const widths = [360, 375, 390, 430, 768, 1024, 1366, 1440, 1920];
const routes = ['/', '/users', '/nodes', '/admins', '/operations', '/security', '/fleet', '/monitoring', '/bandwidth'];
const languages = ['en','fa','ar','zh_CN','zh_TW','ja','ru','vi','es','id','uk','tr','pt_BR'];
const demoUser = {
  id: 1,
  uuid: 'demo-user-001',
  name: 'demo-user',
  owner: 'demo-admin',
  total: 0,
  used: 0,
  expiry_date: '2030-01-01',
  is_active: true,
  is_online: false,
  online_count: 0,
  device_limit: 1,
  anyconnect_enabled: false,
  node_ids: [1],
};

function responseFor(url) {
  const path = new URL(url).pathname.replace(/^\/api/, '');
  const ok = (data = {}) => ({ success: true, msg: 'ok', data });

  if (path === '/server/info') return ok({ cpu_usage: 12, memory_usage: 24, uptime: 7200, disk_usage: 31 });
  if (path === '/nodes/' || path === '/nodes') return ok([
    { id: 1, name: 'Demo Europe', status: true, drain: false, maintenance: false },
    { id: 2, name: 'Demo USA', status: true, drain: false, maintenance: false },
  ]);
  if (path.includes('/users/online')) return ok({ total: 0, per_node: {} });
  if (path === '/users/' || path === '/users') return ok([demoUser]);
  if (path.startsWith('/users')) return ok({});
  if (path === '/admin/' || path === '/admin') return ok([]);
  if (path.startsWith('/admins')) return ok([]);
  if (path.startsWith('/backups')) return ok({ backups: [] });
  if (path === '/fleet/' || path === '/fleet') return ok([]);
  if (path.startsWith('/fleet/jobs/')) return ok({ id: 'demo', state: 'succeeded', stage: 'done' });
  if (path === '/operations/dashboard') return ok({ users: 1, nodes: 0, online: 0, traffic_bytes: 0 });
  if (path === '/operations/audit') return ok([]);
  if (path.includes('/operations/users/') && path.includes('/history')) return ok([]);
  if (path.startsWith('/security')) return ok({
    rate_limit_enabled: true,
    rate_limit_per_minute: 120,
    ip_allowlist_enabled: false,
    ip_allowlist: [],
    totp_enabled: false,
    tokens: [],
  });
  if (path.startsWith('/server/monitoring')) return ok({
    enabled: false,
    telegram_configured: false,
    cpu_threshold: 90,
    memory_threshold: 90,
    disk_threshold: 90,
  });
  if (path === '/bandwidth/status') return ok([]);
  if (path === '/bandwidth/' || path === '/bandwidth') return ok({
    settings: { enabled: false, target_type: 'all', download_mbps: 1, node_ids: [] },
    nodes: [], users: [demoUser], owners: [], groups: [],
  });
  if (path.startsWith('/bandwidth')) return ok({});
  if (path === '/anyconnect/settings') return ok({ default_enabled: false });
  if (path === '/server/settings/' || path === '/server/settings') return ok({
    subscription_url_prefix: 'https://example.invalid/',
    subscription_path: 'sub',
  });
  if (path.includes('/settings') || path.includes('/setting')) return ok({});
  return ok({});
}

function demoToken() {
  const payload = Buffer.from(JSON.stringify({
    exp: Math.floor(Date.now() / 1000) + 3600,
    type: 'main_admin',
  })).toString('base64url');
  return `demo.${payload}.signature`;
}


const browser=await zoomBrowser();
const failures=[];let views=0;
const start=Date.now();
try {
for (const language of languages) {
 for (const theme of ['dark','light']) for (const zoom of [1,1.25,1.5]) for (const width of widths) {
  const page=await browser.context.newPage();const errors=[];
  await page.setViewportSize({width,height:width<=430?844:1000});
  await page.addInitScript(({language,theme,token})=>{
   localStorage.setItem('pvnetwork_language',language);localStorage.setItem('ov-dashboard-theme',theme);
   localStorage.setItem('authToken',token);localStorage.setItem('userRole','main_admin');
  },{language,theme,token:demoToken()});
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/api/**',async route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(responseFor(route.request().url()))}));
  try {
   for (const route of routes) {
    await page.goto(route==='/'?baseUrl+'/':baseUrl+route,{waitUntil:'domcontentloaded',timeout:10000});
    await browser.setZoom(page,zoom);
    await page.waitForTimeout(100);
    const metrics=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth,
     dir:document.documentElement.dir,lang:document.documentElement.lang,content:document.body.innerText.trim().length,
     controls:[...document.querySelectorAll('.header-actions > *')].map(el=>{const r=el.getBoundingClientRect();return {label:el.className,x:r.x,right:r.right,w:r.width,h:r.height};})}));
    const label=`${language} ${theme} ${width} zoom=${zoom} ${route}`;
    if(Math.abs(metrics.width-width/zoom)>1)failures.push(label+': native zoom viewport mismatch');
    if(metrics.scroll>metrics.width+1)failures.push(label+': page overflow');
    if(metrics.dir!==(['fa','ar'].includes(language)?'rtl':'ltr'))failures.push(label+': direction');
    if(metrics.lang.replace('-','_')!==language)failures.push(label+': document language');
    if(metrics.content<20)failures.push(label+': empty page');
    for(const c of metrics.controls)if(c.x < -1||c.right>metrics.width+1||c.w<43.99||c.h<43.99)failures.push(label+': header '+c.label+' '+JSON.stringify(c));
    views++;
   }
   if(errors.length)failures.push(`${language} ${theme} ${width} zoom=${zoom}: ${errors.join('; ')}`);
  } catch(error) { failures.push(`${language} ${theme} ${width} zoom=${zoom}: ${error.message}`); }
  finally { await page.close(); }
 }
 console.log('LANGUAGE_MATRIX_PROGRESS='+JSON.stringify({language,views,failures:failures.length,seconds:Math.round((Date.now()-start)/1000)}));
 if(process.env.PV_QA_REPORT)await writeFile(process.env.PV_QA_REPORT,JSON.stringify({views,failures,language,lastUpdate:new Date().toISOString()},null,2));
}
} finally { await browser.close(); }
console.log('LANGUAGE_MATRIX='+JSON.stringify({views,failures:failures.length,seconds:Math.round((Date.now()-start)/1000)}));
process.exitCode=failures.length?1:0;
