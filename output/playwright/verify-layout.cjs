const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  await page.goto('http://localhost:3001', { waitUntil: 'networkidle' });

  const report = {};
  async function clickNav(name) {
    await page.getByRole('button', { name }).click();
    await page.waitForTimeout(700);
  }

  await clickNav('Queries');
  await page.screenshot({ path: 'output/playwright/queries-layout.png', fullPage: true });
  report.queries = await page.evaluate(() => {
    const row = document.querySelector('tbody tr');
    const cells = row ? Array.from(row.querySelectorAll('td')).map((td) => {
      const r = td.getBoundingClientRect();
      return { top: Math.round(r.top), height: Math.round(r.height), text: (td.textContent || '').trim().slice(0, 80) };
    }) : [];
    return { cells };
  });

  await clickNav('Benchmark');
  await page.screenshot({ path: 'output/playwright/benchmark-layout.png', fullPage: true });
  report.benchmark = await page.evaluate(() => {
    const sections = Array.from(document.querySelectorAll('h3,h4,h5')).map((el) => {
      const r = el.getBoundingClientRect();
      return { text: (el.textContent || '').trim(), top: Math.round(r.top) };
    });
    return { sections };
  });

  await clickNav('History');
  await page.screenshot({ path: 'output/playwright/history-layout.png', fullPage: true });
  report.history = await page.evaluate(() => {
    const labels = Array.from(document.querySelectorAll('aside section')).map((section) => (section.textContent || '').trim().slice(0, 80));
    return { labels };
  });

  await clickNav('System Status');
  await page.screenshot({ path: 'output/playwright/status-layout.png', fullPage: true });
  report.status = await page.evaluate(() => {
    const text = document.body.innerText;
    return {
      hasRuntime: text.includes('Runtime Parameters'),
      hasEmbeddingModel: text.includes('BAAI/bge-small-en-v1.5'),
      hasCacheTtl: text.includes('Cache TTL'),
      hasHistoryDb: text.includes('History DB'),
    };
  });

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch((err) => { console.error(err); process.exit(1); });
