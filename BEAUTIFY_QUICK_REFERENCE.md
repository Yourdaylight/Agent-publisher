# Article Beautification - Quick Reference

---

## 🎯 Three Beautification Pathways

### 1. Automatic (On Markdown Save)
**When**: User edits Markdown in editor  
**Flow**: Markdown → Wenyan/Regex → WebChat inline styles  
**Cost**: 0 credits  
**Trigger**: `PUT /api/articles/{id}` with `{content: markdown}`

### 2. Manual Theme Selection
**When**: User clicks "Render Markdown Preview"  
**Flow**: Markdown → Wenyan (theme) → WebChat inline styles  
**Cost**: 0 credits  
**Endpoint**: `POST /api/articles/{id}/beautify?theme=orangeheart`

### 3. AI Beautification
**When**: User wants professional LLM-enhanced layout  
**Flow**: HTML → LLM (detailed brief) → Enhanced HTML  
**Cost**: 3 credits  
**Endpoint**: `POST /api/articles/{id}/ai-beautify?style_hint=...`

---

## 📁 Key Files

| File | What It Does | Key Function |
|------|-------------|--------------|
| `article_service.py:664` | Markdown→HTML rendering | `_markdown_to_html()` |
| `article_service.py:753` | Smart update logic | `update_article()` |
| `article_service.py:1492` | LLM beautification | `ai_beautify_html()` |
| `wechat_style_service.py:176` | Inline CSS injection | `inject_styles()` |
| `articles.py:239` | Beautify endpoint | `beautify_article()` |
| `articles.py:272` | AI beautify endpoint | `ai_beautify_article()` |

---

## 🔄 Smart Update Detection

```python
# When user edits Markdown:
PUT /api/articles/42 { "content": "# New markdown" }
  ↓
# Backend checks:
if "content" in updates and "html_content" NOT in updates:
    # AUTO-RENDER: Re-render to HTML
    article.html_content = _markdown_to_html(article.content)
else:
    # NO AUTO-RENDER: Use explicit HTML/keep existing
    # (User is overriding)
```

**Key Insight**: Backend intelligently detects intent based on what fields are provided.

---

## 🎨 Inline Style Injection

```python
# WeChat doesn't support <style> tags or CSS classes
# Solution: Inject inline styles via style attributes

from agent_publisher.services.wechat_style_service import WeChatStyleService

html = "<h1>Title</h1><p>Content</p>"
styled = WeChatStyleService.inject_styles(html)
# Result:
# <h1 style="font-size: 24px; ...">Title</h1>
# <p style="font-size: 16px; ...">Content</p>
```

**Non-Destructive**: Tags with existing `style` attributes are NEVER overwritten.

---

## 📐 Predefined Inline Styles

| Element | Style | Key Properties |
|---------|-------|-----------------|
| `<p>` | Paragraph | 16px, line-height: 1.75, #3f3f3f, 20px margin |
| `<h1>` | Title | 24px bold, centered, #1a1a1a |
| `<h2>` | Section | 22px bold, bottom border #07C160 |
| `<h3>` | Subsection | 20px bold |
| `<a>` | Link | #07C160 green, bottom border |
| `<blockquote>` | Quote | Card style, left green border |
| `<pre>` | Code block | Monospace, gray bg, overflow scroll |
| `<img>` | Image | 100% max-width, rounded, centered |
| `<ul>`, `<ol>` | Lists | Proper padding & margins |

---

## 🏗️ Two-Tier Rendering

### Tier 1: Wenyan CLI (Preferred)
```bash
which wenyan                    # Check if installed
wenyan render -f file.md -t default  # Render with theme
```
✅ Professional output  
✅ Multiple themes  
❌ Requires external tool

### Tier 2: Basic Regex Fallback
✅ No dependencies  
✅ Fast  
❌ Limited Markdown support

```python
# Auto-fallback in code:
_markdown_to_html() →
  ├─ Try: wenyan render
  ├─ Fallback: _basic_markdown_to_html()  # Regex based
  └─ Always: WeChatStyleService.inject_styles()
```

---

## 🤖 AI Beautification LLM Prompt

**System Role**: Top WeChat public account design expert

**Key Instructions**:
- All styles must be inline (`style` attribute)
- No CSS classes or IDs
- Preserve all original content
- Reference top publications (虎嗅, 36氪, 少数派)
- Choose color scheme based on content:
  - 🟢 Scheme A: WeChat green (#07C160)
  - 🔵 Scheme B: Tech blue (#2563eb)
  - ⚫ Scheme C: Business gray (#374151)

**H2 Styling Ideas** (pick one style for article):
- Left 4px color bar + text
- Bottom gradient underline
- Background rounded card
- Centered with decorative elements

**User Prompt**:
```
Please beautify this HTML:
{html_content}

User additional requirements:
{style_hint}
```

---

## 💳 Credit System

**AI Beautification Cost**: 3 credits per request

**Flow**:
1. Check balance: `balance >= 3`?
2. If NO: Return 402 (Payment Required)
3. If YES: Consume 3 credits
4. Process beautification
5. If error: Refund 3 credits

---

## 🖼️ Frontend Editing Modes

### ArticleEditorPage.vue Tabs

| Tab | Content | Save Behavior |
|-----|---------|---------------|
| **TipTap** | WYSIWYG editor | `{html_content: richHtml}` |
| **Markdown** | Raw text | `{content: markdown}` → auto-renders |
| **HTML** | Source code | `{html_content: htmlSource}` |
| **Preview** | Read-only | Shows current render |

### Save Logic

```javascript
const buildPayload = () => {
  if (editMode === 'markdown') {
    return { content: form.content };  // Auto-renders
  } else {
    return { html_content: form.html_content };  // As-is
  }
};
```

---

## 🔗 API Endpoints Cheat Sheet

```bash
# Get article
GET /api/articles/{id}

# Update (auto-renders if markdown)
PUT /api/articles/{id}
{ "title": "...", "content": "# Markdown..." }

# Manual beautify with theme
POST /api/articles/{id}/beautify
{ "theme": "orangeheart" }

# AI beautify (3 credits)
POST /api/articles/{id}/ai-beautify
{ "style_hint": "blue professional theme" }

# View publish preview
GET /api/articles/{id}/publish-records
```

---

## 🐛 Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| "wenyan not found" | CLI not installed | `npm install -g @wenyan-md/cli` |
| HTML shows as text | Using `v-text` | Use `v-html` in template |
| Styles missing in WeChat | Using `<style>` tags | Use inline `style` attributes only |
| 402 Payment Required | No credits | Recharge or reduce cost |
| LLM returns error | Service not configured | Check `.env`: `DEFAULT_LLM_*` settings |

---

## 📊 Rendering Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Markdown→HTML (Wenyan) | 100-500ms | Professional |
| Markdown→HTML (Regex) | 10-50ms | Basic |
| Style Injection | 50-250ms | HTML parsing |
| AI Beautification | 2-10s | LLM call + processing |

---

## ✅ Best Practices

1. **Always preserve Markdown source**
   - Never delete `content` field
   - Allows re-rendering with new themes

2. **Auto-render detection works if**
   - You send `{content: markdown}` alone
   - Backend auto-detects and renders
   - User doesn't need to explicitly beautify

3. **Manual override works if**
   - You send `{html_content: html}`
   - Backend respects and stores as-is
   - No re-rendering happens

4. **For AI beautification**
   - Start with basic rendered HTML (not Markdown)
   - Provide optional `style_hint` for guidance
   - Budget 3 credits per article

5. **WeChat compatibility**
   - Always use inline styles
   - Test rendering in WeChat OA editor
   - Avoid absolute sizing, use relative units

---

## 🔗 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Vue Components)                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ ArticleEditorPage: Rich | Markdown | HTML | Preview     │ │
│  └─────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │ PUT /api/articles/{id}
                         ▼
         ┌───────────────────────────────────────────┐
         │ Update Logic (article_service.py:753)     │
         │ Smart: Detect what fields are provided    │
         └───────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   Markdown only    HTML only         Both
        │                │                │
        ▼                ▼                ▼
   Auto-render    Keep as-is         Use HTML
        │
        ▼
  ┌──────────────────────────────────────┐
  │ _markdown_to_html()                   │
  │ ┌────────────────────────────────────┐│
  │ │ Tier 1: Wenyan CLI (if available)  ││
  │ │ Tier 2: Regex Fallback             ││
  │ └────────────────────────────────────┘│
  │              │                        │
  │              ▼                        │
  │ WeChatStyleService.inject_styles()    │
  │ (Add inline CSS to all tags)          │
  └──────────────────────────────────────┘
        │
        ▼
    HTML Content
        │
        ▼
  Saved to DB: article.html_content
        │
        ▼
┌─────────────────────────────┐
│ Frontend Preview Updates    │
│ (v-html directive)          │
└─────────────────────────────┘
```

---

## 📚 Related Resources

- Full documentation: `BEAUTIFY_PIPELINE.md`
- Article model: `agent_publisher/models/article.py`
- Service code: `agent_publisher/services/article_service.py`
- Tests: `tests/test_wechat_style_service.py`, `tests/test_article_service.py`

---

**Last Updated**: April 17, 2026  
**Status**: ✅ Complete
