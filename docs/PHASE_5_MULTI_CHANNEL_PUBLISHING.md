# Phase 5: Multi-Channel Publishing
## Publish Generated Articles to Telegram, Slack, Email, and Custom Webhooks

**Phase Duration:** 1 week  
**Timeline:** Week 6-7 of integration project  
**Depends On:** Phase 1 ✅, Phase 2 ✅, Phase 3 ✅, Phase 4 ✅  
**Status:** Planning  

---

## Objectives

### Primary Goals
1. **Expand Publishing Channels** - From 1 (WeChat) to 7+ channels
2. **Unified Publishing API** - Single interface for all channels
3. **Template System** - Customize content per channel
4. **Delivery Tracking** - Know where articles were published
5. **Cross-Channel Analytics** - Unified metrics across all channels
6. **Prepare Phase 6** - Ready for production deployment

### Success Criteria
- ✅ Articles publishable to 7+ channels
- ✅ Publishing latency <5s per channel
- ✅ Delivery success rate >98%
- ✅ Template system fully functional
- ✅ Unified publishing API
- ✅ Cross-channel analytics
- ✅ Zero breaking changes
- ✅ Ready for production

---

## Current State vs. Target

### Today (Before Phase 5)

```
Agent Publisher Publishing
│
└─ WeChat Official Account (only)
   ├─ Article posted to WechatOA
   ├─ Audience: ~thousands per OA
   └─ Channel: Single (WeChat)
```

### After Phase 5

```
Agent Publisher Publishing - Multi-Channel
│
├─ WeChat Official Account (existing)
│  └─ Desktop + Mobile apps
│
├─ Telegram (via TrendRadar)
│  └─ Subscribers to notification channel
│
├─ Slack (via TrendRadar)
│  └─ Team members + channels
│
├─ Email (via TrendRadar)
│  └─ Email subscribers
│
├─ Custom Webhook (via TrendRadar)
│  └─ Any HTTP endpoint
│
├─ RSS Feed (new)
│  └─ Feed readers
│
└─ Analytics Dashboard
   ├─ Views per channel
   ├─ Engagement per channel
   ├─ Best performing channels
   └─ Cross-channel metrics
```

---

## Implementation Plan

### Week 1: Backend Infrastructure

#### Task 5.1: Create Publication Channel Models
**File:** `agent_publisher/models/publication_channel.py`

```python
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class PublicationChannel(Base):
    """Configuration for publishing channels."""
    
    __tablename__ = "publication_channels"
    
    id: int = Column(Integer, primary_key=True, index=True)
    agent_id: int = Column(Integer, ForeignKey("agent.id"), index=True)
    
    # Channel information
    channel_type: str = Column(String(50), index=True)  # "wechat", "telegram", "slack", "email", "webhook", "rss"
    channel_name: str = Column(String(255))  # User-friendly name
    
    # Configuration (encrypted in production)
    channel_config: Dict[str, Any] = Column(JSON)
    # Format:
    # Telegram: {"bot_token": "...", "chat_id": "..."}
    # Slack: {"webhook_url": "...", "channel": "#news"}
    # Email: {"recipients": ["email1@example.com"], "from_name": "Publisher"}
    # Webhook: {"url": "...", "auth_token": "..."}
    # RSS: {"feed_title": "...", "feed_url": "..."}
    # WeChat: {"official_account_id": "...", "app_id": "..."}
    
    # Publishing settings
    is_enabled: bool = Column(Boolean, default=True, index=True)
    template_id: Optional[int] = Column(Integer, ForeignKey("publication_templates.id"))
    auto_publish: bool = Column(Boolean, default=False)  # Auto-publish all articles
    publish_schedule: Optional[str] = Column(String(255))  # Cron expression (if not immediate)
    
    # Metadata
    description: Optional[str] = Column(String(500))
    tags: List[str] = Column(JSON, default=[])
    metadata: Dict[str, Any] = Column(JSON, default={})
    
    # Audit
    created_at: datetime = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_published_at: Optional[datetime] = Column(DateTime, nullable=True)
    
    # Soft delete
    deleted_at: Optional[datetime] = Column(DateTime, nullable=True)

class PublicationTemplate(Base):
    """Templates for formatting articles per channel."""
    
    __tablename__ = "publication_templates"
    
    id: int = Column(Integer, primary_key=True)
    agent_id: int = Column(Integer, ForeignKey("agent.id"), index=True)
    
    # Template info
    name: str = Column(String(255))
    channel_type: str = Column(String(50))  # "telegram", "slack", "email", etc.
    
    # Template content
    title_template: str = Column(String(500))  # Markdown, can include {variables}
    body_template: str = Column(String(5000))  # Markdown, can include {variables}
    footer_template: Optional[str] = Column(String(1000))
    
    # Available variables: {title}, {summary}, {content}, {url}, {platform}, {hotness}, {agent_name}
    
    # Formatting options
    max_length: Optional[int] = Column(Integer)  # Max chars for this channel
    strip_images: bool = Column(Boolean, default=False)  # Remove images for text-only channels
    strip_html: bool = Column(Boolean, default=False)  # Use plain text
    
    is_default: bool = Column(Boolean, default=False)
    
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PublicationRecord(Base):
    """Track all published articles."""
    
    __tablename__ = "publication_records"
    
    id: int = Column(Integer, primary_key=True)
    article_id: int = Column(Integer, ForeignKey("article.id"), index=True)
    channel_id: int = Column(Integer, ForeignKey("publication_channels.id"), index=True)
    
    # Publishing details
    status: str = Column(String(50), index=True)  # "pending", "sent", "failed", "scheduled"
    published_url: Optional[str] = Column(String(2000))  # URL to published article
    error_message: Optional[str] = Column(String(1000))
    
    # Metrics
    views: int = Column(Integer, default=0)
    clicks: int = Column(Integer, default=0)
    shares: int = Column(Integer, default=0)
    reactions: int = Column(Integer, default=0)
    
    # Metadata
    platform_response: Dict[str, Any] = Column(JSON)  # Raw response from platform API
    metadata: Dict[str, Any] = Column(JSON)
    
    published_at: datetime = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### Task 5.2: Create Channel Publisher Service
**File:** `agent_publisher/services/multi_channel_publisher_service.py`

```python
"""
Service for publishing articles to multiple channels.

Responsibilities:
1. Route articles to appropriate channels
2. Format content per channel template
3. Execute publishing to external services
4. Track delivery status
5. Handle retries and failures
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MultiChannelPublisherService:
    """Publish articles to multiple channels."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.publishers: Dict[str, 'ChannelPublisher'] = {
            'wechat': WeChatPublisher(),
            'telegram': TelegramPublisher(),
            'slack': SlackPublisher(),
            'email': EmailPublisher(),
            'webhook': WebhookPublisher(),
            'rss': RSSPublisher(),
        }
    
    async def publish_article(
        self,
        article_id: int,
        agent_id: int,
        channel_ids: Optional[List[int]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Publish article to specified channels.
        
        Args:
            article_id: Article to publish
            agent_id: Agent that owns the article
            channel_ids: Specific channels (None = all enabled)
            dry_run: Don't actually publish, just validate
        
        Returns:
            {
                "status": "success|partial|failed",
                "total_channels": X,
                "successful": Y,
                "failed": Z,
                "results": [
                    {
                        "channel_id": 1,
                        "channel_type": "telegram",
                        "status": "sent",
                        "url": "...",
                        "error": null
                    }
                ]
            }
        """
        # Load article and channels
        article = await self.db.get(Article, article_id)
        if not article:
            raise ValueError(f"Article {article_id} not found")
        
        channels = await self._get_channels(agent_id, channel_ids)
        if not channels:
            return {
                "status": "failed",
                "error": "No enabled channels found",
                "results": []
            }
        
        # Publish to each channel
        results = []
        for channel in channels:
            result = await self._publish_to_channel(
                article, channel, dry_run
            )
            results.append(result)
        
        # Aggregate results
        successful = sum(1 for r in results if r["status"] == "sent")
        failed = sum(1 for r in results if r["status"] == "failed")
        
        return {
            "status": "success" if failed == 0 else ("partial" if successful > 0 else "failed"),
            "total_channels": len(channels),
            "successful": successful,
            "failed": failed,
            "results": results
        }
    
    async def _publish_to_channel(
        self,
        article: Article,
        channel: PublicationChannel,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Publish article to single channel."""
        try:
            logger.info(
                "Publishing article %d to channel %d (%s)",
                article.id, channel.id, channel.channel_type
            )
            
            # Get publisher for this channel type
            publisher = self.publishers.get(channel.channel_type)
            if not publisher:
                raise ValueError(f"Unknown channel type: {channel.channel_type}")
            
            # Format article for channel
            formatted = await self._format_article(article, channel)
            
            # Publish if not dry run
            if not dry_run:
                result = await publisher.publish(formatted, channel.channel_config)
            else:
                result = {
                    "status": "success",
                    "url": "https://example.com/dry-run",
                    "message_id": "dry-run-123"
                }
            
            # Record publication
            await self._record_publication(
                article.id, channel.id, result
            )
            
            return {
                "channel_id": channel.id,
                "channel_type": channel.channel_type,
                "status": "sent",
                "url": result.get("url"),
                "message_id": result.get("message_id"),
                "error": None
            }
        
        except Exception as e:
            logger.error(
                "Failed to publish article %d to channel %d: %s",
                article.id, channel.id, e, exc_info=True
            )
            
            return {
                "channel_id": channel.id,
                "channel_type": channel.channel_type,
                "status": "failed",
                "url": None,
                "error": str(e)
            }
    
    async def _format_article(
        self,
        article: Article,
        channel: PublicationChannel
    ) -> Dict[str, Any]:
        """Format article using channel template."""
        # Load template
        template = await self._get_template(channel)
        
        # Build variable context
        context = {
            "title": article.title,
            "summary": article.summary or article.title,
            "content": article.content,
            "url": article.url or "",
            "platform": article.source_platform or "unknown",
            "agent_name": channel.agent.name if channel.agent else "Agent Publisher",
        }
        
        # Format using template
        formatted_title = template.title_template.format(**context)
        formatted_body = template.body_template.format(**context)
        formatted_footer = (
            template.footer_template.format(**context)
            if template.footer_template else ""
        )
        
        # Enforce length limits
        if template.max_length:
            content = f"{formatted_title}\n\n{formatted_body}\n\n{formatted_footer}"
            if len(content) > template.max_length:
                content = content[:template.max_length-3] + "..."
        
        return {
            "title": formatted_title,
            "body": formatted_body,
            "footer": formatted_footer,
            "images": [] if template.strip_images else (article.images or []),
            "channel_type": channel.channel_type,
        }
    
    async def _get_channels(
        self,
        agent_id: int,
        channel_ids: Optional[List[int]] = None
    ) -> List[PublicationChannel]:
        """Get enabled channels for agent."""
        from sqlalchemy import select
        
        query = select(PublicationChannel).where(
            PublicationChannel.agent_id == agent_id,
            PublicationChannel.is_enabled == True,
            PublicationChannel.deleted_at.is_(None)
        )
        
        if channel_ids:
            query = query.where(PublicationChannel.id.in_(channel_ids))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def _get_template(
        self,
        channel: PublicationChannel
    ) -> PublicationTemplate:
        """Get template for channel."""
        # Use channel's template if assigned, else default for type
        if channel.template_id:
            return await self.db.get(PublicationTemplate, channel.template_id)
        
        from sqlalchemy import select
        query = select(PublicationTemplate).where(
            PublicationTemplate.agent_id == channel.agent_id,
            PublicationTemplate.channel_type == channel.channel_type,
            PublicationTemplate.is_default == True
        )
        
        result = await self.db.execute(query)
        template = result.scalars().first()
        
        if not template:
            # Create default template if missing
            template = self._create_default_template(channel)
        
        return template
    
    async def _record_publication(
        self,
        article_id: int,
        channel_id: int,
        result: Dict
    ):
        """Record publication event."""
        record = PublicationRecord(
            article_id=article_id,
            channel_id=channel_id,
            status="sent" if result.get("status") == "success" else "failed",
            published_url=result.get("url"),
            error_message=result.get("error"),
            platform_response=result,
        )
        
        self.db.add(record)
        await self.db.commit()
```

#### Task 5.3: Create Channel-Specific Publishers
**File:** `agent_publisher/services/channel_publishers/`

**Telegram Publisher:**
```python
class TelegramPublisher:
    """Publish to Telegram."""
    
    async def publish(
        self,
        formatted: Dict[str, Any],
        config: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Publish to Telegram.
        
        Config: {"bot_token": "...", "chat_id": "..."}
        """
        import aiohttp
        
        bot_token = config.get("bot_token")
        chat_id = config.get("chat_id")
        
        if not bot_token or not chat_id:
            raise ValueError("Missing bot_token or chat_id in config")
        
        # Format message for Telegram (Markdown)
        message = f"**{formatted['title']}**\n\n{formatted['body']}"
        
        # Send via Telegram Bot API
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                }
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Telegram API error: {resp.status}")
                
                data = await resp.json()
                return {
                    "status": "success",
                    "url": f"https://t.me/{chat_id}/{data['result']['message_id']}",
                    "message_id": str(data['result']['message_id'])
                }
```

**Slack Publisher:**
```python
class SlackPublisher:
    """Publish to Slack."""
    
    async def publish(
        self,
        formatted: Dict[str, Any],
        config: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Publish to Slack.
        
        Config: {"webhook_url": "...", "channel": "#news"}
        """
        import aiohttp
        
        webhook_url = config.get("webhook_url")
        
        if not webhook_url:
            raise ValueError("Missing webhook_url in config")
        
        # Format for Slack (JSON blocks)
        payload = {
            "text": formatted['title'],
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": formatted['title'][:150]
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": formatted['body'][:1000]
                    }
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"Slack webhook error: {resp.status}")
                
                return {
                    "status": "success",
                    "url": webhook_url,
                    "message_id": "slack-message"
                }
```

**Email Publisher:**
```python
class EmailPublisher:
    """Publish via email."""
    
    async def publish(
        self,
        formatted: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Publish via email.
        
        Config: {
            "recipients": ["email1@example.com"],
            "from_name": "Publisher",
            "smtp_server": "...",
            "smtp_port": 587
        }
        """
        from email.mime.text import MIMEText
        import smtplib
        
        recipients = config.get("recipients", [])
        from_name = config.get("from_name", "Agent Publisher")
        
        # Create email
        msg = MIMEText(formatted['body'], 'html')
        msg['Subject'] = formatted['title']
        msg['From'] = from_name
        msg['To'] = ', '.join(recipients)
        
        # Send via SMTP
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port", 587)
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.send_message(msg)
        
        return {
            "status": "success",
            "url": f"mailto:{recipients[0]}",
            "message_id": f"email-{len(recipients)}"
        }
```

#### Task 5.4: Create Publishing API Endpoints
**File:** `agent_publisher/api/routes/publications.py`

```python
router = APIRouter(prefix="/api/publications", tags=["publications"])

@router.post("/channels")
async def create_channel(
    request: CreateChannelRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """Create a new publication channel."""
    channel = PublicationChannel(**request.dict())
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel

@router.get("/channels")
async def list_channels(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """List publication channels for agent."""
    from sqlalchemy import select
    
    stmt = select(PublicationChannel).where(
        PublicationChannel.agent_id == agent_id,
        PublicationChannel.deleted_at.is_(None)
    )
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/publish/{article_id}")
async def publish_article(
    article_id: int,
    request: PublishRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """Publish article to channels."""
    service = MultiChannelPublisherService(db)
    
    result = await service.publish_article(
        article_id=article_id,
        agent_id=request.agent_id,
        channel_ids=request.channel_ids,
        dry_run=request.dry_run
    )
    
    return result

@router.get("/records/{article_id}")
async def get_publication_records(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """Get publication history for article."""
    from sqlalchemy import select
    
    stmt = select(PublicationRecord).where(
        PublicationRecord.article_id == article_id
    ).order_by(PublicationRecord.published_at.desc())
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/stats")
async def get_publication_stats(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """Get publishing statistics."""
    from sqlalchemy import select, func
    
    # By channel type
    stmt = select(
        PublicationRecord.status,
        func.count(PublicationRecord.id).label('count')
    ).where(
        PublicationRecord.channel.has(
            PublicationChannel.agent_id == agent_id
        )
    ).group_by(PublicationRecord.status)
    
    result = await db.execute(stmt)
    
    return {
        "total_publications": sum(r[1] for r in result),
        "by_status": {r[0]: r[1] for r in result},
        "total_views": await self._sum_metric(db, "views", agent_id),
        "total_clicks": await self._sum_metric(db, "clicks", agent_id),
    }
```

---

## Database Schema

### New Tables

```sql
CREATE TABLE publication_channels (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  agent_id BIGINT NOT NULL,
  
  channel_type VARCHAR(50),        -- "wechat", "telegram", "slack", etc.
  channel_name VARCHAR(255),
  
  channel_config JSON,             -- Encrypted credentials
  is_enabled BOOLEAN DEFAULT TRUE,
  
  template_id BIGINT,              -- Reference to PublicationTemplate
  auto_publish BOOLEAN DEFAULT FALSE,
  publish_schedule VARCHAR(255),   -- Cron expression
  
  description VARCHAR(500),
  tags JSON,
  metadata JSON,
  
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_published_at DATETIME NULL,
  deleted_at DATETIME NULL,
  
  INDEX idx_agent_id (agent_id),
  INDEX idx_channel_type (channel_type),
  INDEX idx_is_enabled (is_enabled),
  FOREIGN KEY (agent_id) REFERENCES agent(id)
);

CREATE TABLE publication_templates (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  agent_id BIGINT NOT NULL,
  
  name VARCHAR(255),
  channel_type VARCHAR(50),        -- Which channels this applies to
  
  title_template VARCHAR(500),
  body_template VARCHAR(5000),
  footer_template VARCHAR(1000),
  
  max_length INT,
  strip_images BOOLEAN DEFAULT FALSE,
  strip_html BOOLEAN DEFAULT FALSE,
  
  is_default BOOLEAN DEFAULT FALSE,
  
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  INDEX idx_agent_id_channel_type (agent_id, channel_type),
  FOREIGN KEY (agent_id) REFERENCES agent(id)
);

CREATE TABLE publication_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  article_id BIGINT NOT NULL,
  channel_id BIGINT NOT NULL,
  
  status VARCHAR(50),              -- "sent", "failed", "scheduled"
  published_url VARCHAR(2000),
  error_message VARCHAR(1000),
  
  views INT DEFAULT 0,
  clicks INT DEFAULT 0,
  shares INT DEFAULT 0,
  reactions INT DEFAULT 0,
  
  platform_response JSON,
  metadata JSON,
  
  published_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  INDEX idx_article_id (article_id),
  INDEX idx_channel_id (channel_id),
  INDEX idx_status (status),
  INDEX idx_published_at (published_at),
  
  FOREIGN KEY (article_id) REFERENCES article(id),
  FOREIGN KEY (channel_id) REFERENCES publication_channels(id)
);
```

---

## Configuration

### New Settings (config.py)

```python
# Phase 5: Multi-Channel Publishing
trendradar_multi_channel_enabled: bool = False  # Feature flag

# Channel-specific credentials
telegram_default_bot_token: str = ""
slack_default_webhook_url: str = ""
email_default_from: str = "noreply@agent-publisher.local"
webhook_default_timeout_seconds: int = 30

# Publishing settings
max_publish_retries: int = 3
publication_timeout_seconds: int = 60
auto_publish_enabled: bool = False

# Analytics
track_publication_analytics: bool = True
analytics_retention_days: int = 90
```

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Publish single article | <5s | Sequential channel publishing |
| Publish latency (p95) | <10s | Includes all channels |
| Delivery success rate | >98% | With retries |
| Template rendering | <100ms | Per template |
| Analytics query | <500ms | 1 month data |

---

## Monitoring & Metrics

### Key Metrics
- Publication success rate by channel
- Average delivery latency by channel
- Cross-channel engagement (views, clicks)
- Template performance
- Channel health

### Alerting Rules
- Delivery success rate < 95%
- Any channel latency > 10s
- Channel configuration errors

---

## Risk Mitigation

### Risk 1: Credential Exposure
**Mitigation:** Encrypt credentials at rest, use environment variables, audit logs

### Risk 2: Rate Limiting
**Mitigation:** Implement per-channel rate limiting, queue system, backoff

### Risk 3: Delivery Failures
**Mitigation:** Automatic retries, dead-letter queue, monitoring

---

## Success Criteria

- ✅ 7+ channels supported
- ✅ Publishing latency <5s per channel
- ✅ Success rate >98%
- ✅ Template system functional
- ✅ Analytics working
- ✅ Ready for Phase 6

---

## Appendix: Phase 5 Checklist

### Implementation
- [ ] Create PublicationChannel model
- [ ] Create PublicationTemplate model
- [ ] Create PublicationRecord model
- [ ] Create MultiChannelPublisherService
- [ ] Implement channel publishers (Telegram, Slack, Email, Webhook)
- [ ] Create API endpoints
- [ ] Add database migrations

### Testing
- [ ] Unit tests for formatting
- [ ] Integration tests for publishing
- [ ] End-to-end publishing tests
- [ ] Error recovery tests
- [ ] Performance tests

### Deployment
- [ ] Code review
- [ ] Staging deployment
- [ ] QA testing
- [ ] Beta rollout (25%)
- [ ] Full release (100%)

---

**Document Version:** 1.0  
**Created:** 2026-04-14  
**Status:** READY FOR IMPLEMENTATION
