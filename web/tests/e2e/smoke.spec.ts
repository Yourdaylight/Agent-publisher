import { expect, test } from '@playwright/test';
import { loginAsAdmin } from './helpers';

test.describe('关键页面冒烟', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('首页显示个人统计卡片', async ({ page }) => {
    await page.goto('/home');
    await expect(page.locator('.stat-row')).toBeVisible();
    // 4 stat cards: 公众号 / 文章 / 写作身份 / Credits
    await expect(page.locator('.stat-card')).toHaveCount(4);
    // Quick actions: 4 buttons
    await expect(page.locator('.quick-actions .action-card')).toHaveCount(4);
  });

  test('侧边栏"首页"菜单项高亮', async ({ page }) => {
    await page.goto('/home');
    // Sidebar should have 首页 menu item
    await expect(page.getByRole('menuitem', { name: '首页' })).toBeVisible();
  });

  test('热点列表可访问', async ({ page }) => {
    await page.goto('/trending');
    await expect(page).toHaveURL(/\/trending/);
    // Stats bar should be visible
    await expect(page.locator('.stats-bar')).toBeVisible();
  });

  test('AI 创作页可访问并显示模式选择', async ({ page }) => {
    await page.goto('/create');
    await expect(page).toHaveURL(/\/create/);
    // Mode chips should be visible in the AI panel
    await expect(page.locator('.mode-chips')).toBeVisible();
    // Three mode chips: 爆款二创 / 深度分析 / 热点总结
    await expect(page.locator('.mode-chip')).toHaveCount(3);
    // Bottom bar should have video button
    await expect(page.getByRole('button', { name: /生成视频/ })).toBeVisible();
  });

  test('文章管理页可访问', async ({ page }) => {
    await page.goto('/articles');
    await expect(page).toHaveURL(/\/articles/);
    await expect(page.getByText('文章管理')).toBeVisible();
  });

  test('会员中心可访问', async ({ page }) => {
    await page.goto('/membership');
    await expect(page).toHaveURL(/\/membership/);
    await expect(page.getByText(/Credits|会员|积分/)).toBeVisible();
  });

  test('设置页显示代理配置项', async ({ page }) => {
    await page.goto('/settings');
    await expect(page).toHaveURL(/\/settings/);
    await expect(page.getByText('微信发布 HTTP 代理')).toBeVisible();
    await expect(page.getByText('热榜自动刷新')).toBeVisible();
  });

  test('邀请码管理页可访问（管理员）', async ({ page }) => {
    await page.goto('/invite-codes');
    await expect(page).toHaveURL(/\/invite-codes/);
    await expect(page.getByText(/邀请码/)).toBeVisible();
  });

  test('未登录访问受保护页面重定向到 /login', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('/articles');
    await expect(page).toHaveURL(/\/login/);
    await context.close();
  });
});
