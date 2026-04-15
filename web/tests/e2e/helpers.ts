import { expect, test, type Page } from '@playwright/test';

// ── Shared helper ───────────────────────────────────────────────────────────
export const loginAsAdmin = async (page: Page) => {
  // Login via API directly (more reliable than UI interaction in CI)
  const accessKey = process.env.AP_ACCESS_KEY ?? 'agent-publisher-2024';
  const response = await page.request.post('/api/auth/login', {
    data: { access_key: accessKey },
  });
  if (!response.ok()) {
    throw new Error(`Login API failed: ${response.status()} ${await response.text()}`);
  }
  const data = await response.json();
  // Inject token into localStorage so the Vue app recognizes the session
  await page.goto('/login');
  await page.evaluate(
    ({ token, user }) => {
      localStorage.setItem('ap_token', token);
      localStorage.setItem('ap_user', JSON.stringify(user));
    },
    {
      token: data.token,
      user: { email: data.email || '__admin__', is_admin: data.is_admin ?? true },
    },
  );
  // Navigate to the main page
  await page.goto('/create');
  await expect(page).toHaveURL(/\/create/, { timeout: 10_000 });
};
