import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4212/panel').replace(/\/$/, '');
const repoRoot = path.resolve(import.meta.dirname, '../..');
const outRoot = path.join(repoRoot, 'docs/images/v1.0.5');

const demoNodes = [
  { id: 1, name: 'Demo Europe', status: true, drain: false, maintenance: false },
  { id: 2, name: 'Demo USA', status: true, drain: false, maintenance: false },
  { id: 3, name: 'Demo Maintenance', status: true, drain: false, maintenance: true },
  { id: 4, name: 'Demo Draining', status: true, drain: true, maintenance: false },
];

function ok(data = {}) { return { success: true, msg: 'ok', data }; }
function responseFor(url) {
  const pathname = new URL(url).pathname.replace(/^\/api/, '');
  if (pathname === '/users/' || pathname === '/users') return ok([]);
  if (pathname.includes('/users/online')) return ok({ total: 0, per_node: {} });
  if (pathname === '/nodes/' || pathname === '/nodes') return ok(demoNodes);
  if (pathname === '/anyconnect/settings') return ok({ default_enabled: false });
  if (pathname === '/server/settings/' || pathname === '/server/settings') {
    return ok({ subscription_url_prefix: 'https://demo.example.invalid/', subscription_path: 'sub' });
  }
  return ok({});
}
function demoToken() {
  const payload = Buffer.from(JSON.stringify({
    exp: Math.floor(Date.now() / 1000) + 3600,
    type: 'main_admin',
  })).toString('base64url');
  return `demo.${payload}.signature`;
}

const browser = await chromium.launch({ headless: true });
for (const item of [
  { lang: 'en', kind: 'desktop', width: 1440, height: 1000 },
  { lang: 'en', kind: 'mobile', width: 390, height: 844 },
  { lang: 'fa', kind: 'desktop', width: 1440, height: 1000 },
  { lang: 'fa', kind: 'mobile', width: 390, height: 844 },
]) {
  const context = await browser.newContext({
    viewport: { width: item.width, height: item.height },
    reducedMotion: 'reduce',
  });
  await context.addInitScript(({ authToken, lang }) => {
    localStorage.setItem('authToken', authToken);
    localStorage.setItem('userRole', 'main_admin');
    localStorage.setItem('pvnetwork_language', lang);
  }, { authToken: demoToken(), lang: item.lang });

  const page = await context.newPage();
  await page.route('**/api/**', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(responseFor(route.request().url())),
    });
  });
  await page.goto(`${baseUrl}/users`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: /add new user|افزودن کاربر|ایجاد کاربر/i }).first().click();
  await page.locator('.create-user-nodes').waitFor({ state: 'visible' });
  await page.locator('#new-user-name').fill('demo-user');
  await page.waitForTimeout(150);

  const dir = path.join(outRoot, item.lang, item.kind);
  fs.mkdirSync(dir, { recursive: true });
  await page.screenshot({
    path: path.join(dir, 'user-create-node-selector.png'),
    fullPage: true,
  });
  await context.close();
}
await browser.close();
console.log('V1_0_5_USER_CREATE_NODE_SELECTOR_DOC_SCREENSHOTS=PASS');
