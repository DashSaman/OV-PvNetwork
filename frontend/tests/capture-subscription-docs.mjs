import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const repoRoot = path.resolve(import.meta.dirname, '../..');
const output = '/tmp/pvnetwork-subscription-fixture.html';
const python = process.env.PV_PYTHON || 'python3';
execFileSync(python, [path.join(repoRoot, 'tests/render_subscription_fixture.py'), output], { stdio: 'inherit' });
const outRoot = path.join(repoRoot, 'docs/images/v1.0.2');
fs.mkdirSync(outRoot, { recursive: true });

const browser = await chromium.launch({ headless: true });
for (const item of [
  { lang: 'fa', theme: 'dark', kind: 'desktop', width: 1440, height: 1000 },
  { lang: 'fa', theme: 'dark', kind: 'mobile', width: 390, height: 844 },
  { lang: 'en', theme: 'light', kind: 'desktop', width: 1440, height: 1000 },
  { lang: 'en', theme: 'light', kind: 'mobile', width: 390, height: 844 },
]) {
  const context = await browser.newContext({ viewport: { width: item.width, height: item.height }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto(pathToFileURL(output).href, { waitUntil: 'domcontentloaded' });
  await page.locator('.logo').evaluate((img, src) => { img.src = src; }, pathToFileURL(path.join(repoRoot, 'frontend/sub_clients/private-network.webp')).href);
  await page.addStyleTag({ content: '.pn5-reveal,.pn-reveal{opacity:1!important;transform:none!important;filter:none!important;transition:none!important}' });
  await page.waitForTimeout(250);
  if (item.lang === 'en') await page.locator('#langBtn').click();
  if (item.theme === 'light') await page.locator('#themeBtn').click();
  await page.waitForTimeout(100);
  const dir = path.join(outRoot, item.lang, item.kind);
  fs.mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, 'subscription.png'), fullPage: true });
  await context.close();
}
await browser.close();
console.log('SUBSCRIPTION_DOC_SCREENSHOTS=PASS');
