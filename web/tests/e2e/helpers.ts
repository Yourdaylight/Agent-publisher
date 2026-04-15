import { expect, test, type Page } from '@playwright/test';

// ── Shared helper ───────────────────────────────────────────────────────────
export const loginAsAdmin = async (page: Page) => {
  await page.goto('/login');
  // "管理员密钥" tab is the default active tab, no need to click it
  await page.getByPlaceholder('请输入访问密钥').fill(process.env.AP_ACCESS_KEY ?? 'agent-publisher-2024');
  // Use text-based locator for TDesign button (text may be inside a <span>)
  await page.getByText('登录', { exact: true }).click();
  // After login: redirects to /create
  await expect(page).toHaveURL(/\/create/, { timeout: 10_000 });
};
