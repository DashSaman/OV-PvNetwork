import { chromium } from 'playwright';

const baseUrl = process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4173';
const widths = [360, 375, 390, 430, 768, 1024, 1366, 1440, 1920];
const routes = ['/', '/users', '/nodes', '/admins', '/operations', '/security', '/fleet', '/monitoring', '/bandwidth'];

function responseFor(url) {
  const path = new URL(url).pathname.replace(/^\/api/, '');
  const ok = (data = {}) => ({ success: true, msg: 'ok', data });

  if (path === '/server/info') return ok({ cpu_usage: 12, memory_usage: 24, uptime: 7200, disk_usage: 31 });
  if (path === '/nodes/' || path === '/nodes') return ok([]);
  if (path.includes('/users/online')) return ok({ total: 0, per_node: {} });
  if (path.startsWith('/users')) return ok([]);
  if (path.startsWith('/admins')) return ok([]);
  if (path.startsWith('/backups')) return ok({ backups: [] });
  if (path === '/fleet/' || path === '/fleet') return ok([]);
  if (path.startsWith('/fleet/jobs/')) return ok({ id: 'demo', state: 'succeeded', stage: 'done' });
  if (path === '/operations/dashboard') return ok({ users: 0, nodes: 0, online: 0, traffic_bytes: 0 });
  if (path === '/operations/audit') return ok([]);
  if (path.includes('/operations/users/') && path.includes('/history')) return ok([]);
  if (path.startsWith('/security')) return ok({
    rate_limit_enabled: true,
    rate_limit_per_minute: 120,
    ip_allowlist_enabled: false,
    ip_allowlist: [],
    totp_enabled: false,
    tokens: [],
  });
  if (path.startsWith('/server/monitoring')) return ok({
    enabled: false,
    telegram_configured: false,
    cpu_threshold: 90,
    memory_threshold: 90,
    disk_threshold: 90,
  });
  if (path.startsWith('/bandwidth')) return ok({
    settings: { enabled: false, target_type: 'all', download_mbps: 0 },
    nodes: [], users: [], owners: [], groups: [],
  });
  if (path.includes('/settings') || path.includes('/setting')) return ok({});
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
const failures = [];

for (const width of widths) {
  const context = await browser.newContext({ viewport: { width, height: width <= 430 ? 820 : 900 } });
  await context.addInitScript(({ token }) => {
    localStorage.setItem('authToken', token);
    localStorage.setItem('userRole', 'main_admin');
    localStorage.setItem('i18nextLng', 'en');
  }, { token: demoToken() });

  const page = await context.newPage();
  await page.route('**/api/**', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(responseFor(route.request().url())),
    });
  });

  for (const route of routes) {
    const consoleErrors = [];
    const onConsole = message => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    };
    page.on('console', onConsole);
    try {
      await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForTimeout(120);
      const metrics = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
        bodyText: document.body.innerText.slice(0, 500),
      }));
      if (metrics.scrollWidth > metrics.innerWidth + 1) {
        failures.push(`${width}px ${route}: horizontal overflow ${metrics.scrollWidth}>${metrics.innerWidth}`);
      }
      if (!metrics.bodyText.trim()) failures.push(`${width}px ${route}: empty body`);
      if (consoleErrors.some(text => /uncaught|TypeError|ReferenceError|Error:/.test(text))) {
        failures.push(`${width}px ${route}: console error ${consoleErrors[0]}`);
      }
    } catch (error) {
      failures.push(`${width}px ${route}: ${error.message}`);
    } finally {
      page.off('console', onConsole);
    }
  }

  if (width <= 430) {
    await page.goto(`${baseUrl}/`, { waitUntil: 'networkidle' });
    const more = page.getByRole('button', { name: /more/i });
    await more.click();
    for (const destination of ['/admins', '/operations', '/security', '/fleet', '/monitoring', '/bandwidth']) {
      const count = await page.locator(`#mobile-more-menu a[href="${destination}"]`).count();
      if (!count) failures.push(`${width}px mobile menu missing route ${destination}`);
    }
  }

  await context.close();
}

await browser.close();

if (failures.length) {
  console.error('RESPONSIVE_SMOKE=FAIL');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}
console.log(`RESPONSIVE_SMOKE=PASS widths=${widths.length} routes=${routes.length}`);
