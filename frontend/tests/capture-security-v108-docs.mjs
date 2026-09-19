import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4217/panel').replace(/\/$/, '');
const root = path.resolve('..');
const token = () => {
  const payload = Buffer.from(JSON.stringify({
    exp: Math.floor(Date.now() / 1000) + 3600,
    type: 'main_admin',
  })).toString('base64url');
  return `demo.${payload}.signature`;
};
const ok = data => ({ success: true, msg: 'ok', data });
const demoNodes = [{
  id: 1,
  name: 'Demo-Europe',
  address: '192.0.2.10',
  port: 9090,
  ovpn_port: 1194,
  protocol: 'udp',
  status: true,
  drain: false,
  maintenance: false,
}];
for (const language of ['en', 'fa']) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(({ language, authToken }) => {
    localStorage.setItem('authToken', authToken);
    localStorage.setItem('userRole', 'main_admin');
    localStorage.setItem('pvnetwork_language', language);
  }, { language, authToken: token() });
  const page = await context.newPage();
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    const apiPath = url.pathname.replace(/^\/api/, '');
    let payload = ok({});
    if (apiPath === '/nodes/' || apiPath === '/nodes') payload = ok(demoNodes);
    else if (apiPath === '/nodes/health/' || apiPath === '/nodes/health') payload = ok([]);
    else if (apiPath.startsWith('/nodes/1/status')) payload = ok({ status: 'running' });
    else if (apiPath === '/server/info') payload = ok({});
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    });
  });
  await page.goto(`${baseUrl}/nodes`, {
    waitUntil: 'domcontentloaded',
    timeout: 10000,
  });
  const addButton = page.locator('button[aria-haspopup="dialog"]').first();
  await addButton.waitFor({ state: 'visible', timeout: 5000 });
  await addButton.click();
  const fingerprint = page.locator('#ssh_fingerprint');
  await fingerprint.waitFor({ state: 'visible', timeout: 5000 });
  await page.locator('#name').fill('Demo-Node');
  await page.locator('#address').fill('192.0.2.20');
  await fingerprint.fill('SHA256:verified-demo-fingerprint');
  const out = path.join(
    root,
    'docs',
    'images',
    'v1.0.8',
    language,
    'desktop',
    'ssh-host-key-pinning.png',
  );
  await fs.mkdir(path.dirname(out), { recursive: true });
  await page.screenshot({ path: out, fullPage: true });
  await browser.close();
}

console.log('SECURITY_V108_DOC_SCREENSHOTS=PASS');
