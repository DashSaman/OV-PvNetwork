import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4184/panel').replace(/\/$/, '');
const repoRoot = path.resolve(import.meta.dirname, '../..');
const outRoot = path.join(repoRoot, 'docs/images/v1.0.3');
fs.mkdirSync(outRoot, { recursive: true });

const GB = 1024 ** 3;
const demoUser = {
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
const demoNodes = [
  { id: 1, name: 'Demo Europe', status: true, drain: false, maintenance: false },
  { id: 2, name: 'Demo USA', status: true, drain: false, maintenance: false },
  { id: 3, name: 'Demo Turkey', status: true, drain: false, maintenance: false },
];

function ok(data = {}) { return { success: true, msg: 'ok', data }; }
function responseFor(url) {
  const pathname = new URL(url).pathname.replace(/^\/api/, '');
  if (pathname === '/users/' || pathname === '/users') return ok([demoUser]);
  if (pathname === '/nodes/' || pathname === '/nodes') return ok(demoNodes);
  if (pathname === '/anyconnect/settings') return ok({ default_enabled: false });
  if (pathname === '/server/settings/' || pathname === '/server/settings') {
    return ok({ subscription_url_prefix: 'https://demo.example.invalid/', subscription_path: 'sub' });
  }
  return ok({});
}
function demoToken() {
  const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600, type: 'main_admin' })).toString('base64url');
  return `demo.${payload}.signature`;
}

const browser = await chromium.launch({ headless: true });
for (const item of [
  { lang: 'en', kind: 'desktop', width: 1440, height: 1000 },
  { lang: 'en', kind: 'mobile', width: 390, height: 844 },
  { lang: 'fa', kind: 'desktop', width: 1440, height: 1000 },
  { lang: 'fa', kind: 'mobile', width: 390, height: 844 },
]) {
  const context = await browser.newContext({ viewport: { width: item.width, height: item.height }, reducedMotion: 'reduce' });
  await context.addInitScript(({ token, lang }) => {
    localStorage.setItem('authToken', token);
    localStorage.setItem('userRole', 'main_admin');
    localStorage.setItem('ovpanel_language', lang);
  }, { token: demoToken(), lang: item.lang });
  const page = await context.newPage();
  await page.route('**/api/**', async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(responseFor(route.request().url())) });
  });
  await page.goto(`${baseUrl}/users`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(350);
  await page.locator('.actions-dropdown-trigger').first().click();
  await page.getByRole('menuitem', { name: /quick edit|ویرایش سریع/i }).click();
  await page.locator('.inline-user-quick-edit').waitFor({ state: 'visible' });
  await page.locator('.quick-edit-node').filter({ hasText: 'Demo Turkey' }).click();
  await page.locator('.quick-edit-reset-usage').click();
  const dir = path.join(outRoot, item.lang, item.kind);
  fs.mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, 'users-inline-quick-edit.png'), fullPage: true });
  await context.close();
}
await browser.close();
console.log('V1_0_3_INLINE_EDIT_DOC_SCREENSHOTS=PASS');
