// Render the actual Jinja subscription, without customer data or network calls.
import { zoomBrowser } from './browser-zoom.mjs';
import { focusContrast } from './focus-contrast.mjs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { createRequire } from 'node:module';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '../..');
const folder = await mkdtemp(path.join(tmpdir(), 'pvnetwork-sub-a11y-'));
const fixture = path.join(folder, 'demo.html');
const axe = await readFile(process.env.PV_AXE_SOURCE || createRequire(import.meta.url).resolve('axe-core/axe.min.js'), 'utf8');
const failures = [], incomplete = [], manualFocus = []; let cases = 0, browser, server;
const check = (value, reason) => { if (!value) throw new Error(reason); };
try {
  execFileSync(process.env.PV_PYTHON || 'python3', [path.join(root, 'tests/render_subscription_fixture.py'), fixture]);
  const html = await readFile(fixture);
  const library = await readFile(path.join(root, 'frontend/sub_clients/qr/qrcode.js'));
  server = createServer((request, response) => {
    if (request.url === '/demo') { response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); response.end(html); }
    else if (request.url === '/sub-assets/qr/qrcode.js') { response.writeHead(200, { 'Content-Type': 'application/javascript' }); response.end(library); }
    else { response.writeHead(404); response.end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  browser = await zoomBrowser();
  for (const language of ['en', 'fa']) for (const theme of ['dark', 'light']) for (const width of [390, 1440]) {
    const page = await browser.context.newPage(); page.setDefaultTimeout(5000);
    const label = `${language}/${theme}/${width}`;
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(({ language, theme }) => { localStorage.setItem('pn_lang', language); localStorage.setItem('pn_theme', theme); }, { language, theme });
    await page.route('**/*', route => route.request().url().startsWith(origin + '/') || route.request().url().startsWith('data:') ? route.continue() : route.abort());
    try {
      await page.goto(origin + '/demo', { waitUntil: 'networkidle' });
      await page.evaluate(axe);
      for (const state of ['page', 'qr']) {
        if (state === 'qr') { await page.locator('.node-qr').first().focus(); await page.keyboard.press('Enter'); await page.locator('#qrOverlay').waitFor({ state: 'visible' }); }
        const result = await page.evaluate(() => window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } }));
        for (const issue of result.violations) failures.push({ label: label + ' ' + state, rule: issue.id, nodes: issue.nodes.map(n => ({ target: n.target, reason: n.failureSummary })) });
        for (const issue of result.incomplete) incomplete.push({ label: label + ' ' + state, rule: issue.id, targets: issue.nodes.map(n => n.target) });
        if (state === 'qr') {
          check(await page.getByRole('dialog').evaluate(el => el.contains(document.activeElement)), 'QR initial focus missing');
          await page.locator('#qrClose').focus(); await page.keyboard.press('Tab');
          check(await page.getByRole('dialog').evaluate(el => el.contains(document.activeElement)), 'QR Tab escaped');
          await page.keyboard.press('Shift+Tab');
          check(await page.getByRole('dialog').evaluate(el => el.contains(document.activeElement)), 'QR Shift+Tab escaped');
          const focus = await focusContrast(page);
          if (focus.manual) manualFocus.push({ label, ...focus });
          else check(focus.ratio >= 3, 'QR focus contrast below 3:1: ' + JSON.stringify(focus));
          await page.keyboard.press('Escape');
          check(await page.locator('.node-qr').first().evaluate(el => el === document.activeElement), 'QR focus did not return');
        }
      }
      cases++;
    } catch (error) { failures.push({ label, error: error.message }); }
    finally { await page.close(); }
  }
} finally {
  await browser?.close();
  if (server) await new Promise(resolve => server.close(resolve));
  await rm(folder, { recursive: true, force: true });
}
if (process.env.PV_A11Y_REPORT) await writeFile(process.env.PV_A11Y_REPORT, JSON.stringify({ counts: { cases }, failures, incomplete, manualFocus }, null, 2));
console.log('SUBSCRIPTION_ACCESSIBILITY=' + JSON.stringify({ cases, failures: failures.length, incomplete: incomplete.length, firstFailures: failures.slice(0, 10) }));
process.exitCode = failures.length ? 1 : 0;
