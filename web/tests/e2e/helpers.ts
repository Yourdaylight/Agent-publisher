import { expect, test, type Page } from '@playwright/test';

// ── Shared helper ───────────────────────────────────────────────────────────
export const loginAsAdmin = async (page: Page) => {
  await page.goto('/login');
  // Click "管理员密钥" tab (TDesign tabs don't use role="tab", use text-based locator)
  await page.locator('.t-tabs__nav-item', { hasText: '管理员密钥' }).click();
  await page.getByPlaceholder('请输入访问密钥').fill(process.env.AP_ACCESS_KEY ?? 'agent-publisher-2024');
  await page.getByRole('button', { name: '登录' }).click();
  // After login: redirects to /create
  await expect(page).toHaveURL(/\/create/, { timeout: 10_000 });
};
