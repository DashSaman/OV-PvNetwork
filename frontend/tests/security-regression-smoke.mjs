import { chromium } from 'playwright';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4173/panel').replace(/\/$/, '');
const payload = `<img src=x onerror="globalThis.__pvnXss=1">`;
const ok = data => ({ success: true, msg: 'ok', data });

function token() {
  const body = Buffer.from(JSON.stringify({
    exp: Math.floor(Date.now() / 1000) + 3600,
    type: 'main_admin',
  })).toString('base64url');
  return `demo.${body}.signature`;
}

function responseFor(url) {
  const path = new URL(url).pathname.replace(/^\/api/, '');
  if (path === '/users/' || path === '/users') return ok([{
    id: 1, uuid: 'xss-user-1', name: payload, owner: 'owner',
    total: 0, used: 0, expiry_date: '2030-01-01', is_active: true,
    is_online: false, online_count: 0, device_limit: 1,
    anyconnect_enabled: false, node_ids: [1],
  }]);
  if (path === '/nodes/' || path === '/nodes') return ok([
    { id: 1, name: 'Safe Node', status: true },
  ]);
  if (path.includes('/users/online')) return ok({ total: 0, per_node: {} });
  if (path === '/anyconnect/settings') return ok({ default_enabled: false });
  if (path === '/server/settings/' || path === '/server/settings') return ok({
    subscription_url_prefix: 'https://example.invalid/', subscription_path: 'sub',
  });
  return ok({});
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await context.addInitScript(({ authToken }) => {
  localStorage.setItem('authToken', authToken);
  localStorage.setItem('userRole', 'main_admin');
  localStorage.setItem('pvnetwork_language', 'en');
  delete globalThis.__pvnXss;
}, { authToken: token() });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(`pageerror:${error.message}`));
page.on('console', message => {
  if (message.type() === 'error' && !message.text().includes('Failed to load resource')) errors.push(`console:${message.text()}`);
});
await page.route('**/api/**', async route => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(responseFor(route.request().url())),
  });
});

try {
  await page.goto(`${baseUrl}/users`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('#root').waitFor({ state: 'attached', timeout: 5000 });
  await page.waitForTimeout(250);
  const state = await page.evaluate(payloadValue => ({
    text: document.body.innerText,
    executed: Boolean(globalThis.__pvnXss),
    scripts: [...document.querySelectorAll('script')].some(node => node.textContent.includes(payloadValue)),
    executableImages: [...document.querySelectorAll('img[onerror]')].length,
  }), payload);
  if (!state.text.includes(payload)) throw new Error(`hostile display value was not rendered as text; body=${state.text.slice(0,1200)}`);
  if (state.executed) throw new Error('hostile display payload executed');
  if (state.scripts) throw new Error('hostile display payload became script content');
  if (state.executableImages) throw new Error('hostile display payload created executable img onerror');
  if (errors.length) throw new Error(`browser errors: ${errors.join(' | ')}`);
  console.log('SECURITY_REGRESSION_SMOKE=PASS');
} finally {
  await context.close();
  await browser.close();
}
