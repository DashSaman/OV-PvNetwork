import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';


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

  if (path === '/server/info') return ok({ cpu: 12, memory_percent: 24, memory_total: 100, memory_used: 24, uptime: 7200, disk_percent: 31, disk_total: 100, disk_used: 31 });
  if (path === '/server/dashboard-live') return ok({
    presence: { online_users: 0, central_online_users: 0, direct_fallback_users: 0 },
    nodes: [1,2].map(id => ({ id, available: true, rate_ready: true, rx_bytes: 9e9, tx_bytes: 11e9, download_bps: 12e6, upload_bps: 4e6, traffic_bytes: 20e9, cpu_usage: 18, memory_usage: 32, uptime: 7200, online_count: 0, online_sessions: 0 })),
  });
  if (path === '/nodes/health/' || path === '/nodes/health') return ok([]);
  if (/^\/nodes\/\d+\/status\/?$/.test(path)) return ok({node_info:{cpu_usage:12,memory_usage:24,uptime:7200}});
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
  if (path === '/operations/dashboard') return ok({ users: 1, nodes: 2, online: 0, traffic_bytes: 0 });
  if (path === '/operations/audit') return ok([]);
  if (path.includes('/operations/users/') && path.includes('/history')) return ok([]);
  if (path === '/security/panel-settings') return ok({username:'demo-admin',panel_path:'panel',panel_port:19000,redirect:null,active_change:null});
  if (path.startsWith('/security')) return ok({
    rate_limit_enabled: true,
    rate_limit_per_minute: 120,
    ip_allowlist_enabled: false,
    allowed_cidrs: [],
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



const root=path.resolve(import.meta.dirname,'../../docs/images/v1.0.50');
const browser=await chromium.launch({headless:true});let captures=0;
try {
for(const language of ['en','fa']) for(const width of [390,1440]) {
 const theme=language==='fa'?'dark':'light';
 const context=await browser.newContext({viewport:{width,height:width===390?844:1000},reducedMotion:'reduce'});
 await context.addInitScript(({language,theme,token})=>{
  localStorage.setItem('pvnetwork_language',language);localStorage.setItem('ov-dashboard-theme',theme);
  localStorage.setItem('authToken',token);localStorage.setItem('userRole','main_admin');
 },{language,theme,token:demoToken()});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>{
  const url=route.request().url();
  if(url.startsWith(baseUrl.split('/panel')[0]+'/api/')) return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(responseFor(url))});
  return url.startsWith(baseUrl.split('/panel')[0]+'/')||url.startsWith('data:')?route.continue():route.abort();
 });
 const folder=path.join(root,language,width===390?'mobile':'desktop');await mkdir(folder,{recursive:true});
 const capture=async name=>{await page.waitForTimeout(500);await page.locator('.ov-page-loader').waitFor({state:'hidden',timeout:5000});await page.screenshot({path:path.join(folder,name+'.png'),fullPage:true});captures++;};
 for(const route of routes){
  await page.goto(route==='/'?baseUrl+'/':baseUrl+route,{waitUntil:'domcontentloaded'});
  await capture(route==='/'?'dashboard':route.slice(1));
 }
 await page.goto(baseUrl+'/users',{waitUntil:'domcontentloaded'});
 await page.locator('.actions-dropdown-trigger').first().click();
 await page.getByRole('menuitem',{name:/quick edit|ویرایش سریع/i}).click();
 await page.locator('.inline-user-quick-edit').waitFor({state:'visible'});await capture('quick-edit');
 await page.locator('.quick-edit-cancel').click();
 await page.getByRole('button',{name:/add new user|افزودن کاربر|ایجاد کاربر/i}).first().click();
 await page.locator('.modal').last().waitFor({state:'visible'});await capture('user-create');
 await page.goto(baseUrl+'/nodes',{waitUntil:'domcontentloaded'});
 await page.locator('#nodes-view .view-header .btn').first().click();
 await page.locator('#ssh_fingerprint').waitFor({state:'visible'});await capture('node-create');
 if(errors.length)throw new Error(errors.join('; '));await context.close();
}
}finally{await browser.close();}
console.log('CURRENT_DEMO_CAPTURES=PASS captures='+captures);
