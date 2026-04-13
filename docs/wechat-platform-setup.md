# 微信第三方平台配置指南

本文档介绍如何配置微信第三方平台，实现公众号一键扫码授权。

## 前提条件

- 已注册[微信开放平台](https://open.weixin.qq.com)账号
- 服务器有公网可访问的 HTTPS 地址（微信回调要求）
- Agent Publisher 服务已正常运行

## 第一步：注册第三方平台

1. 登录 [微信开放平台](https://open.weixin.qq.com)
2. 进入「管理中心」→「第三方平台」→「创建第三方平台」
3. 选择「平台型第三方平台」
4. 填写基本信息：
   - **平台名称**：Agent Publisher（或自定义名称）
   - **平台简介**：AI 驱动的多账号公众号内容管理平台
   - **平台图标**：上传品牌 logo

## 第二步：配置开发资料

在第三方平台详情页 →「开发配置」中设置：

### 授权事件接收 URL

```
https://your-domain.com/api/wechat-platform/ticket-callback
```

> ⚠️ 必须是 HTTPS 地址。微信会每 10 分钟向此 URL 推送 `component_verify_ticket`。

### 消息校验 Token

自定义一个字符串（建议 32 位随机），例如：`mytoken1234567890abcdef`

### 消息加解密 Key

自定义一个 43 位字符串（由 a-z, A-Z, 0-9 组成），例如：`abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG`

### 授权回调 URI

```
https://your-domain.com/api/wechat-platform/auth-callback
```

## 第三步：选择权限集

至少勾选以下权限集：

| 权限集 | 说明 |
|--------|------|
| 消息管理权限 | 接收和回复用户消息 |
| 微信菜单权限 | 管理公众号菜单 |
| 素材管理权限 | 上传和管理图片/视频等素材 |
| 图文内容管理权限 | 创建和管理图文素材、草稿 |
| 用户管理权限 | 获取粉丝列表和基本信息 |
| 数据统计权限 | 获取阅读、分享等统计数据 |

## 第四步：配置 Agent Publisher

在 `.env` 文件中添加以下配置：

```env
# ============================================
# 微信第三方平台配置（扫码授权公众号）
# ============================================
# 在微信开放平台注册第三方平台后获取
# 配置后用户可通过扫码一键授权公众号，无需手动填写 AppID/AppSecret

# 第三方平台 AppID（在开放平台「开发配置」中查看）
WECHAT_PLATFORM_APPID=wx1234567890abcdef

# 第三方平台 AppSecret（在开放平台「开发配置」中查看，重置后复制）
WECHAT_PLATFORM_SECRET=your_app_secret_here

# 消息校验 Token（需与开放平台配置一致）
WECHAT_PLATFORM_TOKEN=mytoken1234567890abcdef

# 消息加解密 Key（需与开放平台配置一致，43位字符串）
WECHAT_PLATFORM_AES_KEY=abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG
```

配置完成后重启服务：

```bash
systemctl restart agent-publisher
# 或
bash update.sh
```

## 第五步：测试验证

### 1. 检查 ticket 推送

服务启动后，等待约 10 分钟，微信会推送 `component_verify_ticket`。

查看日志确认：

```bash
journalctl -u agent-publisher -f | grep component_verify_ticket
```

看到 `Stored component_verify_ticket successfully` 表示配置成功。

### 2. 添加测试公众号

在第三方平台未全网发布前，需要先将测试公众号添加到「授权测试公众号/小程序列表」：

1. 进入第三方平台详情 →「开发配置」
2. 在「授权测试公众号/小程序列表」中添加测试公众号的 AppID

### 3. 扫码授权

1. 打开 Agent Publisher 管理界面
2. 进入「公众号列表」页面
3. 点击「扫码授权添加」按钮
4. 使用公众号管理员微信扫描二维码
5. 确认授权后，公众号自动添加到列表

## 常见问题

### Q: 提示「component_verify_ticket not available」

**原因**：微信还没有推送 ticket，或推送地址配置不正确。

**解决**：
1. 确认授权事件接收 URL 配置正确（HTTPS）
2. 确认服务器防火墙允许微信服务器访问
3. 等待 10 分钟让微信推送下一次 ticket
4. 查看日志中是否有 ticket 回调请求

### Q: 扫码后提示「授权失败」

**原因**：可能是回调地址无法访问，或 AppSecret 配置错误。

**解决**：
1. 检查 `.env` 中的 `WECHAT_PLATFORM_SECRET` 是否正确
2. 确认授权回调 URI 配置正确
3. 检查服务器是否能正常响应 HTTPS 请求

### Q: 提示「该公众号没有此接口的权限」

**原因**：公众号本身没有该接口的权限（如未认证的订阅号）。

**解决**：确保公众号是认证的服务号或已认证的订阅号。

### Q: 已有的公众号还能用手动添加吗？

**可以**。手动添加和扫码授权两种方式完全兼容，已有账号无需迁移。
扫码授权的公众号 `auth_mode` 为 `platform`，手动添加的为 `manual`。

## 架构说明

```
授权流程:
1. 用户点击「扫码授权添加」
2. 后端获取 pre_auth_code → 生成授权链接
3. 前端展示二维码
4. 管理员扫码 → 微信跳转回调 URL
5. 后端用 auth_code 换取 authorizer_access_token
6. 创建 Account 记录（auth_mode=platform）
7. 前端自动刷新列表

Token 刷新:
- authorizer_access_token 有效期 2 小时
- 系统自动使用 authorizer_refresh_token 刷新
- refresh_token 有效期较长，由微信管理
```
