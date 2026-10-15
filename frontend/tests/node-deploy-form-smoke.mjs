import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4186/panel';
const widths = [360, 375, 390, 430, 768, 1024, 1366, 1440, 1920];
const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600, type: 'main_admin' })).toString('base64url');
const browser = await chromium.launch({ headless: true });
try {
  for (const language of ['en', 'fa']) {
    for (const width of widths) {
      const context = await browser.newContext({ viewport: { width, height: 950 } });
      await context.addInitScript(({ language, token }) => {
        localStorage.setItem('pvnetwork_language', language);
        localStorage.setItem('authToken', token);
        localStorage.setItem('userRole', 'main_admin');
      }, { language, token: `demo.${payload}.signature` });
      const page = await context.newPage();
      page.setDefaultTimeout(5000);
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const mutations = [];
      await page.route('**/api/**', async route => {
        if (route.request().method() !== 'GET') mutations.push(route.request().url());
        const path = new URL(route.request().url()).pathname;
        let data = {};
        if (/\/nodes\/?$|\/nodes\/health\/?$|\/users\/?$/.test(path)) data = [];
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, msg: 'ok', data }) });
      });
      try {
        await page.goto(`${base}/nodes`, { waitUntil: 'networkidle', timeout: 10000 });
        await page.locator('#nodes-view .view-header button').click();
        const modal = page.locator('.modal-overlay .modal');
        const deployment = modal.locator('select').first();
        await deployment.selectOption('manual');
        assert.equal(await deployment.inputValue(), 'manual', `${language}/${width}: selected manual mode must remain selected`);
        assert.equal(await modal.locator('input[name="key"]').count(), 1);
        assert.equal(await modal.locator('input[name="ssh_password"]').count(), 0);
        await deployment.selectOption('auto');
        assert.equal(await deployment.inputValue(), 'auto');
        assert.equal(await modal.locator('input[name="key"]').count(), 0);
        await modal.locator('#sshAuthMethod').selectOption('key');
        await modal.locator('#ssh_private_key').fill('demo-key-text-never-submitted');
        assert.equal(await modal.locator('input[name="ssh_password"]').count(), 0);
        await modal.locator('#mode').selectOption('adopt');
        assert.equal(await modal.locator('input[name="existing_node_id"]').count(), 1);
        await modal.locator('#mode').selectOption('fresh');
        assert.equal(await modal.locator('input[name="existing_node_id"]').count(), 0);
        await modal.locator('#sshAuthMethod').selectOption('password');
        assert.equal(await modal.locator('#ssh_private_key').count(), 0);
        assert.equal(await modal.locator('input[name="ssh_password"]').count(), 1);
        assert.equal(await page.locator('html').getAttribute('dir'), language === 'fa' ? 'rtl' : 'ltr');
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true);
        assert.deepEqual(mutations, []);
        console.log(`PASS node deployment form ${language}/${width}`);
      } catch (error) {
        console.error('Fixture page:', page.url(), errors, (await page.locator('body').innerText()).slice(0, 1200));
        throw new Error(`${language}/${width}: ${error.message}`, { cause: error });
      } finally { await context.close(); }
    }
  }
} finally { await browser.close(); }
