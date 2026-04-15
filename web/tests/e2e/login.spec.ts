import { expect, test } from '@playwright/test';

test.describe('登录链路', () => {
  test('密钥登录成功跳转创作页', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('tab', { name: '管理员密钥' }).click();
    await page.getByPlaceholder('请输入访问密钥').fill(
      process.env.AP_ACCESS_KEY ?? 'agent-publisher-2024',
    );
    await page.getByRole('button', { name: '登录' }).click();

    await expect(page).toHaveURL(/\/create/, { timeout: 10_000 });
  });

  test('错误密钥展示错误提示', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('tab', { name: '管理员密钥' }).click();
    await page.getByPlaceholder('请输入访问密钥').fill('wrong-key-12345');
    await page.getByRole('button', { name: '登录' }).click();

    await expect(page.getByText(/密钥|错误|失败|invalid/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test('邀请码 Tab 可见', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('tab', { name: '邀请码体验' })).toBeVisible();
  });

  test('已登录用户重访 /login 自动跳回 /create', async ({ page }) => {
    // First login
    await page.goto('/login');
    await page.getByRole('tab', { name: '管理员密钥' }).click();
    await page.getByPlaceholder('请输入访问密钥').fill(
      process.env.AP_ACCESS_KEY ?? 'agent-publisher-2024',
    );
    await page.getByRole('button', { name: '登录' }).click();
    await expect(page).toHaveURL(/\/create/);

    // Revisit /login → should redirect
    await page.goto('/login');
    await expect(page).toHaveURL(/\/create/);
  });
});
