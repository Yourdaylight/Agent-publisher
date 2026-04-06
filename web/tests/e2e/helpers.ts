import { expect, test, type Page } from '@playwright/test';

// ── Shared helper ───────────────────────────────────────────────────────────
export const loginAsAdmin = async (page: Page) => {
  await page.goto('/login');
  // Click "密钥登录" tab (first tab, access-key mode)
  await page.getByRole('tab', { name: '密钥登录' }).click();
  await page.getByPlaceholder('请输入访问密钥').fill(process.env.AP_ACCESS_KEY ?? 'agent-publisher-2024');
  await page.getByRole('button', { name: '登录' }).click();
  // After login: redirects to /home
  await expect(page).toHaveURL(/\/home/, { timeout: 10_000 });
};
