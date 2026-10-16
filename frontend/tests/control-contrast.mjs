import { zoomBrowser } from './browser-zoom.mjs';



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




const browser=await zoomBrowser();let cases=0,controls=0;const failures=[];
const sampleWidths=process.env.PV_CONTRAST_PROBE? [1440]:widths;
const sampleZooms=process.env.PV_CONTRAST_PROBE? [1]:[1,1.25,1.5];
try {
for(const language of ['en','fa']) for(const theme of ['light','dark'])
 for(const width of sampleWidths) for(const zoom of sampleZooms){
 const page=await browser.context.newPage();await page.setViewportSize({width,height:1000});
 await page.addInitScript(({language,theme,token})=>{
  localStorage.setItem('pvnetwork_language',language);localStorage.setItem('ov-dashboard-theme',theme);
  localStorage.setItem('authToken',token);localStorage.setItem('userRole','main_admin');
 },{language,theme,token:demoToken()});
 await page.route('**/api/**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(responseFor(route.request().url()))}));
 const check=async label=>{
  const result=await page.locator('main :is(input:not([type="checkbox"]):not([type="radio"]):not([type="range"]):not([type="hidden"]),select,textarea),.modal :is(input:not([type="checkbox"]):not([type="radio"]),select,textarea)').evaluateAll(elements=>{
   const rgba=value=>{const n=value.match(/[\d.]+/g)?.map(Number);if(!n||n.length<3)throw new Error('Unsupported computed color '+value);return [...n.slice(0,3),n[3]??1];};
   const blend=(fg,bg)=>fg.slice(0,3).map((v,i)=>v*fg[3]+bg[i]*(1-fg[3]));
   const luminance=rgb=>rgb.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
   const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
   return [...elements,...document.querySelectorAll('main .view-header h2')].filter(el=>el.getClientRects().length&&!el.disabled).map(el=>{
    const style=getComputedStyle(el),background=rgba(style.backgroundColor),foreground=rgba(style.color);
    // Bound translucency against both extremes: no guessed ancestor/gradient color.
    const heading=el.matches('.view-header h2');
    const paints=heading?[...getComputedStyle(el.closest('.view-header')).backgroundImage.matchAll(/rgba?\([^)]*\)/g)].map(match=>rgba(match[0])):[background];
    if(!paints.length)throw new Error('Heading gradient colors unavailable');
    const ratios=paints.flatMap(paint=>[[0,0,0],[255,255,255]].map(base=>{const bg=blend(paint,base);return contrast(blend(foreground,bg),bg);}));
    const placeholder=el.placeholder?rgba(getComputedStyle(el,'::placeholder').color):null;
    const placeholderRatios=placeholder?[[0,0,0],[255,255,255]].map(base=>{const bg=blend(background,base);return contrast(blend(placeholder,bg),bg);}):[];
    return {tag:el.tagName,type:el.type,id:el.id,foreground:style.color,background:heading?getComputedStyle(el.closest('.view-header')).backgroundImage:style.backgroundColor,threshold:heading?3:4.5,minimum:Math.min(...ratios),maximum:Math.max(...ratios),placeholderMinimum:placeholderRatios.length?Math.min(...placeholderRatios):null};
   });
  });
  controls+=result.length;
  for(const item of result)if(item.minimum<item.threshold||item.placeholderMinimum!==null&&item.placeholderMinimum<4.5)failures.push({label,...item});
 };
 try {
  for(const route of ['/users','/nodes','/security','/monitoring','/bandwidth']){
   await page.goto(baseUrl+route,{waitUntil:'domcontentloaded'});await browser.setZoom(page,zoom);
   await page.waitForTimeout(150);await page.locator('.ov-page-loader').waitFor({state:'hidden',timeout:5000});
   const label=`${language} ${theme} ${width} zoom=${zoom} ${route}`;
   await check(label);
   const field=page.locator('input:not([type="checkbox"]):not([type="radio"]):visible,textarea:visible,select:visible').first();
   if(await field.count()){await field.focus();await check(label+' focused');}
   if(route==='/nodes'){
    await page.locator('#nodes-view .view-header .btn').first().click();await page.locator('#ssh_fingerprint').waitFor();
    await page.locator('#name').fill('Demo contrast node');await check(label+' create dialog');
   }
  }
  cases++;
 }catch(error){failures.push({label:`${language} ${theme} ${width} ${zoom}`,error:error.message});}
 finally{await page.close();}
}
}finally{await browser.close();}
console.log('CONTROL_CONTRAST='+JSON.stringify({cases,controls,failures:failures.length,firstFailures:failures.slice(0,5)}));
process.exitCode=failures.length?1:0;
