import { chromium } from 'playwright';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4173/panel').replace(/\/$/, '');
const failures = [];
const widths = [390, 1440];
const languages = ['en', 'fa'];

const nodes = [
  { id: 1, name: 'Demo Europe', address: '192.0.2.10', port: 9090, protocol: 'udp', ovpn_port: 1194, status: true },
  { id: 2, name: 'Old Node', address: '192.0.2.20', port: 9090, protocol: 'udp', ovpn_port: 1194, status: true },
];
const user = {
  id: 1, uuid: 'u1', name: 'alice', total: 0, used: 0, expiry_date: '2030-01-01',
  is_active: true, owner: 'owner', device_limit: 1, node_ids: [1], is_online: false,
};

function ok(data = {}) { return { success: true, msg: 'ok', data }; }
function token() {
  const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600, type: 'main_admin' })).toString('base64url');
  return `demo.${payload}.signature`;
}
function nodeRouterState(id) {
  if (Number(id) === 2) {
    return { configured: false, enabled: false, capable: false, healthy: false, upgrade_required: true, port: 1195, protocol: 'tcp', subnet: '10.9.0.0/24' };
  }
  return { configured: true, enabled: true, capable: true, healthy: true, upgrade_required: false, port: 1195, protocol: 'tcp', subnet: '10.9.0.0/24' };
}

for (const language of languages) {
  for (const width of widths) {
    let credentialCreated = false;
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width, height: width < 500 ? 844 : 1000 } });
    await context.addInitScript(({ language, authToken }) => {
      localStorage.setItem('authToken', authToken);
      localStorage.setItem('userRole', 'main_admin');
      localStorage.setItem('pvnetwork_language', language);
    }, { language, authToken: token() });
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    page.on('dialog', dialog => dialog.dismiss());
    await page.route('**/api/**', async route => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^\/api/, '');
      const method = request.method();
      let body = ok({});
      if (path === '/nodes/' || path === '/nodes') body = ok(nodes);
      else if (path === '/nodes/health/' || path === '/nodes/health') body = ok([]);
      else if (/^\/nodes\/\d+\/status\/?$/.test(path)) body = ok({ node_info: { cpu_usage: 1, memory_usage: 2 } });
      else if (path === '/users/' || path === '/users') body = ok([user]);
      else if (path === '/users/presence') body = ok({ online_users: 0, counts_by_uuid: {} });
      else if (path === '/anyconnect/settings') body = ok({ default_enabled: false });
      else if (path === '/server/settings/' || path === '/server/settings') body = ok({ subscription_url_prefix: 'https://example.invalid/', subscription_path: 'sub' });
      else if (/^\/router-openvpn\/nodes\/\d+$/.test(path)) {
        const id = Number(path.split('/').pop()); body = ok(nodeRouterState(id));
      } else if (path === '/router-openvpn/nodes/1/preflight' && method === 'POST') body = ok({ ok: true, port: 1195, protocol: 'tcp', subnet: '10.9.0.0/24' });
      else if (path === '/router-openvpn/nodes/1' && method === 'PUT') body = ok(nodeRouterState(1));
      else if (path === '/router-openvpn/users/u1/nodes/1' && method === 'GET') {
        body = ok({ user_uuid: 'u1', node_id: 1, node_name: 'Demo Europe', common_name: 'alice-Demo Europe', configured: credentialCreated, enabled: credentialCreated, username: credentialCreated ? 'r_demo_1' : null, password_available: false, listener_enabled: true });
      } else if (path === '/router-openvpn/users/u1/nodes/1/credential' && method === 'POST') {
        credentialCreated = true;
        body = ok({ user_uuid: 'u1', node_id: 1, node_name: 'Demo Europe', common_name: 'alice-Demo Europe', username: 'r_demo_1', password: 'OneTimePassword-Example-123456789', enabled: true, password_available: true });
      } else if (path === '/router-openvpn/users/u1/nodes/1/credential/status' && method === 'PUT') {
        body = ok({ enabled: false });
      } else if (path === '/router-openvpn/users/u1/nodes/1/profile' && method === 'GET') {
        await route.fulfill({ status: 200, contentType: 'application/x-openvpn-profile', body: 'client\nauth-user-pass\n' }); return;
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });

    try {
      await page.goto(`${baseUrl}/users`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      await page.locator('tbody tr').first().waitFor({ state: 'visible', timeout: 5000 });
      await page.locator('tbody tr').first().getByLabel('Open actions menu').click();
      await page.getByRole('menuitem', { name: /router|mikrotik|روتر|میکروتیک/i }).click();
      await page.locator('.router-openvpn-user-modal').waitFor({ state: 'visible', timeout: 5000 });
      const normalCopy = page.getByText(/normal openvpn remains certificate-only|OpenVPN معمولی.*نیاز ندارد/i);
      if (!(await normalCopy.count())) failures.push(`${language} ${width}: normal certificate-only explanation missing`);
      await page.getByRole('button', { name: /generate|rotate|ساخت|تغییر/i }).click();
      await page.locator('.router-openvpn-one-time-secret input[value="r_demo_1"]').waitFor({ state: 'visible', timeout: 5000 });
      await page.locator('.router-openvpn-one-time-secret input[value="OneTimePassword-Example-123456789"]').waitFor({ state: 'visible', timeout: 5000 });
      await page.getByRole('button', { name: /close|بستن/i }).last().click();

      await page.locator('tbody tr').first().getByLabel('Open actions menu').click();
      await page.getByRole('menuitem', { name: /router|mikrotik|روتر|میکروتیک/i }).click();
      await page.locator('.router-openvpn-user-modal').waitFor({ state: 'visible', timeout: 5000 });
      if (await page.locator('.router-openvpn-one-time-secret input[value="OneTimePassword-Example-123456789"]').count()) {
        failures.push(`${language} ${width}: one-time password survived modal reopen`);
      }
      await page.getByRole('button', { name: /close|بستن/i }).last().click();

      await page.goto(`${baseUrl}/nodes`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      const nodeRow = page.locator('tr', { hasText: 'Demo Europe' }).first();
      await nodeRow.waitFor({ state: 'visible', timeout: 5000 });
      await nodeRow.getByLabel('Open actions menu').click();
      await page.getByRole('menuitem', { name: /router|mikrotik|روتر|میکروتیک/i }).click();
      await page.locator('.router-openvpn-node-modal').waitFor({ state: 'visible', timeout: 5000 });
      await page.getByRole('button', { name: /preflight|بررسی/i }).click();
      await page.getByText(/preflight.*pass|بررسی.*موفق/i).waitFor({ state: 'visible', timeout: 5000 });
      const metrics = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
      if (metrics.sw > metrics.iw + 1) failures.push(`${language} ${width}: router modal horizontal overflow ${metrics.sw}>${metrics.iw}`);
      await page.getByRole('button', { name: /close|بستن/i }).last().click();
    } catch (error) {
      failures.push(`${language} ${width}: ${error.message}`);
    } finally {
      await context.close();
      await browser.close();
    }
  }
}

if (failures.length) {
  console.error('ROUTER_OPENVPN_SMOKE=FAIL');
  failures.forEach(item => console.error(`- ${item}`));
  process.exit(1);
}
console.log(`ROUTER_OPENVPN_SMOKE=PASS languages=${languages.length} widths=${widths.length}`);
