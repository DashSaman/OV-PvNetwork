import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base = process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4188/panel';
const widths = [360, 375, 390, 430, 768, 1024, 1366, 1440, 1920];
const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600, type: 'main_admin' })).toString('base64url');
const browser = await chromium.launch({ headless: true });
try {
  for (const language of ['en', 'fa']) for (const width of widths) {
    const context = await browser.newContext({ viewport: { width, height: 950 } });
    await context.addInitScript(({ language, token }) => { localStorage.setItem('pvnetwork_language', language); localStorage.setItem('authToken', token); localStorage.setItem('userRole', 'main_admin'); }, { language, token: `demo.${payload}.signature` });
    const page = await context.newPage(); page.setDefaultTimeout(7000); const errors = []; const changes = [];
    page.on('pageerror', error => errors.push(error.message)); page.on('dialog', dialog => dialog.accept());
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      let data = {};
      if (/\/nodes\/?$/.test(path)) data = [{ id: 7, name: 'demo-node', address: 'node.example.invalid', 'tunnel-address': 'vpn.example.invalid', port: 9443, ovpn_port: 1194, protocol: 'udp', status: 'active' }];
      else if (path.endsWith('/health/')) data = [];
      if (route.request().method() === 'PUT') changes.push(JSON.parse(route.request().postData()));
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, data, msg: 'ok' }) });
    });
    try {
      await page.goto(`${base}/nodes`, { waitUntil: 'networkidle' });
      await page.locator('.actions-dropdown-trigger').click(); await page.getByRole('menuitem').first().click();
      const modal = page.locator('.modal-overlay .modal'); await modal.waitFor();
      assert.equal(await modal.locator('#edit-key').getAttribute('required'), null, 'Unchanged private key must not be requested');
      assert.equal(await modal.locator('#edit-key').getAttribute('type'), 'password');
      assert.equal(await modal.locator('#edit-tunnel_address').inputValue(), 'vpn.example.invalid');
      await modal.locator('#edit-name').fill('demo-renamed'); await modal.locator('.modal-footer button').last().click();
      await modal.waitFor({ state: 'detached' });
      assert.equal(changes.length, 1); assert.equal(changes[0].name, 'demo-renamed'); assert.equal(changes[0].tunnel_address, 'vpn.example.invalid');
      assert.ok(changes[0].key === undefined || changes[0].key === null); assert.equal(changes[0].protocol, 'udp');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true);
      assert.deepEqual(errors, []); console.log(`PASS node credential-preserving edit ${language}/${width}`);
    } finally { await context.close(); }
  }
} finally { await browser.close(); }
