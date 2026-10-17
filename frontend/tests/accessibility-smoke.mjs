// Synthetic loopback-only WCAG and actual keyboard regression; no live API.
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { zoomBrowser } from './browser-zoom.mjs';
import { focusContrast, textContrast } from './focus-contrast.mjs';
import { baseUrl, routes, responseFor, demoToken } from './accessibility-fixtures.mjs';

const require = createRequire(import.meta.url);
const origin = new URL(baseUrl).origin;
if (!/^http:\/\/127\.0\.0\.1:\d+\/panel$/.test(baseUrl)) throw new Error('Owned loopback preview required');
const axe = await readFile(process.env.PV_AXE_SOURCE || require.resolve('axe-core/axe.min.js'), 'utf8');
const failures = [], incomplete = [], manualFocus = [], counts = { pages: 0, dialogs: 0, axe: 0, negativeControls: 0, focusMeasured: 0 };
const browser = await zoomBrowser();
const quick = Boolean(process.env.PV_A11Y_QUICK);
const widths = (process.env.PV_A11Y_WIDTHS || (quick ? '1440' : '390,1440')).split(',').map(Number);
const languages = (process.env.PV_A11Y_LANGUAGES || (quick ? 'en' : 'en,fa')).split(',');
const themes = (process.env.PV_A11Y_THEMES || (quick ? 'dark' : 'dark,light')).split(',');
const zooms = (process.env.PV_A11Y_ZOOMS || '1').split(',').map(Number);
const keyboardOnly = Boolean(process.env.PV_A11Y_KEYBOARD_ONLY);
const responsive = Boolean(process.env.PV_A11Y_RESPONSIVE);
const menu = async (page, name) => {
  await page.locator('.actions-dropdown-trigger').first().click();
  await page.getByRole('menuitem', { name }).click();
};
const cases = [
  ['add-user', '/users', page => page.locator('#users-view .view-header .btn').first().click()],
  ['edit-user', '/users', page => menu(page, /^(edit|ویرایش)$/i)],
  ['renew-user', '/users', page => menu(page, /renew|تمدید/i)],
  ['rename-user', '/users', page => menu(page, /rename|تغییر نام/i)],
  ['download', '/users', page => menu(page, /download|دانلود/i)],
  ['domain-history', '/users', page => menu(page, /domain history/i)],
  ['anyconnect', '/users', page => page.getByRole('button', { name: /AnyConnect/i }).first().click()],
  ['router-user', '/users', page => menu(page, /router|mikrotik|روتر|میکروتیک/i)],
  ['add-node', '/nodes', page => page.locator('#nodes-view .view-header .btn').first().click()],
  ['edit-node', '/nodes', page => menu(page, /^(edit|ویرایش)$/i)],
  ['router-node', '/nodes', page => menu(page, /router|mikrotik|روتر|میکروتیک/i)],
  ['node-archive', '/nodes', page => menu(page, /Node backup.*restore|بکاپ.*بازیابی نود/i)],
  ['reconcile-node', '/nodes', page => menu(page, /reconcil|همگام|هماهنگ|تطبیق|ترمیم/i)],
  ['add-admin', '/admins', page => page.locator('#admins-view .view-header .btn').first().click()],
  ['edit-admin', '/admins', page => page.locator('.btn-admin-edit').first().click()],
  ['delete-admin-confirmation', '/admins', page => page.locator('.btn-admin-delete').first().click()],
  ['panel-confirmation', '/security', async page => {
    await page.locator('#pvn-new-username').fill('demo-next'); await page.locator('#pvn-current-password').fill('Demo-fixture-only-123');
    await page.locator('section[aria-labelledby="panel-runtime-title"] .monitor-actions button').click();
  }],
];
const verify = (condition, message) => { if (!condition) throw new Error(message); };
async function audit(page, label) {
  if (keyboardOnly) return;
  await page.evaluate(axe);
  const result = await page.evaluate(() => window.axe.run(document, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
  }));
  counts.axe++;
  for (const issue of result.violations) failures.push({ label, rule: issue.id, nodes: issue.nodes.map(n => ({ target: n.target, reason: n.failureSummary })) });
  for (const issue of result.incomplete) incomplete.push({ label, rule: issue.id, targets: issue.nodes.map(n => n.target) });
}
async function navigate(page, route, zoom) {
  await page.goto(baseUrl + route, { waitUntil: 'networkidle' });
  verify(page.url().replace(/\/$/, '') === (baseUrl + route).replace(/\/$/, ''), 'Wrong route: ' + page.url());
  await browser.setZoom(page, zoom);
}
try {
  for (const language of languages) for (const theme of themes) for (const width of widths) for (const zoom of zooms) {
    const page = await browser.context.newPage(); page.setDefaultTimeout(7000);
    await page.setViewportSize({ width, height: 1000 });
    await page.addInitScript(({ language, theme, token }) => {
      localStorage.setItem('pvnetwork_language', language); localStorage.setItem('ov-dashboard-theme', theme);
      localStorage.setItem('authToken', token); localStorage.setItem('userRole', 'main_admin');
    }, { language, theme, token: demoToken() });
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== origin) return route.abort();
      if (url.pathname.startsWith('/api/')) {
        let data = responseFor(url.href);
        if (/\/router-openvpn\/nodes\/\d+$/.test(url.pathname)) data = { success: true, data: { configured: true, enabled: true, capable: true, healthy: true, port: 1195, protocol: 'tcp', subnet: '10.9.0.0/24' } };
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
      }
      return route.continue();
    });
    const prefix = `${language}/${theme}/${width}/${zoom}`;
    try {
      await navigate(page, '/users', zoom);
      await page.locator('body').click({ position: { x: 1, y: 1 } });
      await page.keyboard.press('Control+Home');
      await page.keyboard.press('Tab');
      verify(await page.locator('.skip-to-content').evaluate(el => el === document.activeElement), 'Skip link is not first keyboard stop');
      await page.keyboard.press('Enter');
      verify(await page.locator('#main-content').evaluate(el => el === document.activeElement), 'Skip link did not focus main content');
      const more = page.locator('.mobile-more-trigger');
      if (await more.isVisible()) {
        await navigate(page, '/security', zoom);
        await more.focus(); await more.press('Enter');
        const items = page.locator('#mobile-more-menu [role="menuitem"]');
        verify(await items.first().evaluate(el => el === document.activeElement), 'Mobile menu initial focus missing');
        await page.keyboard.press('End');
        verify(await items.last().evaluate(el => el === document.activeElement), 'Mobile menu End failed');
        await page.keyboard.press('Home'); await page.keyboard.press('ArrowDown');
        verify(await items.nth(1).evaluate(el => el === document.activeElement), 'Mobile menu ArrowDown failed');
        const focus = await focusContrast(page);
        if (focus.manual) manualFocus.push({ label: prefix + ' mobile-menu', ...focus });
        else { counts.focusMeasured++; verify(focus.ratio >= 3, 'Mobile menu focus contrast below 3:1: ' + JSON.stringify(focus)); }
        await audit(page, prefix + ' mobile-menu-active');
        const activeText = await textContrast(page, '.mobile-more-menu .active');
        if (activeText.manual) manualFocus.push({ label: prefix + ' mobile-menu-active-text', ...activeText });
        else verify(activeText.ratio >= 4.5, 'Mobile active label contrast below 4.5:1: ' + JSON.stringify(activeText));
        await page.keyboard.press('Escape');
        verify(await more.evaluate(el => el === document.activeElement), 'Mobile menu did not restore focus');
      }
    } catch (error) { failures.push({ label: prefix + ' navigation-keyboard', error: error.message }); }
    for (const route of (responsive ? ['/users'] : routes)) {
      await navigate(page, route, zoom);
      verify(await page.locator('html').getAttribute('dir') === (language === 'fa' ? 'rtl' : 'ltr'), 'Wrong direction');
      await audit(page, prefix + route); counts.pages++;
      const moving = await page.evaluate(() => [...document.querySelectorAll('*')].filter(el => el.getClientRects().length).flatMap(el => {
        const style = getComputedStyle(el);
        const seconds = value => Math.max(...value.split(',').map(v => parseFloat(v) * (v.trim().endsWith('ms') ? .001 : 1)));
        return (style.animationName !== 'none' && seconds(style.animationDuration) > .05) || seconds(style.transitionDuration) > .05 ? [{ tag: el.tagName, class: el.className?.baseVal ?? el.className, animation: style.animationDuration, transition: style.transitionDuration }] : [];
      }));
      verify(!moving.length, 'Reduced-motion duration exceeded: ' + prefix + route + ' ' + JSON.stringify(moving));
    }
    // A deliberately broken element proves that the scanner is active.
    if (!counts.negativeControls && !keyboardOnly) {
      await page.evaluate(() => { const input = document.createElement('input'); input.id = 'demo-negative-label'; document.body.append(input); });
      const negative = await page.evaluate(() => window.axe.run('#demo-negative-label', { runOnly: ['label'] }));
      verify(negative.violations.some(v => v.id === 'label'), 'Axe negative control did not fail');
      await page.locator('#demo-negative-label').evaluate(el => el.remove()); counts.negativeControls++;
    }
    try {
      await navigate(page, '/users', zoom);
      const trigger = page.locator('.actions-dropdown-trigger').first();
      await trigger.focus(); await trigger.press('Enter');
      const items = page.getByRole('menuitem').filter({ hasNot: page.locator('[disabled]') });
      await items.first().press('End');
      verify(await items.last().evaluate(el => el === document.activeElement), 'End did not select last menu item');
      await items.last().press('Home');
      verify(await items.first().evaluate(el => el === document.activeElement), 'Home did not select first menu item');
      await items.first().press('ArrowDown');
      verify(await items.nth(1).evaluate(el => el === document.activeElement), 'ArrowDown did not move through menu');
      const focus = await focusContrast(page);
      if (focus.manual) manualFocus.push({ label: prefix + ' action-menu', ...focus });
      else { counts.focusMeasured++; verify(focus.ratio >= 3, 'Action menu focus contrast below 3:1: ' + JSON.stringify(focus)); }
      await audit(page, prefix + ' action-menu');
      for (const state of ['normal', 'hover']) {
        if (state === 'hover') await page.locator('.actions-dropdown-item.danger-action').hover();
        const danger = await textContrast(page, '.actions-dropdown-item.danger-action');
        if (danger.manual) manualFocus.push({ label: prefix + ' danger-menu-' + state, ...danger });
        else verify(danger.ratio >= 4.5, 'Danger action contrast below 4.5:1: ' + JSON.stringify(danger));
      }
      await page.keyboard.press('Escape');
      verify(await trigger.evaluate(el => el === document.activeElement), 'Menu focus did not return');
    } catch (error) { failures.push({ label: prefix + ' action-menu', error: error.message }); }
    for (const [name, route, open] of cases) {
      if (responsive && !['add-user', 'edit-user', 'edit-node', 'panel-confirmation'].includes(name)) continue;
      const label = prefix + ' ' + name;
      try {
        await navigate(page, route, zoom); await open(page);
        const dialog = page.getByRole('dialog'); await dialog.waitFor();
        verify(await dialog.count() === 1, 'Expected one named dialog');
        verify((await dialog.ariaSnapshot()).split('\n')[0].includes('"'), 'Missing accessible dialog name');
        verify(await dialog.evaluate(el => el.contains(document.activeElement)), 'Initial focus outside dialog');
        await audit(page, label);
        // axe leaves gradient-backed helper text incomplete. Check both gradient
        // endpoints as well as opaque surfaces instead of treating it as a pass.
        const unreadableHints = await dialog.locator('.input-group small').filter({ visible: true }).evaluateAll(elements => {
          const rgb = value => (value.match(/[\d.]+/g) || []).map(Number).slice(0, 3);
          const luminance = color => color.map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
          return elements.flatMap(element => {
            const foreground = luminance(rgb(getComputedStyle(element).color));
            for (let parent = element; parent; parent = parent.parentElement) {
              const style = getComputedStyle(parent);
              const stops = style.backgroundImage.match(/rgba?\([^)]+\)/g);
              const surfaces = stops || (style.backgroundColor !== 'rgba(0, 0, 0, 0)' ? [style.backgroundColor] : []);
              if (surfaces.length) {
                const ratios = surfaces.map(color => { const background = luminance(rgb(color)); return (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05); });
                return Math.min(...ratios) < 4.5 ? [{ text: element.textContent, ratios }] : [];
              }
            }
            return [];
          });
        });
        verify(!unreadableHints.length, 'Unreadable dialog helper text: ' + JSON.stringify(unreadableHints));
        const tabbable = dialog.locator('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]').filter({ visible: true });
        await tabbable.last().focus(); await page.keyboard.press('Tab');
        verify(await dialog.evaluate(el => el.contains(document.activeElement)), 'Tab escaped dialog');
        await tabbable.first().focus(); await page.keyboard.press('Shift+Tab');
        verify(await dialog.evaluate(el => el.contains(document.activeElement)), 'Shift+Tab escaped dialog');
        const focus = await page.evaluate(() => { const s = getComputedStyle(document.activeElement); return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) }; });
        verify(focus.style !== 'none' && focus.width >= 2, 'Focus indicator missing');
        const contrast = await focusContrast(page);
        if (contrast.manual) manualFocus.push({ label, ...contrast });
        else { counts.focusMeasured++; verify(contrast.ratio >= 3, 'Focus contrast below 3:1: ' + JSON.stringify(contrast)); }
        if (process.env.PV_A11Y_SCREENSHOTS && zoom === 1 && theme === 'light' && name === 'edit-user') {
          await mkdir(process.env.PV_A11Y_SCREENSHOTS, { recursive: true });
          await page.screenshot({ path: path.join(process.env.PV_A11Y_SCREENSHOTS, `${language}-${width}-focus.png`) });
        }
        await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'hidden' });
        verify(await page.evaluate(() => document.activeElement !== document.body && document.activeElement.isConnected), 'Focus did not return to invoker');
        counts.dialogs++;
      } catch (error) { failures.push({ label, error: error.message }); }
    }
    await page.close();
    // A new document must not inherit the authenticated page's init script.
    const login = await browser.context.newPage();
    await login.setViewportSize({ width, height: 1000 });
    await login.addInitScript(({ language, theme }) => { localStorage.removeItem('authToken'); localStorage.removeItem('userRole'); localStorage.setItem('pvnetwork_language', language); localStorage.setItem('ov-dashboard-theme', theme); }, { language, theme });
    await login.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.origin !== origin) return route.abort();
      if (url.pathname.startsWith('/api/')) return route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Synthetic rejected login' }) });
      return route.continue();
    });
    await navigate(login, '/login', zoom); await audit(login, prefix + ' login'); counts.pages++;
    try {
      await login.locator('#username').fill('demo-a11y'); await login.locator('#password').fill('Demo-fixture-only-123');
      await login.locator('button[type="submit"]').press('Enter'); await login.getByRole('alert').waitFor();
    } catch (error) { failures.push({ label: prefix + ' login-error-announcement', error: error.message }); }
    await login.close();
  }
} finally { await browser.close(); }
const report = { counts, failures, incomplete, manualFocus };
if (process.env.PV_A11Y_REPORT) await writeFile(process.env.PV_A11Y_REPORT, JSON.stringify(report, null, 2));
console.log('ACCESSIBILITY=' + JSON.stringify({ counts, failures: failures.length, incomplete: incomplete.length, firstFailures: failures.slice(0, 8) }));
process.exitCode = failures.length ? 1 : 0;
