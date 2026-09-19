import { chromium } from 'playwright';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4173/panel').replace(/\/$/, '');
const widths = [360, 375, 390, 430, 768, 1024, 1366, 1440, 1920];
const routes = ['/', '/users', '/nodes', '/admins', '/operations', '/security', '/fleet', '/monitoring', '/bandwidth'];
const languages = ['en', 'fa'];
const demoUser = {
  id: 1,
  uuid: 'demo-user-001',
  name: 'demo-user',
  owner: 'demo-admin',
  total: 0,
  used: 0,
  expiry_date: '2030-01-01',
  is_active: true,
  is_online: false,
  online_count: 0,
  device_limit: 1,
  anyconnect_enabled: false,
  node_ids: [1],
};

function responseFor(url) {
  const path = new URL(url).pathname.replace(/^\/api/, '');
  const ok = (data = {}) => ({ success: true, msg: 'ok', data });

  if (path === '/server/info') return ok({ cpu_usage: 12, memory_usage: 24, uptime: 7200, disk_usage: 31 });
  if (path === '/nodes/' || path === '/nodes') return ok([
    { id: 1, name: 'Demo Europe', status: true, drain: false, maintenance: false },
    { id: 2, name: 'Demo USA', status: true, drain: false, maintenance: false },
  ]);
  if (path.includes('/users/online')) return ok({ total: 0, per_node: {} });
  if (path === '/users/' || path === '/users') return ok([demoUser]);
  if (path.startsWith('/users')) return ok({});
  if (path === '/admin/' || path === '/admin') return ok([]);
  if (path.startsWith('/admins')) return ok([]);
  if (path.startsWith('/backups')) return ok({ backups: [] });
  if (path === '/fleet/' || path === '/fleet') return ok([]);
  if (path.startsWith('/fleet/jobs/')) return ok({ id: 'demo', state: 'succeeded', stage: 'done' });
  if (path === '/operations/dashboard') return ok({ users: 1, nodes: 0, online: 0, traffic_bytes: 0 });
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
  if (path === '/bandwidth/status') return ok([]);
  if (path === '/bandwidth/' || path === '/bandwidth') return ok({
    settings: { enabled: false, target_type: 'all', download_mbps: 1, node_ids: [] },
    nodes: [], users: [demoUser], owners: [], groups: [],
  });
  if (path.startsWith('/bandwidth')) return ok({});
  if (path === '/anyconnect/settings') return ok({ default_enabled: false });
  if (path === '/server/settings/' || path === '/server/settings') return ok({
    subscription_url_prefix: 'https://example.invalid/',
    subscription_path: 'sub',
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

function routeUrl(route) {
  return route === '/' ? `${baseUrl}/` : `${baseUrl}${route}`;
}

async function openRoute(page, route, timeout = 10000) {
  await page.goto(routeUrl(route), { waitUntil: 'domcontentloaded', timeout });
  await page.locator('#root').waitFor({ state: 'attached', timeout });
  await page.waitForTimeout(180);
}

async function assertModalInsideViewport(page, label, width, height) {
  const modal = page.locator('.modal').last();
  await modal.waitFor({ state: 'visible', timeout: 5000 });
  const box = await modal.boundingBox();
  if (!box || box.x < -1 || box.y < -1 || box.x + box.width > width + 1 || box.y + box.height > height + 1) {
    failures.push(`${label}: modal escapes viewport`);
  }
}

async function closeLastModal(page) {
  const close = page.locator('.modal .close-modal-btn').last();
  if (await close.count()) await close.click();
}

const browser = await chromium.launch({ headless: true });
const failures = [];

for (const language of languages) {
  for (const width of widths) {
    const context = await browser.newContext({ viewport: { width, height: width <= 430 ? 820 : 900 } });
    await context.addInitScript(({ token, language }) => {
      localStorage.setItem('authToken', token);
      localStorage.setItem('userRole', 'main_admin');
      localStorage.setItem('pvnetwork_language', language);
    }, { token: demoToken(), language });

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
        await openRoute(page, route);
        const metrics = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          innerWidth: window.innerWidth,
          bodyText: document.body.innerText.slice(0, 500),
          hasRootContent: Boolean(document.querySelector('#root')?.children.length),
          dir: document.documentElement.dir,
          lang: document.documentElement.lang,
        }));
        if (!metrics.hasRootContent) failures.push(`${language} ${width}px ${route}: React root not rendered`);
        const expectedDir = language === 'fa' ? 'rtl' : 'ltr';
        if (metrics.dir !== expectedDir) failures.push(`${language} ${width}px ${route}: dir=${metrics.dir}, expected ${expectedDir}`);
        if (!String(metrics.lang || '').toLowerCase().startsWith(language)) failures.push(`${language} ${width}px ${route}: lang=${metrics.lang}`);
        if (metrics.scrollWidth > metrics.innerWidth + 1) {
          failures.push(`${language} ${width}px ${route}: horizontal overflow ${metrics.scrollWidth}>${metrics.innerWidth}`);
        }
        if (!metrics.bodyText.trim()) failures.push(`${language} ${width}px ${route}: empty body`);
        if (consoleErrors.some(text => /uncaught|TypeError|ReferenceError|Error:/.test(text))) {
          failures.push(`${language} ${width}px ${route}: console error ${consoleErrors[0]}`);
        }
      } catch (error) {
        failures.push(`${language} ${width}px ${route}: ${error.message}`);
      } finally {
        page.off('console', onConsole);
      }
    }

    if (width <= 430) {
      try {
        await openRoute(page, '/');
        const more = page.locator('.mobile-more-trigger');
        await more.click({ timeout: 5000 });
        for (const destination of ['/admins', '/operations', '/security', '/fleet', '/monitoring', '/bandwidth']) {
          const count = await page.locator(`#mobile-more-menu a[href$="${destination}"]`).count();
          if (!count) failures.push(`${language} ${width}px mobile menu missing route ${destination}`);
        }
        await page.keyboard.press('Escape');
        if (await page.locator('#mobile-more-menu').count()) failures.push(`${language} ${width}px mobile More menu did not close with Escape`);

        await openRoute(page, '/users');
        const trigger = page.locator('.actions-dropdown-trigger').first();
        await trigger.click({ timeout: 5000 });
        const menu = page.locator('.actions-dropdown-menu');
        const box = await menu.boundingBox();
        if (!box || box.x < 0 || box.y < 0 || box.x + box.width > width + 1) {
          failures.push(`${language} ${width}px user action menu escapes viewport`);
        }
        await page.keyboard.press('Escape');
        if (await menu.count()) failures.push(`${language} ${width}px user action menu did not close with Escape`);

        // Quick Edit is an inline row, not a modal. Verify it stays usable on phones.
        await trigger.click({ timeout: 5000 });
        await page.getByRole('menuitem', { name: /quick edit|ویرایش سریع/i }).click();
        const quickEdit = page.locator('.inline-user-quick-edit');
        await quickEdit.waitFor({ state: 'visible', timeout: 5000 });
        const quickBox = await quickEdit.boundingBox();
        if (!quickBox || quickBox.x < -1 || quickBox.x + quickBox.width > width + 1) {
          failures.push(`${language} ${width}px Quick Edit escapes viewport`);
        }
        for (const selector of ['.quick-edit-reset-usage', '.quick-edit-apply', '.quick-edit-cancel']) {
          const buttonBox = await page.locator(selector).boundingBox();
          if (!buttonBox || buttonBox.height < 44) failures.push(`${language} ${width}px ${selector} touch target below 44px`);
        }
        const usernameReadonly = await page.locator('.quick-edit-username').getAttribute('readonly');
        if (usernameReadonly === null) failures.push(`${language} ${width}px Quick Edit username must stay read-only until safe rename ships`);
        await page.locator('.quick-edit-node').filter({ hasText: 'Demo USA' }).click();
        await page.locator('.quick-edit-reset-usage').click();
        const resetPressed = await page.locator('.quick-edit-reset-usage').getAttribute('aria-pressed');
        if (resetPressed !== 'true') failures.push(`${language} ${width}px Quick Edit reset queue did not toggle`);
        await page.locator('.quick-edit-cancel').click();
        if (await quickEdit.count()) failures.push(`${language} ${width}px Quick Edit did not close on Cancel`);

        await trigger.click({ timeout: 5000 });
        await page.getByRole('menuitem', { name: /renew|تمدید/i }).click();
        const modal = page.locator('.modal').last();
        const modalBox = await modal.boundingBox();
        if (!modalBox || modalBox.y < 0 || modalBox.height > 820 + 1) {
          failures.push(`${language} ${width}px Renew modal escapes viewport height`);
        }
        await page.locator('.close-modal-btn').last().click();

        // Core user dialogs must all remain reachable on a phone viewport.
        await page.getByRole('button', { name: /add new user|افزودن کاربر|ایجاد کاربر/i }).first().click();
        await assertModalInsideViewport(page, `${language} ${width}px Add User`, width, 820);
        await closeLastModal(page);

        await trigger.click();
        await page.getByRole('menuitem', { name: /^(Edit|ویرایش)$/i }).click();
        await assertModalInsideViewport(page, `${language} ${width}px Edit User`, width, 820);
        await closeLastModal(page);

        const anyConnectButton = page.getByRole('button', { name: /AnyConnect/i }).first();
        await anyConnectButton.click();
        await assertModalInsideViewport(page, `${language} ${width}px AnyConnect`, width, 820);
        await closeLastModal(page);

        await openRoute(page, '/nodes');
        await page.locator('#nodes-view .view-header .btn').first().click();
        await assertModalInsideViewport(page, `${language} ${width}px Add Node`, width, 820);
        await closeLastModal(page);

        await openRoute(page, '/admins');
        await page.locator('#admins-view .view-header .btn').first().click();
        await assertModalInsideViewport(page, `${language} ${width}px Add Admin`, width, 820);
        await closeLastModal(page);
      } catch (error) {
        failures.push(`${language} ${width}px mobile interactions: ${error.message}`);
      }
    }

    await context.close();
  }
}

// Login is unauthenticated, so verify it in fresh contexts at phone and desktop widths.
for (const language of languages) {
  for (const width of [360, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: width <= 430 ? 820 : 900 } });
    await context.addInitScript(language => {
      localStorage.clear();
      localStorage.setItem('pvnetwork_language', language);
    }, language);
    const page = await context.newPage();
    try {
      await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      await page.waitForTimeout(120);
      const metrics = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
        hasUsername: Boolean(document.querySelector('#username')),
        hasPassword: Boolean(document.querySelector('#password')),
      }));
      if (!metrics.hasUsername || !metrics.hasPassword) failures.push(`${language} ${width}px login: fields missing`);
      if (metrics.scrollWidth > metrics.innerWidth + 1) failures.push(`${language} ${width}px login: horizontal overflow`);
    } catch (error) {
      failures.push(`${language} ${width}px login: ${error.message}`);
    }
    await context.close();
  }
}

await browser.close();

if (failures.length) {
  console.error('RESPONSIVE_SMOKE=FAIL');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}
console.log(`RESPONSIVE_SMOKE=PASS languages=${languages.length} widths=${widths.length} routes=${routes.length}`);
