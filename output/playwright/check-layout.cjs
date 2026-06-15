const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const out = path.resolve('output/playwright');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto('http://localhost:3001', { waitUntil: 'networkidle' });
  const tabs = [
    ['queries', 'Queries'],
    ['benchmark', 'Benchmark'],
    ['history', 'History'],
    ['status', 'System Status'],
  ];
  for (const [name, label] of tabs) {
    await page.getByRole('button', { name: label }).click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: true });
    const metrics = await page.evaluate(() => ({
      bodyScrollWidth: document.body.scrollWidth,
      bodyClientWidth: document.body.clientWidth,
      bodyScrollHeight: document.body.scrollHeight,
      bodyClientHeight: document.body.clientHeight,
      overlaps: Array.from(document.querySelectorAll('td, th, button, aside, section')).slice(0, 250).map((el) => {
        const r = el.getBoundingClientRect();
        return { tag: el.tagName, text: (el.textContent || '').trim().slice(0, 80), x: r.x, y: r.y, w: r.width, h: r.height };
      })
    }));
    fs.writeFileSync(path.join(out, `${name}.json`), JSON.stringify(metrics, null, 2));
  }
  await browser.close();
})();
