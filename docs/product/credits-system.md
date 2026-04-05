# Credits 计费体系设计

> 最后更新：2026-04-03

## 设计理念

**按用量付费，而非按时间订阅**

与 baolem 的月卡/年卡模式不同，Agent Publisher 采用 Credits 体系：
- 用户购买 Credits，按实际使用量扣减
- 不同操作消耗不同数量的 Credits
- 未使用的 Credits 不过期（套餐内赠送的除外）
- 为后续扩展新的内容形态（视频等）提供灵活定价空间

## Credits 消耗定价

### 内容生成

| 操作 | 消耗 | 说明 |
|------|------|------|
| AI 生成文章 | 10 Credits | 完整文章（标题+摘要+正文） |
| AI 段落改写 | 2 Credits | 选中段落重写 |
| AI 扩写/缩写 | 3 Credits | 内容扩展或压缩 |
| AI 标题生成 | 1 Credit | 生成多个标题候选 |

### 配图生成

| 操作 | 消耗 | 说明 |
|------|------|------|
| 混元文生图（标准） | 5 Credits | 一张 AI 配图 |
| 混元文生图（高清） | 8 Credits | 高分辨率版本 |
| 封面图生成 | 5 Credits | 公众号封面 |

### 视频生成（v3.0 规划）

| 操作 | 消耗 | 说明 |
|------|------|------|
| 短视频渲染 | 20 Credits | Remotion 渲染一个短视频 |
| TTS 语音合成 | 5 Credits | 文字转语音轨道 |
| 视频模板预览 | 0 Credits | 预览不收费 |

### 免费操作

| 操作 | 消耗 | 说明 |
|------|------|------|
| 浏览热点 | 0 | 发现页无限浏览 |
| 收藏素材 | 0 | 素材管理不收费 |
| 手动编辑 | 0 | 纯手工编辑不涉及 AI |
| 发布到草稿箱 | 0 | 推送操作不收费 |
| 热点导出 CSV | 1 Credit | 批量数据导出 |

## 套餐包设计

### 月度套餐

| 套餐 | 月 Credits | 价格 | 定位 | 核心限制 |
|------|-----------|------|------|---------|
| **免费版** | 50 | ¥0 | 体验 | 1个公众号，基础功能 |
| **基础版** | 500 | ¥59/月 | 个人自媒体 | 3个公众号，全部功能 |
| **专业版** | 2000 | ¥129/月 | 专业运营 | 10个公众号，优先队列 |

### 年度套餐

| 套餐 | 年 Credits | 价格 | 折扣 |
|------|-----------|------|------|
| **年度专业版** | 30000 | ¥999/年 | 相当于 ¥83/月 |

### 加油包（随时购买，不过期）

| 包名 | Credits | 价格 | 单价 |
|------|---------|------|------|
| 小包 | 100 | ¥15 | ¥0.15/Credit |
| 中包 | 500 | ¥59 | ¥0.118/Credit |
| 大包 | 2000 | ¥199 | ¥0.0995/Credit |

## 数据模型

### credits_balance（用户余额）

```
user_id          - 用户ID
total_credits    - 总余额
used_credits     - 已使用
free_credits     - 免费额度（每月重置）
paid_credits     - 付费额度（不过期）
updated_at       - 最后更新时间
```

### credits_transaction（消耗记录）

```
id               - 记录ID
user_id          - 用户ID
operation_type   - 操作类型（generate_article/generate_image/...）
credits_amount   - 变动数量（负数=消耗，正数=充值）
balance_after    - 变动后余额
reference_id     - 关联对象ID（article_id / image_id / ...）
description      - 描述
created_at       - 时间
```

### credits_package（套餐定义）

```
id               - 套餐ID
name             - 套餐名
package_type     - 类型（monthly/yearly/addon）
credits_amount   - 包含 Credits
price_cents      - 价格（分）
max_accounts     - 公众号上限
features         - 功能列表 JSON
is_active        - 是否启用
```

## 前端交互

### Credits 仪表盘组件

在顶部导航栏常驻显示：

```
[Credits: 450 ▼]
```

点击展开下拉：
```
┌─────────────────────────┐
│ 剩余 Credits: 450       │
│ ├ 免费额度: 20/50       │
│ ├ 付费额度: 430         │
│                         │
│ 本月消耗: 50 Credits    │
│ ├ 生成文章: 30 (3次)    │
│ ├ AI配图: 15 (3张)      │
│ └ 段落改写: 5 (2次)     │
│                         │
│ [购买 Credits]  [详情→]  │
└─────────────────────────┘
```

### 消耗前确认

在执行 AI 操作前弹出：

```
┌─────────────────────────┐
│ 确认消耗                 │
│                         │
│ 操作：生成文章           │
│ 消耗：10 Credits        │
│ 余额：450 → 440        │
│                         │
│ □ 不再提醒              │
│ [取消]  [确认生成]       │
└─────────────────────────┘
```

### 余额不足拦截

```
┌─────────────────────────┐
│ ⚠️ Credits 不足          │
│                         │
│ 需要：10 Credits        │
│ 当前：3 Credits         │
│                         │
│ [购买加油包]  [升级套餐]  │
└─────────────────────────┘
```

## 后端实现要点

### API 端点

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/credits/balance` | 查询当前余额 |
| GET | `/api/credits/transactions` | 消耗记录列表 |
| POST | `/api/credits/check` | 预检查余额是否充足 |
| POST | `/api/credits/consume` | 扣减 Credits |
| POST | `/api/credits/recharge` | 充值（人工/自动） |
| GET | `/api/credits/packages` | 套餐列表 |

### 扣减流程

```
1. 前端调用 AI 操作
2. 后端 middleware 拦截
3. 检查 credits_balance >= cost
4. 乐观锁扣减余额
5. 写入 credits_transaction
6. 执行实际操作
7. 如果操作失败，退回 Credits
```

### 每月免费额度重置

```python
# 每月1日 00:00 执行
async def reset_free_credits():
    """重置所有用户的免费月度额度"""
    await db.execute(
        update(CreditsBalance)
        .values(free_credits=case(
            (CreditsBalance.plan_type == 'free', 50),
            (CreditsBalance.plan_type == 'basic', 500),
            (CreditsBalance.plan_type == 'pro', 2000),
        ))
    )
```
