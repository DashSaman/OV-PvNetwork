import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base = process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4188/panel';
const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600, type: 'main_admin' })).toString('base64url');
const id = 'a'.repeat(8) + '-' + 'b'.repeat(4) + '-' + 'c'.repeat(4) + '-' + 'd'.repeat(4) + '-' + 'e'.repeat(12);
const browser = await chromium.launch({ headless: true });
try {
  for (const language of ['en', 'fa']) for (const width of [360, 375, 390, 430, 768, 1024, 1366, 1440, 1920]) {
    const context = await browser.newContext({ viewport: { width, height: 950 }, hasTouch: width < 768 });
    await context.addInitScript(({ language, token }) => { localStorage.setItem('pvnetwork_language', language); localStorage.setItem('authToken', token); localStorage.setItem('userRole', 'main_admin'); }, { language, token: `demo.${payload}.signature` });
    const page = await context.newPage(); page.setDefaultTimeout(7000);
    const errors = []; const posts = []; let polls = 0;
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      const request = route.request(); const path = new URL(request.url()).pathname; let data = {};
      if (request.method() === 'POST') { posts.push(path); data = { job_id: id, node_id: 7 }; }
      else if (/\/nodes\/?$/.test(path)) data = [{ id: 7, name: 'demo-node', address: 'node.example.invalid', protocol: 'udp', status: true }];
      else if (path.endsWith('/health/')) data = [];
      else if (path.endsWith('/reconcile/' + id)) { polls++; data = { id, state: 'succeeded', progress: 100, result: { operation: 'node-reconcile', node_id: 7 } }; }
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ success: true, data }) });
    });
    try {
      await page.goto(`${base}/nodes`, { waitUntil: 'networkidle' });
      await page.locator('.actions-dropdown-trigger').click();
      await page.getByRole('menuitem', { name: language === 'fa' ? 'همگام‌سازی کاربران اختصاص‌یافته' : 'Reconcile assigned users', exact: true }).click();
      const dialog = page.getByRole('dialog'); await dialog.waitFor();
      assert.equal(posts.length, 0, 'Opening a dialog must not start repair');
      await dialog.locator('.modal-footer button').last().click();
      await page.waitForFunction(() => document.querySelector('progress')?.value === 100);
      assert.deepEqual(posts, ['/api/nodes/7/reconcile']); assert.ok(polls);
      assert.equal(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 1), true);
      await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'detached' });
      await page.locator('.actions-dropdown-trigger').click(); await page.getByRole('menuitem').last().click();
      await dialog.waitFor(); await page.waitForFunction(() => document.querySelector('progress')?.value === 100);
      assert.equal(posts.length, 1, 'Reopening resumes status without restarting repair');
      await page.keyboard.press('Tab'); assert.equal(await dialog.evaluate(element => element.contains(document.activeElement)), true);
      await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'detached' });
      assert.deepEqual(errors, []); console.log(`PASS scoped node reconcile ${language}/${width}`);
    } finally { await context.close(); }
  }
} finally { await browser.close(); }
