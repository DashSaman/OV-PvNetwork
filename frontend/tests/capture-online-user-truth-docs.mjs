import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4212/panel').replace(/\/$/, '');
const root = path.resolve('..', 'docs', 'images', 'v1.0.7');
const users = [
  { id: 1, uuid: 'demo-a', name: 'demo-alpha', owner: 'owner', total: 0, used: 0, expiry_date: '2030-01-01', is_active: true, is_online: true, online_count: 1, device_limit: 1, node_ids: [1] },
  { id: 2, uuid: 'demo-b', name: 'demo-beta', owner: 'owner', total: 0, used: 0, expiry_date: '2030-01-01', is_active: true, is_online: true, online_count: 1, device_limit: 1, node_ids: [2] },
  { id: 3, uuid: 'demo-c', name: 'demo-gamma', owner: 'owner', total: 0, used: 0, expiry_date: '2030-01-01', is_active: true, is_online: true, online_count: 1, device_limit: 1, node_ids: [1,2] },
  { id: 4, uuid: 'demo-d', name: 'demo-offline', owner: 'owner', total: 0, used: 0, expiry_date: '2030-01-01', is_active: true, is_online: false, online_count: 0, device_limit: 1, node_ids: [1] },
];
const nodes = [
  { id: 1, name: 'Demo Europe', status: true, drain: false, maintenance: false },
  { id: 2, name: 'Demo USA', status: true, drain: false, maintenance: false },
];
const ok = data => ({ success: true, msg: 'ok', data });
function token() {
  const p = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now()/1000)+3600, type: 'main_admin' })).toString('base64url');
  return `demo.${p}.signature`;
}
async function mock(page) {
  await page.route('**/api/**', async route => {
    const p = new URL(route.request().url()).pathname.replace(/^\/api/, '');
    let payload = ok({});
    if (p === '/nodes/' || p === '/nodes') payload = ok(nodes);
    else if (p === '/users/' || p === '/users') payload = ok(users);
    else if (p === '/users/presence') payload = ok({ counts_by_uuid: { 'demo-a': 1, 'demo-b': 1, 'demo-c': 1 }, online_users: 3, sample_time: 1234567890 });
    else if (p === '/server/info') payload = ok({ cpu: 10, memory_total: 100, memory_used: 20, memory_percent: 20, disk_total: 100, disk_used: 20, disk_percent: 20, uptime: 7200 });
    else if (p === '/server/dashboard-live') payload = ok({
      presence: { online_users: 3, central_online_users: 2, direct_fallback_users: 1 },
      nodes: [
        { id: 1, available: true, rate_ready: true, rx_bytes: 9e9, tx_bytes: 11e9, download_bps: 12e6, upload_bps: 4e6, traffic_bytes: 20e9, cpu_usage: 18, memory_usage: 32, uptime: 7200, online_count: 3, online_sessions: 3 },
        { id: 2, available: true, rate_ready: true, rx_bytes: 7e9, tx_bytes: 8e9, download_bps: 8e6, upload_bps: 3e6, traffic_bytes: 15e9, cpu_usage: 11, memory_usage: 28, uptime: 8600, online_count: 2, online_sessions: 2 },
      ],
    });
    else if (p === '/anyconnect/settings') payload = ok({ default_enabled: false });
    else if (p === '/server/settings/' || p === '/server/settings') payload = ok({ subscription_url_prefix: 'https://demo.example.invalid/', subscription_path: 'sub' });
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  });
}
const browser = await chromium.launch({ headless: true });
for (const language of ['en','fa']) {
  for (const item of [
    { kind: 'desktop', width: 1440, height: 1000, route: '/', file: 'online-truth-dashboard.png' },
    { kind: 'mobile', width: 390, height: 844, route: '/users', file: 'online-truth-users.png' },
  ]) {
    const context = await browser.newContext({ viewport: { width: item.width, height: item.height }, reducedMotion: 'reduce' });
    await context.addInitScript(({ language, authToken }) => {
      localStorage.setItem('authToken', authToken);
      localStorage.setItem('userRole', 'main_admin');
      localStorage.setItem('pvnetwork_language', language);
    }, { language, authToken: token() });
    const page = await context.newPage();
    await mock(page);
    await page.goto(`${baseUrl}${item.route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    const out = path.join(root, language, item.kind, item.file);
    await fs.mkdir(path.dirname(out), { recursive: true });
    await page.screenshot({ path: out, fullPage: true });
    console.log(out);
    await context.close();
  }
}
await browser.close();
