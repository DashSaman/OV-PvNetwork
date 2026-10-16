import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base = process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4188/panel';
const widths = [360, 375, 390, 430, 768, 1024, 1366, 1440, 1920];
const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600, type: 'main_admin' })).toString('base64url');
const browser = await chromium.launch({ headless: true });
try {
  for (const language of ['en', 'fa']) for (const width of widths) {
    const context = await browser.newContext({ viewport: { width, height: 950 }, hasTouch: width < 768 });
    await context.addInitScript(({ language, token }) => {
      localStorage.setItem('pvnetwork_language', language); localStorage.setItem('authToken', token); localStorage.setItem('userRole', 'main_admin');
    }, { language, token: `demo.${payload}.signature` });
    const page = await context.newPage(); page.setDefaultTimeout(7000);
    const errors = []; const posts = []; let uploaded = false; let action = 'backup';
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      const request = route.request(); const path = new URL(request.url()).pathname;
      const archive = { archive_id: 'a'.repeat(24), sha256: 'b'.repeat(64), size: 13, expires_at: Math.floor(Date.now() / 1000) + 3600, node_id: 7 };
      let data = {}; let status = 200;
      if (request.method() === 'POST') {
        posts.push({ path, content: request.postData(), headers: request.headers() });
        if (path.endsWith('/upload')) { uploaded = true; status = 201; data = archive; }
        else { action = path.split('/').at(-1); status = 202; data = { archive_id: archive.archive_id, job_id: 'demo-job' }; }
      } else if (/\/nodes\/?$/.test(path)) data = [{ id: 7, name: 'demo-node', address: 'node.example.invalid', protocol: 'udp', status: true }];
      else if (path.includes('/archives/') && path.endsWith('/status')) data = { state: 'succeeded', progress: 100, result: { ...archive, operation: action } };
      else if (path.endsWith('/download')) { await route.fulfill({ contentType: 'application/gzip', body: 'private-demo-backup', headers: { 'Content-Disposition': 'attachment; filename="demo.tar.gz"' } }); return; }
      else if (path.endsWith('/health/')) data = [];
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify({ success: true, data, msg: 'ok' }) });
    });
    try {
      await page.goto(`${base}/nodes`, { waitUntil: 'networkidle' });
      await page.locator('.actions-dropdown-trigger').click(); await page.getByRole('menuitem', { name: language === 'fa' ? 'بکاپ / بازیابی نود' : 'Node backup / restore', exact: true }).click();
      const modal = page.getByRole('dialog'); await modal.waitFor();
      assert.equal(await page.locator('html').getAttribute('dir'), language === 'fa' ? 'rtl' : 'ltr');
      await modal.locator('[name=ssh_password]').fill('demo-ssh-secret');
      await modal.locator('[name=ssh_fingerprint]').fill(`SHA256:${'c'.repeat(43)}`);
      await modal.locator('button[type=submit]').click();
      await modal.locator('progress').waitFor();
      await page.waitForFunction(() => document.querySelector('progress')?.value === 100);
      assert.equal(await modal.locator('[name=ssh_password]').inputValue(), '');
      assert.equal(JSON.parse(posts[0].content).ssh_password, 'demo-ssh-secret');
      const downloadEvent = page.waitForEvent('download'); await modal.locator('[data-action=download]').click(); await downloadEvent;
      await modal.locator('[name=operation]').selectOption('restore');
      await modal.locator('[name=archive_file]').setInputFiles({ name: 'demo.tar.gz', mimeType: 'application/gzip', buffer: Buffer.from('demo-archive-bytes') });
      await modal.locator('[name=offline]').check();
      assert.equal(await modal.locator('[name=confirm_downtime]').getAttribute('required'), '');
      await modal.locator('[name=confirm_downtime]').check(); await modal.locator('[name=start_recovered]').check();
      await modal.locator('[name=auth]').selectOption('key');
      await modal.locator('[name=ssh_private_key]').fill('demo-key-not-a-real-private-key');
      await modal.locator('button[type=submit]').click();
      await page.waitForFunction(() => document.querySelector('progress')?.value === 100 && document.querySelector('[name=ssh_private_key]')?.value === '');
      assert.equal(uploaded, true); const restore = posts.find(item => item.path.endsWith('/restore')); assert.ok(restore);
      const values = JSON.parse(restore.content); assert.equal(values.offline, true); assert.equal(values.confirm_downtime, true); assert.equal(values.start_recovered, true);
      assert.equal(values.archive_id, 'a'.repeat(24)); assert.equal(values.ssh_password, '');
      assert.equal(posts.find(item => item.path.endsWith('/upload')).content, 'demo-archive-bytes');
      assert.equal(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }).includes('demo-key-not-a-real-private-key')), false);
      assert.equal(await modal.evaluate(element => element.scrollWidth <= element.clientWidth + 1), true);
      const box = await modal.boundingBox(); assert.ok(box.x >= 0 && box.x + box.width <= width + 1);
      await modal.locator('[data-action=discard]').click();
      await modal.locator('.node-archive-receipt').waitFor({ state: 'detached' });
      await page.keyboard.press('Escape'); await modal.waitFor({ state: 'detached' });
      assert.deepEqual(errors, []); console.log(`PASS node archive workflow ${language}/${width}`);
    } catch (error) {
      console.error('Archive fixture failure:', language, width, page.url(), errors, (await page.locator('body').innerText()).slice(0, 1600));
      throw error;
    } finally { await context.close(); }
  }
} finally { await browser.close(); }
