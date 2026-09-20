import { chromium } from 'playwright';

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4173/panel').replace(/\/$/, '');
const ok = data => ({ success: true, msg: 'ok', data });

function makeToken(sub, gen) {
  const payload = Buffer.from(JSON.stringify({
    sub, gen, type: 'main_admin', exp: Math.floor(Date.now() / 1000) + 3600,
  })).toString('base64url');
  return `demo.${payload}.signature`;
}

const oldToken = makeToken('owner', 'gen-old');
const pendingToken = makeToken('new-owner', 'gen-new');
const securityData = {
  rate_limit_enabled: true, rate_limit_per_minute: 120,
  ip_allowlist_enabled: false, allowed_cidrs: [], totp_enabled: false, tokens: [],
};

async function newContext(browser, viewport) {
  const context = await browser.newContext({ viewport });
  await context.addInitScript(({ token }) => {
    if (!localStorage.getItem('authToken')) localStorage.setItem('authToken', token);
    if (!localStorage.getItem('userRole')) localStorage.setItem('userRole', 'main_admin');
    localStorage.setItem('pvnetwork_language', 'en');
  }, { token: oldToken });
  return context;
}

async function mockApi(page, terminalStatus) {
  const stats = { apply: 0, polls: 0, authOnPoll: false, changeHeader: false };
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^\/api/, '');
    let body = ok({});
    if (path === '/security/' || path === '/security') body = ok(securityData);
    else if (path === '/security/panel-settings' && request.method() === 'GET') {
      body = ok({ username: 'owner', panel_path: 'panel', redirect: null, active_change: null });
    } else if (path === '/security/panel-settings/apply' && request.method() === 'POST') {
      stats.apply += 1;
      body = ok({
        change_id: `change-${terminalStatus}`,
        status_token: `status-${terminalStatus}`,
        pending_access_token: pendingToken,
        target_path: 'newpanel',
      });
    } else if (path.includes('/security/panel-settings/jobs/')) {
      stats.polls += 1;
      const headers = request.headers();
      stats.authOnPoll ||= Boolean(headers.authorization);
      stats.changeHeader ||= headers['x-pvnetwork-change-token'] === `status-${terminalStatus}`;
      body = ok({
        change_id: `change-${terminalStatus}`,
        status: terminalStatus,
        old_path: 'panel', new_path: 'newpanel', changed_fields: ['username', 'path'],
        failure_reason: terminalStatus === 'rolled_back' ? 'verification failed' : null,
      });
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  return stats;
}

async function openCard(page) {
  await page.goto(`${baseUrl}/security`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.getByRole('heading', { name: /Panel & Main Admin/i }).waitFor({ timeout: 5000 });
}

async function submit(page) {
  await page.getByLabel('Current password').fill('demo-current-value');
  await page.getByLabel('New username').fill('new-owner');
  await page.getByLabel('New password', { exact: true }).fill('demo-new-value-456');
  await page.getByLabel('Confirm new password', { exact: true }).fill('demo-new-value-456');
  await page.getByLabel('Panel path').fill('newpanel');
  await page.getByRole('button', { name: 'Apply changes' }).click();
  const dialog = page.getByRole('dialog', { name: /Confirm panel changes/i });
  await dialog.waitFor({ state: 'visible', timeout: 5000 });
  await dialog.getByText(/owner.*new-owner/i).waitFor();
  await dialog.getByText(/panel.*newpanel/i).waitFor();
  await dialog.getByRole('button', { name: 'Confirm' }).click();
}

async function successFlow(browser) {
  const context = await newContext(browser, { width: 1440, height: 950 });
  const page = await context.newPage();
  const stats = await mockApi(page, 'complete');
  await openCard(page);
  await submit(page);
  await page.waitForURL('**/newpanel/security', { timeout: 10000 });
  const storage = await page.evaluate(() => ({
    token: localStorage.getItem('authToken'),
    pending: sessionStorage.getItem('pvnPendingAuthToken'),
    envelope: sessionStorage.getItem('pvnPanelSettingsChange'),
  }));
  if (stats.apply !== 1 || stats.polls < 1) throw new Error('success apply/poll missing');
  if (stats.authOnPoll) throw new Error('job poll leaked Authorization');
  if (!stats.changeHeader) throw new Error('job poll omitted change token');
  if (storage.token !== pendingToken) throw new Error('replacement token not promoted');
  if (storage.pending || storage.envelope) throw new Error('success handoff not cleared');
  await context.close();
}

async function rollbackFlow(browser) {
  const context = await newContext(browser, { width: 390, height: 844 });
  const page = await context.newPage();
  const stats = await mockApi(page, 'rolled_back');
  await openCard(page);
  await submit(page);
  await page.getByText(/verification failed/i).waitFor({ timeout: 10000 });
  const state = await page.evaluate(() => ({
    token: localStorage.getItem('authToken'),
    pending: sessionStorage.getItem('pvnPendingAuthToken'),
    envelope: sessionStorage.getItem('pvnPanelSettingsChange'),
    scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth,
  }));
  if (state.token !== oldToken) throw new Error('rollback replaced original session');
  if (state.pending || state.envelope) throw new Error('rollback handoff not cleared');
  if (!page.url().includes('/panel/security')) throw new Error(`rollback navigated: ${page.url()}`);
  if (state.scrollWidth > state.innerWidth + 1) throw new Error('mobile horizontal overflow');
  if (stats.authOnPoll || !stats.changeHeader) throw new Error('rollback poll auth contract failed');
  await context.close();
}

const browser = await chromium.launch({ headless: true });
try {
  await successFlow(browser);
  await rollbackFlow(browser);
} finally {
  await browser.close();
}
console.log('PANEL_SETTINGS_SMOKE=PASS');
