const { test } = require('@playwright/test');

test('capture current app layouts', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
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
    await page.screenshot({ path: `output/playwright/${name}.png`, fullPage: true });
  }
});
