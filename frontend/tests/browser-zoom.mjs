// Native Chromium tab zoom, with an extension confined to an owned QA profile.
// deviceScaleFactor alone changes density and does not test browser zoom.
import { chromium } from 'playwright';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

export async function zoomBrowser() {
  const root = await mkdtemp(path.join(tmpdir(), 'pvnetwork-zoom-'));
  let context;
  try {
    const extension = path.join(root, 'extension');
    await mkdir(extension);
    await writeFile(path.join(extension, 'manifest.json'), JSON.stringify({
      manifest_version: 3, name: 'PVNetwork owned zoom QA', version: '1.0',
      permissions: ['tabs'], background: { service_worker: 'worker.js' },
    }));
    await writeFile(path.join(extension, 'worker.js'), 'chrome.runtime.onInstalled.addListener(() => {});');
    context = await chromium.launchPersistentContext(path.join(root, 'profile'), {
      headless: true, channel: 'chromium', reducedMotion: 'reduce',
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`],
    });
    const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
    return {
      context,
      async setZoom(page, zoom) {
        const url = page.url();
        if (!/^http:\/\/127\.0\.0\.1:\d+\//.test(url)) throw new Error('Zoom QA permits only owned loopback fixtures');
        await worker.evaluate(async ({ url, zoom }) => {
          const tab = (await chrome.tabs.query({})).find(item => item.url === url);
          if (!tab) throw new Error('Owned QA tab missing');
          await chrome.tabs.setZoom(tab.id, zoom);
          const actual = await chrome.tabs.getZoom(tab.id);
          if (Math.abs(actual - zoom) > 0.001) throw new Error('Native browser zoom was not applied');
        }, { url, zoom });
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      },
      async close() {
        await context.close();
        await rm(root, { recursive: true, force: true });
      },
    };
  } catch (error) {
    await context?.close();
    await rm(root, { recursive: true, force: true });
    throw error;
  }
}
