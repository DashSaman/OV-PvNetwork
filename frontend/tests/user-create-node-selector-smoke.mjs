import { chromium } from 'playwright';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4173/panel').replace(/\/$/, '');
const widths = [360, 390, 768, 1440];
const languages = ['en', 'fa'];
const failures = [];

const demoNodes = [
  { id: 1, name: 'Demo Europe', status: true, drain: false, maintenance: false },
  { id: 2, name: 'Demo USA', status: true, drain: false, maintenance: false },
  { id: 3, name: 'Demo Maintenance', status: true, drain: false, maintenance: true },
];

function ok(data = {}) {
  return { success: true, msg: 'ok', data };
}

function token() {
  const payload = Buffer.from(JSON.stringify({
    exp: Math.floor(Date.now() / 1000) + 3600,
    type: 'main_admin',
  })).toString('base64url');
  return `demo.${payload}.signature`;
}

function getPayload(path) {
  if (path === '/nodes/' || path === '/nodes') return ok(demoNodes);
  if (path === '/users/' || path === '/users') return ok([]);
  if (path.includes('/users/online')) return ok({ total: 0, per_node: {} });
  if (path === '/anyconnect/settings') return ok({ default_enabled: false });
  if (path === '/server/settings/' || path === '/server/settings') {
    return ok({ subscription_url_prefix: 'https://example.invalid/', subscription_path: 'sub' });
  }
  if (path.startsWith('/admin') || path.startsWith('/admins')) return ok({});
  if (path.startsWith('/server/')) return ok({});
  return ok({});
}

for (const language of languages) {
  for (const width of widths) {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width, height: width <= 430 ? 844 : 1000 } });
    await context.addInitScript(({ language, authToken }) => {
      localStorage.setItem('authToken', authToken);
      localStorage.setItem('userRole', 'main_admin');
      localStorage.setItem('pvnetwork_language', language);
    }, { language, authToken: token() });

    const page = await context.newPage();
    const mutations = [];
    page.on('dialog', dialog => dialog.dismiss());
    await page.route('**/api/**', async route => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^\/api/, '');
      const method = request.method();
      if (method === 'POST' && (path === '/users/' || path === '/users')) {
        let body = null;
        try { body = request.postDataJSON(); } catch { body = null; }
        mutations.push({ method, path, body });
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ok('demo-created')) });
        return;
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(getPayload(path)) });
    });

    try {
      await page.goto(`${baseUrl}/users`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      await page.locator('#root').waitFor({ state: 'attached', timeout: 5000 });
      await page.getByRole('button', { name: /add new user|افزودن کاربر|ایجاد کاربر/i }).first().click();

      const selector = page.locator('.create-user-nodes');
      await selector.waitFor({ state: 'visible', timeout: 5000 });
      const metrics = await page.evaluate(() => ({
        sw: document.documentElement.scrollWidth,
        iw: window.innerWidth,
        dir: document.documentElement.dir,
      }));
      const expectedDir = language === 'fa' ? 'rtl' : 'ltr';
      if (metrics.dir !== expectedDir) failures.push(`${language} ${width}: dir=${metrics.dir}, expected ${expectedDir}`);
      if (metrics.sw > metrics.iw + 1) failures.push(`${language} ${width}: horizontal overflow ${metrics.sw}>${metrics.iw}`);

      const europe = page.locator('.create-user-node').filter({ hasText: 'Demo Europe' }).locator('input');
      const usa = page.locator('.create-user-node').filter({ hasText: 'Demo USA' }).locator('input');
      const maintenance = page.locator('.create-user-node').filter({ hasText: 'Demo Maintenance' }).locator('input');
      if (!(await europe.isChecked())) failures.push(`${language} ${width}: Europe not selected by default`);
      if (!(await usa.isChecked())) failures.push(`${language} ${width}: USA not selected by default`);
      if (await maintenance.isChecked()) failures.push(`${language} ${width}: maintenance node selected by default`);
      if (!(await maintenance.isDisabled())) failures.push(`${language} ${width}: maintenance node is selectable`);

      if (width <= 430) {
        for (const label of await page.locator('.create-user-node').all()) {
          const box = await label.boundingBox();
          if (!box || box.height < 44) failures.push(`${language} ${width}: node touch target below 44px`);
        }
        const box = await selector.boundingBox();
        if (!box || box.x < -1 || box.x + box.width > width + 1) failures.push(`${language} ${width}: selector escapes viewport`);
      }

      await usa.uncheck();
      await page.locator('#new-user-name').fill(`demo${width}`.slice(0, 10));
      await page.getByRole('button', { name: /create user|ایجاد کاربر/i }).last().click();
      await page.waitForTimeout(300);

      const create = mutations.find(item => item.method === 'POST' && (item.path === '/users/' || item.path === '/users'));
      if (!create) failures.push(`${language} ${width}: create-user request missing`);
      else if (JSON.stringify(create.body?.node_ids) !== JSON.stringify([1])) {
        failures.push(`${language} ${width}: node_ids payload=${JSON.stringify(create.body?.node_ids)}`);
      }
    } catch (error) {
      failures.push(`${language} ${width}: ${error.message}`);
    } finally {
      await context.close();
      await browser.close();
    }
  }
}

if (failures.length) {
  console.error('USER_CREATE_NODE_SELECTOR_SMOKE=FAIL');
  failures.forEach(item => console.error(`- ${item}`));
  process.exit(1);
}
console.log(`USER_CREATE_NODE_SELECTOR_SMOKE=PASS languages=${languages.length} widths=${widths.length}`);
