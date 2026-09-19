import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const repoRoot = path.resolve(import.meta.dirname, '../..');
const output = '/tmp/pvnetwork-subscription-fixture.html';
const python = process.env.PV_PYTHON || 'python3';
execFileSync(python, [path.join(repoRoot, 'tests/render_subscription_fixture.py'), output], { stdio: 'inherit' });

const widths = [360, 375, 390, 430, 768, 1024, 1440];
const browser = await chromium.launch({ headless: true });
const failures = [];

for (const width of widths) {
  const context = await browser.newContext({ viewport: { width, height: 900 } });
  const page = await context.newPage();
  await page.goto(pathToFileURL(output).href, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(250);

  const metrics = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    bodyScrollWidth: document.body.scrollWidth,
  }));
  if (metrics.scrollWidth > metrics.innerWidth + 1 || metrics.bodyScrollWidth > metrics.innerWidth + 1) {
    failures.push(`${width}px: page horizontal overflow ${metrics.scrollWidth}/${metrics.bodyScrollWidth} > ${metrics.innerWidth}`);
  }

  if (width <= 430) {
    const tooSmall = await page.locator('button:visible').evaluateAll(buttons => buttons
      .map(button => {
        const rect = button.getBoundingClientRect();
        return { text: (button.textContent || button.getAttribute('aria-label') || '').trim(), width: rect.width, height: rect.height };
      })
      .filter(item => item.width < 44 || item.height < 44));
    for (const item of tooSmall) failures.push(`${width}px: touch target too small ${JSON.stringify(item)}`);
  }

  const escaping = await page.locator('.hero, .section, .any-card, .client, .node').evaluateAll(nodes => nodes
    .map(node => {
      const r = node.getBoundingClientRect();
      return { cls: node.className, left: r.left, right: r.right, width: r.width };
    })
    .filter(r => r.left < -1 || r.right > window.innerWidth + 1));
  if (escaping.length) failures.push(`${width}px: content escapes viewport ${JSON.stringify(escaping.slice(0, 3))}`);

  if (width === 390 || width === 1440) {
    await page.locator('#langBtn').click();
    await page.locator('#themeBtn').click();
    await page.waitForTimeout(100);
    const switched = await page.evaluate(() => ({
      dir: document.documentElement.dir,
      lang: document.documentElement.lang,
      theme: document.documentElement.dataset.theme,
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    }));
    if (switched.dir !== 'ltr' || switched.lang !== 'en') failures.push(`${width}px: language switch did not produce English LTR`);
    if (switched.theme !== 'light') failures.push(`${width}px: theme switch did not produce light theme`);
    if (switched.scrollWidth > switched.innerWidth + 1) failures.push(`${width}px EN/light: horizontal overflow`);
  }

  await context.close();
}

await browser.close();
if (failures.length) {
  console.error('SUBSCRIPTION_RESPONSIVE_SMOKE=FAIL');
  for (const failure of failures) console.error(failure);
  process.exit(1);
}
console.log(`SUBSCRIPTION_RESPONSIVE_SMOKE=PASS widths=${widths.length}`);
