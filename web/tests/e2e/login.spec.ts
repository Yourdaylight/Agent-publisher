import { expect, test } from '@playwright/test';

test.describe('登录链路', () => {
  test('密钥登录 API 返回 token', async ({ request }) => {
    const response = await request.post('/api/auth/login', {
      data: { access_key: process.env.AP_ACCESS_KEY ?? 'agent-publisher-2024' },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.token).toBeDefined();
    expect(data.is_admin).toBe(true);
  });

  test('错误密钥返回 401', async ({ request }) => {
    const response = await request.post('/api/auth/login', {
      data: { access_key: 'wrong-key-12345' },
    });
    expect(response.status()).toBe(401);
  });

  test('登录页面可访问', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByPlaceholder('请输入访问密钥')).toBeVisible({ timeout: 10_000 });
  });

  test('已登录用户重访 /login 自动跳回 /create', async ({ page }) => {
    // Login via API and inject token
    const accessKey = process.env.AP_ACCESS_KEY ?? 'agent-publisher-2024';
    const response = await page.request.post('/api/auth/login', {
      data: { access_key: accessKey },
    });
    const data = await response.json();
    await page.goto('/login');
    await page.evaluate((token) => {
      localStorage.setItem('ap_token', token);
      localStorage.setItem('ap_user', JSON.stringify({ email: '__admin__', is_admin: true }));
    }, data.token);

    // Revisit /login → should redirect
    await page.goto('/login');
    await expect(page).toHaveURL(/\/create/, { timeout: 10_000 });
  });
});
