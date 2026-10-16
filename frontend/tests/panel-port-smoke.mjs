import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base = process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4188/panel';
const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600, type: 'main_admin' })).toString('base64url');
const browser = await chromium.launch({ headless: true });
try {
  for (const language of ['en', 'fa']) for (const width of [360, 375, 390, 430, 768, 1024, 1366, 1440, 1920]) {
    const context = await browser.newContext({ viewport: { width, height: 950 }, hasTouch: width < 768 });
    await context.addInitScript(({ language, token }) => { localStorage.setItem('pvnetwork_language', language); localStorage.setItem('authToken', token); localStorage.setItem('userRole', 'main_admin'); }, { language, token: `demo.${payload}.signature` });
    const page = await context.newPage(); page.setDefaultTimeout(7000); const changes = []; const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      const request = route.request(); const path = new URL(request.url()).pathname; let data = {};
      if (path.endsWith('/security/') || path.endsWith('/security')) data = { allowed_cidrs: [], tokens: [], totp_enabled: false };
      if (path.endsWith('/security/panel-settings')) data = { username: 'demo-admin', panel_path: 'panel', panel_port: changes.length ? 19443 : 19000 };
      if (path.endsWith('/panel-settings/apply')) { changes.push(JSON.parse(request.postData())); data = { change_id: 'demo-port-change', status_token: 'demo-status-value', target_path: 'panel', target_port: 19443 }; }
      if (path.includes('/panel-settings/jobs/')) { assert.equal(request.headers().authorization, undefined); data = { change_id: 'demo-port-change', status: 'complete', new_port: 19443 }; }
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ success: true, data }) });
    });
    try {
      await page.goto(`${base}/security`, { waitUntil: 'networkidle' });
      const card = page.locator('section[aria-labelledby=panel-runtime-title]');
      await card.locator('#pvn-current-password').fill('demo-current-private');
      await card.locator('#pvn-new-port').fill('19002'); await card.locator('.monitor-actions button').click();
      assert.equal(await page.getByRole('dialog').count(), 0); assert.equal(changes.length, 0);
      await card.locator('#pvn-new-port').fill('19443'); await card.locator('.monitor-actions button').click();
      const dialog = page.getByRole('dialog'); await dialog.waitFor();
      await page.keyboard.press('Tab'); assert.equal(await dialog.evaluate(element => element.contains(document.activeElement)), true);
      await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'detached' }); assert.equal(changes.length, 0);
      await card.locator('.monitor-actions button').click(); await dialog.waitFor();
      assert.match(await dialog.innerText(), /19443/); await dialog.locator('.modal-footer button').last().click();
      await page.waitForFunction(() => document.getElementById('pvn-current-password')?.value === '' && !document.querySelector('[role=dialog]'));
      await card.locator('.success-message').waitFor();
      assert.deepEqual(changes, [{ current_password: 'demo-current-private', new_port: 19443 }]);
      assert.equal(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }).includes('demo-current-private')), false);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true);
      assert.deepEqual(errors, []); console.log(`PASS staged panel internal port ${language}/${width}`);
    } finally { await context.close(); }
  }
} finally { await browser.close(); }
