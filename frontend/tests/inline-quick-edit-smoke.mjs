import { chromium } from 'playwright';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4185/panel').replace(/\/$/, '');
const widths = [360, 390, 768, 1440];
const languages = ['en', 'fa'];
const GB = 1024 ** 3;
const failures = [];

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

for (const language of languages) {
  for (const width of widths) {
    const height = width <= 430 ? 844 : 1000;
    const requests = [];
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce' });
    await context.addInitScript(({ language, authToken }) => {
      localStorage.setItem('authToken', authToken);
      localStorage.setItem('userRole', 'main_admin');
      localStorage.setItem('ovpanel_language', language);
    }, { language, authToken: token() });
    const page = await context.newPage();
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
      else if (path === '/nodes/' || path === '/nodes') payload = ok(demoNodes);
      else if (path === '/anyconnect/settings') payload = ok({ default_enabled: false });
      else if (path === '/server/settings/' || path === '/server/settings') payload = ok({ subscription_url_prefix: 'https://demo.example.invalid/', subscription_path: 'sub' });
      else if (path === '/users/demo-user-v103/nodes') payload = ok({ desired_node_ids: [1, 2, 3], pending_node_ids: [] });
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
    });

    try {
      await page.goto(`${baseUrl}/users`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      await page.locator('.actions-dropdown-trigger').first().click();
      await page.getByRole('menuitem', { name: /quick edit|ویرایش سریع/i }).click();
      const form = page.locator('.inline-user-quick-edit');
      await form.waitFor({ state: 'visible', timeout: 5000 });

      const metrics = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
      if (metrics.sw > metrics.iw + 1) failures.push(`${language} ${width}: page overflow ${metrics.sw}>${metrics.iw}`);
      const formBox = await form.boundingBox();
      if (!formBox || formBox.x < -1 || formBox.x + formBox.width > width + 1) failures.push(`${language} ${width}: quick edit escapes viewport`);
      if (await page.locator('.quick-edit-username').getAttribute('readonly') === null) failures.push(`${language} ${width}: username is not readonly`);

      if (width <= 430) {
        for (const selector of ['.quick-edit-reset-usage', '.quick-edit-cancel', '.quick-edit-apply']) {
          const box = await page.locator(selector).boundingBox();
          if (!box || box.height < 44) failures.push(`${language} ${width}: ${selector} below 44px`);
        }
      }

      await page.locator('.quick-edit-traffic').fill('90');
      await page.locator('.quick-edit-device-limit').fill('4');
      await page.locator('.quick-edit-active').uncheck();
      await page.locator('.quick-edit-node').filter({ hasText: 'Demo Turkey' }).click();
      await page.locator('.quick-edit-reset-usage').click();
      await page.locator('.quick-edit-apply').click();
      await page.waitForTimeout(250);

      const reset = requests.find(item => item.method === 'GET' && item.path === '/users/demo-user-v103');
      const update = requests.find(item => item.method === 'PUT' && item.path === '/users/demo-user-v103/');
      const status = requests.find(item => item.method === 'PUT' && item.path === '/users/demo-user-v103/status');
      const nodes = requests.find(item => item.method === 'PUT' && item.path === '/users/demo-user-v103/nodes');
      if (!reset) failures.push(`${language} ${width}: reset request missing`);
      if (!update || update.body?.total !== 90 * GB || update.body?.device_limit !== 4) failures.push(`${language} ${width}: user update payload invalid`);
      if (!status || status.body?.status !== false) failures.push(`${language} ${width}: status update missing`);
      if (!nodes || JSON.stringify(nodes.body?.node_ids) !== JSON.stringify([1, 2, 3])) failures.push(`${language} ${width}: node assignment payload invalid`);
    } catch (error) {
      failures.push(`${language} ${width}: ${error.message}`);
    } finally {
      await context.close();
      await browser.close();
    }
  }
}

if (failures.length) {
  console.error('INLINE_QUICK_EDIT_SMOKE=FAIL');
  failures.forEach(item => console.error(`- ${item}`));
  process.exit(1);
}
console.log(`INLINE_QUICK_EDIT_SMOKE=PASS languages=${languages.length} widths=${widths.length}`);
