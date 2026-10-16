import { zoomBrowser } from './browser-zoom.mjs';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4185/panel').replace(/\/$/, '');
const widths = [360, 375, 390, 430, 768, 1024, 1366, 1440, 1920];
const languages = ['en', 'fa'];
const zooms = [1, 1.25, 1.5];
const themes = ['dark', 'light'];
const GB = 1024 ** 3;
const failures = [];
const mutationDelay = Math.max(0, Math.min(1000, Number(process.env.PV_QUICK_EDIT_RESPONSE_DELAY_MS || 0)));

const demoNodes = [
  { id: 1, name: 'Demo Europe', status: true, drain: false, maintenance: false },
  { id: 2, name: 'Demo USA', status: true, drain: false, maintenance: false },
  { id: 3, name: 'Demo Turkey', status: true, drain: false, maintenance: false },
];

function demoUser() {
  return {
    id: 103,
    uuid: 'demo-user-v103',
    name: 'demo-user-103',
    owner: 'demo-owner',
    total: 80 * GB,
    used: 12 * GB,
    expiry_date: '2026-12-31',
    is_active: true,
    is_online: true,
    online_count: 1,
    device_limit: 3,
    anyconnect_enabled: true,
    anyconnect_configured: true,
    anyconnect_password_available: true,
    node_ids: [1, 2],
  };
}

function token() {
  const payload = Buffer.from(JSON.stringify({
    exp: Math.floor(Date.now() / 1000) + 3600,
    type: 'main_admin',
  })).toString('base64url');
  return `demo.${payload}.signature`;
}

const browser = await zoomBrowser();
try {
for (const language of languages) {
for (const theme of themes) {
 for (const zoom of zooms) {
  for (const width of widths) {
    const height = width <= 430 ? 844 : 1000;
    const requests = [];
    const context = browser.context;
    const page = await context.newPage();
    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.setViewportSize({ width, height });
    await page.addInitScript(({ language, theme, authToken }) => {
      localStorage.setItem('authToken', authToken);
      localStorage.setItem('userRole', 'main_admin');
      localStorage.setItem('pvnetwork_language', language);
      localStorage.setItem('ov-dashboard-theme', theme);
    }, { language, theme, authToken: token() });
    await page.route('**/api/**', async route => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^\/api/, '');
      const method = request.method();
      let body = null;
      try { body = request.postDataJSON(); } catch { body = null; }
      if (method !== 'GET' || !['/users/', '/nodes/', '/anyconnect/settings', '/server/settings/'].includes(path)) {
        requests.push({ method, path, body });
      }
      const ok = data => ({ success: true, msg: 'ok', data });
      let payload = ok({});
      if (path === '/users/' || path === '/users') payload = ok([demoUser()]);
      else if (path === '/users/presence') payload = ok({ counts_by_uuid: { 'demo-user-v103': 1 }, online_users: 1, sample_time: 1234567890 });
      else if (path === '/nodes/' || path === '/nodes') payload = ok(demoNodes);
      else if (path === '/anyconnect/settings') payload = ok({ default_enabled: false });
      else if (path === '/server/settings/' || path === '/server/settings') payload = ok({ subscription_url_prefix: 'https://demo.example.invalid/', subscription_path: 'sub' });
      else if (path === '/users/demo-user-v103/nodes') payload = ok({ desired_node_ids: [1, 2, 3], pending_node_ids: [] });
      if (mutationDelay && path.startsWith('/users/demo-user-v103')) await new Promise(resolve => setTimeout(resolve, mutationDelay));
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
    });

    try {
      await page.goto(`${baseUrl}/users`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      await browser.setZoom(page, zoom);
      await page.locator('.pn-admin-logo').first().evaluate(image => image.decode());
      for (const element of await page.locator('.header-actions > *').all()) {
        const box=await element.boundingBox();
        const inner=await page.evaluate(()=>innerWidth);
        if (!box || box.x < -1 || box.x+box.width > inner+1 || box.height < 43.99 || box.width < 43.99) failures.push(`${language} ${theme} ${width} zoom=${zoom}: ${await element.getAttribute('class')} header bounds=${JSON.stringify(box)} viewport=${inner}`);
      }
      await page.locator('.actions-dropdown-trigger').first().click();
      await page.getByRole('menuitem', { name: /quick edit|ویرایش سریع/i }).click();
      const form = page.locator('.inline-user-quick-edit');
      await form.waitFor({ state: 'visible', timeout: 5000 });
      if (!await page.locator('.quick-edit-traffic').evaluate(element => element === document.activeElement)) failures.push(`${language} ${width} zoom=${zoom}: editor focus missing`);

      const metrics = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth, dpr: window.devicePixelRatio }));
      if (Math.abs(metrics.iw - width / zoom) > 1) failures.push(`${language} ${width} zoom=${zoom}: native CSS viewport mismatch`);
      if (metrics.sw > metrics.iw + 1) failures.push(`${language} ${width}: page overflow ${metrics.sw}>${metrics.iw}`);
      const formBox = await form.boundingBox();
      if (!formBox || formBox.x < -1 || formBox.x + formBox.width > metrics.iw + 1) failures.push(`${language} ${width} zoom=${zoom}: quick edit escapes viewport`);
      if (await page.locator('.quick-edit-username').getAttribute('readonly') === null) failures.push(`${language} ${width}: username is not readonly`);

      {
        for (const selector of ['.quick-edit-reset-usage', '.quick-edit-cancel', '.quick-edit-apply']) {
          const box = await page.locator(selector).boundingBox();
          if (!box || box.height < 44) failures.push(`${language} ${width}: ${selector} below 44px`);
        }
      }

      await page.locator('.quick-edit-traffic').fill('90');
      await page.setViewportSize({ width: width > 992 ? 768 : 1440, height });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await page.setViewportSize({ width, height });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      if (await page.locator('.quick-edit-traffic').inputValue() !== '90') failures.push(`${language} ${width} zoom=${zoom}: draft lost after resize`);
      await page.locator('.quick-edit-device-limit').fill('4');
      await page.locator('.quick-edit-active').uncheck();
      await page.locator('.quick-edit-node').filter({ hasText: 'Demo Turkey' }).click();
      await page.locator('.quick-edit-reset-usage').click();
      if (process.env.PV_QA_SCREENSHOT_DIR && theme === 'dark' && zoom === 1 && [390, 1440].includes(width)) {
        await mkdir(process.env.PV_QA_SCREENSHOT_DIR, { recursive: true });
        await page.locator('.quick-edit-apply').scrollIntoViewIfNeeded();
        await page.screenshot({ path: path.join(process.env.PV_QA_SCREENSHOT_DIR, `quick-edit-${language}-${width}.png`), fullPage: width > 430 });
      }
      await page.locator('.quick-edit-apply').focus();
      if (!await page.locator('.quick-edit-apply').evaluate(element => element === document.activeElement)) failures.push(`${language} ${width} zoom=${zoom}: save focus missing`);
      if (zoom === 1.25) await page.locator('.quick-edit-apply').press('Enter');
      else await page.locator('.quick-edit-apply').click();
      // Save performs reset/edit/status/assignment sequentially. Form closure
      // confirms the real action completed; a fixed delay races slower runners.
      await form.waitFor({ state: 'hidden', timeout: 10000 });

      const reset = requests.find(item => item.method === 'POST' && item.path === '/users/demo-user-v103/reset');
      if (requests.some(item => item.method === 'GET' && item.path === '/users/demo-user-v103')) failures.push(`${language} ${width}: unsafe legacy reset GET`);
      const update = requests.find(item => item.method === 'PUT' && item.path === '/users/demo-user-v103/');
      const status = requests.find(item => item.method === 'PUT' && item.path === '/users/demo-user-v103/status');
      const nodes = requests.find(item => item.method === 'PUT' && item.path === '/users/demo-user-v103/nodes');
      if (!reset) failures.push(`${language} ${width}: reset request missing`);
      if (!update || update.body?.total !== 90 * GB || update.body?.device_limit !== 4) failures.push(`${language} ${width}: user update payload invalid`);
      if (!status || status.body?.status !== false) failures.push(`${language} ${width}: status update missing`);
      if (!nodes || JSON.stringify(nodes.body?.node_ids) !== JSON.stringify([1, 2, 3])) failures.push(`${language} ${width}: node assignment payload invalid`);
      if (pageErrors.length) failures.push(`${language} ${width} zoom=${zoom}: ${pageErrors.join('; ')}`);
    } catch (error) {
      failures.push(`${language} ${width}: ${error.message}`);
    } finally {
      await page.close();
    }
  }
 }
}
}
} finally { await browser.close(); }

if (failures.length) {
  console.error('INLINE_QUICK_EDIT_SMOKE=FAIL');
  failures.forEach(item => console.error(`- ${item}`));
  process.exit(1);
}
console.log(`INLINE_QUICK_EDIT_SMOKE=PASS languages=${languages.length} themes=${themes.length} widths=${widths.length} native_browser_zooms=${zooms.join(',')}`);
