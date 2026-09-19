import { chromium } from 'playwright';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4173/panel').replace(/\/$/, '');
const failures = [];
const widths = [390, 1440];
const languages = ['en', 'fa'];
const users = [
  { id: 1, uuid: 'u1', name: 'alpha', owner: 'owner', total: 0, used: 0, expiry_date: '2030-01-01', is_active: true, is_online: true, online_count: 1, device_limit: 1, node_ids: [1] },
  { id: 2, uuid: 'u2', name: 'beta', owner: 'owner', total: 0, used: 0, expiry_date: '2030-01-01', is_active: true, is_online: true, online_count: 1, device_limit: 1, node_ids: [2] },
  { id: 3, uuid: 'u3', name: 'gamma', owner: 'owner', total: 0, used: 0, expiry_date: '2030-01-01', is_active: true, is_online: true, online_count: 1, device_limit: 1, node_ids: [1, 2] },
  { id: 4, uuid: 'u4', name: 'offline', owner: 'owner', total: 0, used: 0, expiry_date: '2030-01-01', is_active: true, is_online: false, online_count: 0, device_limit: 1, node_ids: [1] },
];
const nodes = [
  { id: 1, name: 'Demo Europe', status: true, drain: false, maintenance: false },
  { id: 2, name: 'Demo USA', status: true, drain: false, maintenance: false },
];
const ok = data => ({ success: true, msg: 'ok', data });
const token = () => {
  const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now()/1000)+3600, type: 'main_admin' })).toString('base64url');
  return `demo.${payload}.signature`;
};

for (const language of languages) {
  for (const width of widths) {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width, height: width < 500 ? 844 : 1000 } });
    await context.addInitScript(({ language, authToken }) => {
      localStorage.setItem('authToken', authToken);
      localStorage.setItem('userRole', 'main_admin');
      localStorage.setItem('pvnetwork_language', language);
    }, { language, authToken: token() });
    const page = await context.newPage();
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname.replace(/^\/api/, '');
      let payload = ok({});
      if (path === '/nodes/' || path === '/nodes') payload = ok(nodes);
      else if (path === '/users/' || path === '/users') payload = ok(users);
      else if (path === '/server/info') payload = ok({ cpu: 10, memory_total: 100, memory_used: 20, memory_percent: 20, disk_total: 100, disk_used: 20, disk_percent: 20, uptime: 1000 });
      else if (path === '/server/dashboard-live') payload = ok({
        presence: { online_users: 3, central_online_users: 2, direct_fallback_users: 1 },
        nodes: [
          { id: 1, available: true, rate_ready: true, rx_bytes: 1000, tx_bytes: 1000, download_bps: 1, upload_bps: 1, traffic_bytes: 2000, cpu_usage: 1, memory_usage: 1, uptime: 100, online_count: 3, online_sessions: 3 },
          { id: 2, available: true, rate_ready: true, rx_bytes: 1000, tx_bytes: 1000, download_bps: 1, upload_bps: 1, traffic_bytes: 2000, cpu_usage: 1, memory_usage: 1, uptime: 100, online_count: 2, online_sessions: 2 },
        ],
      });
      else if (path === '/anyconnect/settings') payload = ok({ default_enabled: false });
      else if (path === '/server/settings/' || path === '/server/settings') payload = ok({ subscription_url_prefix: 'https://example.invalid/', subscription_path: 'sub' });
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
    });

    try {
      await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      const dashboardBox = page.locator('.ov-metric-box').filter({ hasText: /Online Users/i }).first();
      await dashboardBox.waitFor({ state: 'visible', timeout: 5000 });
      await page.waitForTimeout(300);
      const dashboardValue = (await dashboardBox.locator('strong').textContent())?.trim();
      if (dashboardValue !== '3') failures.push(`${language} ${width}: dashboard=${dashboardValue}`);

      await page.goto(`${baseUrl}/users`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      const userCard = page.locator('.user-stat-card').filter({ has: page.locator('.user-stat-label').filter({ hasText: /Online Users|کاربران آنلاین/i }) }).first();
      await userCard.waitFor({ state: 'visible', timeout: 5000 });
      const usersValue = (await userCard.locator('.user-stat-value').textContent())?.trim();
      if (usersValue !== '3') failures.push(`${language} ${width}: users=${usersValue}`);
      if (dashboardValue !== usersValue) failures.push(`${language} ${width}: mismatch dashboard=${dashboardValue} users=${usersValue}`);
    } catch (error) {
      failures.push(`${language} ${width}: ${error.message}`);
    } finally {
      await context.close();
      await browser.close();
    }
  }
}

if (failures.length) {
  console.error('ONLINE_USER_TRUTH_SMOKE=FAIL');
  failures.forEach(item => console.error(`- ${item}`));
  process.exit(1);
}
console.log(`ONLINE_USER_TRUTH_SMOKE=PASS languages=${languages.length} widths=${widths.length}`);
