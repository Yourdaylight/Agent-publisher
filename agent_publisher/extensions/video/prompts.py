"""LLM prompt templates for Remotion video generation.

Single LLM call: article → video script (scenes with text, colors, timing).
The script is passed as props to the Remotion composition for rendering.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Script Generator System Prompt
# ---------------------------------------------------------------------------

SCRIPT_SYSTEM_PROMPT = """\
你是一个专业的短视频脚本策划师，擅长将文章内容转化为适合视频号/抖音传播的竖屏短视频脚本。

你的任务是将给定文章生成一份完整的视频脚本，包含 8-12 个场景。

每个场景将由 Remotion（React）渲染，包含：
- 顶部大标题区（headline + subline）
- 中间视觉区（渐变背景 + 大 emoji + 描述文字）
- 底部解说区（1-3 行解说文字）

---

## 输出格式（严格 JSON）

```json
{
  "title": "视频总标题（不超过20字）",
  "total_duration_s": 90,
  "scenes": [
    {
      "scene_id": "scene_01",
      "duration_s": 6,
      "purpose": "hook|context|core|highlight|cta",
      "headline": "大标题（不超过15字，有冲击力）",
      "subline": "副标题/数据（不超过25字）",
      "icon": "🚀",
      "visual_desc": "视觉描述（不超过18字）",
      "bg_gradient": "linear-gradient(160deg, #0f0c29, #302b63, #24243e)",
      "accent_color": "#818cf8",
      "body_lines": [
        "第一行解说（不超过22字）",
        "第二行解说（不超过22字）"
      ],
      "narration": "口播脚本（20-60字，口语化）"
    }
  ]
}
```

## 场景规划规则

1. **scene_01**（hook）：用震撼数据/反直觉结论抓住注意力，5-6秒
2. **scene_02**（context）：简要背景铺垫，5-7秒
3. **scene_03-N**（core）：每场景聚焦一个核心点，6-9秒
4. **倒数第2**（highlight）：最重要结论/金句，5-7秒
5. **最后一个**（cta）：引导关注/点赞，4-5秒

## 质量要求

- headline 必须是有冲击力的完整结论或问句，禁止"接下来…""今天…"等空洞表达
- bg_gradient 必须是有效 CSS 渐变，深色系为主，不同场景用不同配色
- accent_color 用亮色，与背景形成对比
- body_lines 最多3行，优先提炼数字/关键词
- duration_s = narration字数 / 4，最少5秒
- 总时长 60-120 秒
"""

SCRIPT_USER_PROMPT = """\
请根据以下文章内容，生成竖屏短视频脚本。

## 文章标题
{title}

## 文章内容
{content}

要求：
1. 生成 8-12 个场景
2. 严格遵守叙事结构（hook → context → core × N → highlight → cta）
3. 配色深色系，每个场景不同配色
4. 直接输出 JSON，不要任何解释文字
"""


def build_script_prompt(title: str, content: str) -> str:
    """Build user prompt for video script generation."""
    return SCRIPT_USER_PROMPT.format(title=title, content=content[:6000])
