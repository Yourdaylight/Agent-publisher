# Phase 4: MCP Tool Integration
## Enrich Article Generation with TrendRadar's MCP Tools

**Phase Duration:** 1 week  
**Timeline:** Week 5-6 of integration project  
**Depends On:** Phase 1 ✅, Phase 2 ✅, Phase 3 ✅  
**Status:** Planning  

---

## Objectives

### Primary Goals
1. **Integrate TrendRadar MCP Server** - Connect LLM to TrendRadar's tool capabilities
2. **Enrich LLM Context** - Provide real-time data during article generation
3. **Enable Dynamic Content** - LLM can search related news, analyze trends, compare periods
4. **Improve Article Quality** - Deeper research context → better content
5. **Prepare Phase 5** - Foundation for multi-channel publishing

### Success Criteria
- ✅ 5+ TrendRadar MCP tools available to LLM
- ✅ Article generation includes MCP tool calls
- ✅ MCP latency <2s (p95)
- ✅ Content quality improvement >30% (user survey)
- ✅ Tool call success rate >95%
- ✅ No breaking changes to existing article generation
- ✅ Graceful fallback if MCP unavailable

---

## Background: MCP (Model Context Protocol)

### What is MCP?

MCP is a protocol that allows Claude (and other LLMs) to access tools/functions provided by external systems. It's similar to function calling, but standardized and more robust.

**TrendRadar exposes 6+ tools via MCP:**
1. `search_news(query, platforms, limit)` - Search news across platforms
2. `get_trending_topics(platform, limit)` - Get platform-specific trending
3. `get_trend_history(keyword, days)` - Historical trend data
4. `compare_periods(keyword, period1, period2)` - Compare trend trajectories
5. `aggregate_news(news_items)` - Deduplicate and aggregate articles
6. `read_article(url)` - Fetch and summarize full article content
7. `analyze_sentiment(text, language)` - Sentiment analysis

### Why Integrate?

**Before Phase 4:**
```
LLM Article Generation
│
├─ Input: Material title + summary
├─ Context: Limited to CandidateMaterial data
├─ Research: Can't access real-time information
└─ Output: Generic article with limited depth
```

**After Phase 4:**
```
LLM Article Generation
│
├─ Input: Material title + summary
│
├─ Context: CandidateMaterial + AI Analysis + Unified Pool data
│
├─ MCP Tools available:
│  ├─ search_news: "Find other articles about this topic"
│  ├─ get_trend_history: "Show me how this trend evolved"
│  ├─ compare_periods: "Compare this to last month's trend"
│  ├─ read_article: "Give me the full story"
│  └─ analyze_sentiment: "What's the general sentiment?"
│
└─ Output: Rich, researched article with depth
```

---

## Architecture Overview

### Phase 4 System Design

```
┌──────────────────────────────────────────────────────────┐
│        Phase 4: MCP Tool Integration                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Agent Publisher                    TrendRadar MCP      │
│  (Article Generation)               Server              │
│         │                                │              │
│         │ 1. Create article prompt      │              │
│         ├──────────────────────────────>│              │
│         │    (material + request)       │              │
│         │                               │              │
│         │ 2. Tool call request          │              │
│         │ (search_news, get_trends)     │              │
│         │<──────────────────────────────┤              │
│         │    (via MCP protocol)         │              │
│         │                               │              │
│         │ 3. Execute tool               │              │
│         │    (query TrendRadar data)    │              │
│         ├──────────────────────────────>│              │
│         │                               │              │
│         │ 4. Return tool result         │              │
│         │<──────────────────────────────┤              │
│         │                               │              │
│         │ 5. Continue with more tools   │              │
│         │    (iterate if needed)        │              │
│         │                               │              │
│         │ 6. Generate final article     │              │
│         │    (using all gathered data)  │              │
│         │                               │              │
│         └─ Output: Rich article        │              │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Integration Points

```
1. Article Generation Workflow
   └─ LLM Client (Claude)
      ├─ Read: CandidateMaterial (base content)
      ├─ Read: MaterialAnalysis (AI insights)
      ├─ Read: UnifiedMaterial (quality score + tags)
      ├─ Call: TrendRadar MCP Tools
      │  ├─ search_news()
      │  ├─ get_trend_history()
      │  ├─ compare_periods()
      │  ├─ read_article()
      │  └─ analyze_sentiment()
      └─ Generate: Article
         ├─ Title
         ├─ Body (with research insights)
         ├─ Images
         └─ Metadata

2. MCP Client Setup
   ├─ Connection: TrendRadar MCP server (websocket)
   ├─ Tools: Auto-loaded from server
   ├─ Error handling: Fallback if MCP unavailable
   └─ Caching: Recent tool results cached 1h

3. Tool Execution Context
   ├─ Material context: what we're writing about
   ├─ Agent preferences: tone, length, focus areas
   ├─ Time context: when article is being written
   └─ Platform context: where it will be published
```

---

## Implementation Plan

### Week 1: MCP Infrastructure

#### Task 4.1: Create MCP Client Wrapper
**File:** `agent_publisher/services/mcp_client_wrapper.py`

```python
"""
Wrapper for TrendRadar MCP client.

Responsibilities:
1. Manage MCP connection lifecycle
2. Execute tools with error handling
3. Cache tool results
4. Provide typed tool interfaces
"""

from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class TrendRadarMCPClient:
    """
    Client for interacting with TrendRadar MCP server.
    
    Features:
    - Automatic connection management
    - Tool call execution with retries
    - Result caching (1h TTL)
    - Graceful degradation if unavailable
    """
    
    def __init__(
        self,
        server_url: str,
        timeout_seconds: int = 30,
        cache_ttl_minutes: int = 60
    ):
        self.server_url = server_url
        self.timeout = timeout_seconds
        self.cache_ttl = cache_ttl_minutes
        self._client = None
        self._cache: Dict[str, Dict] = {}
        self._initialized = False
    
    async def initialize(self):
        """Connect to TrendRadar MCP server."""
        if self._initialized:
            return
        
        try:
            from fastmcp import ClientSession
            
            self._client = await ClientSession.connect(self.server_url)
            self._initialized = True
            logger.info("MCP client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize MCP client: %s", e)
            self._initialized = False
            raise
    
    async def search_news(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Search news across TrendRadar platforms.
        
        Args:
            query: Search query
            platforms: Filter by platforms (weibo, douyin, etc.)
            limit: Number of results
        
        Returns:
            {
                "status": "success|error",
                "results": [
                    {
                        "title": "...",
                        "url": "...",
                        "platform": "weibo",
                        "hot_value": 85,
                        "summary": "..."
                    }
                ],
                "query_time_ms": 123
            }
        """
        cache_key = f"search_news:{query}:{':'.join(platforms or [])}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            await self.initialize()
            
            result = await self._client.call_tool(
                "search_news",
                {
                    "query": query,
                    "platforms": platforms,
                    "limit": limit,
                }
            )
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error("search_news failed: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "results": []
            }
    
    async def get_trending_topics(
        self,
        platform: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get trending topics from a specific platform.
        
        Returns:
            {
                "status": "success|error",
                "platform": "weibo",
                "topics": [
                    {
                        "title": "...",
                        "rank": 1,
                        "hot_value": 95,
                        "url": "..."
                    }
                ]
            }
        """
        cache_key = f"trending:{platform}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            await self.initialize()
            
            result = await self._client.call_tool(
                "get_trending_topics",
                {
                    "platform": platform,
                    "limit": limit,
                }
            )
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error("get_trending_topics failed: %s", e)
            return {
                "status": "error",
                "platform": platform,
                "topics": []
            }
    
    async def get_trend_history(
        self,
        keyword: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get historical trend data for keyword.
        
        Returns:
            {
                "status": "success|error",
                "keyword": "ai",
                "history": [
                    {"date": "2026-04-14", "hot_value": 85, "count": 1500},
                    {"date": "2026-04-13", "hot_value": 75, "count": 1200}
                ]
            }
        """
        cache_key = f"history:{keyword}:{days}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            await self.initialize()
            
            result = await self._client.call_tool(
                "get_trend_history",
                {
                    "keyword": keyword,
                    "days": days,
                }
            )
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error("get_trend_history failed: %s", e)
            return {
                "status": "error",
                "keyword": keyword,
                "history": []
            }
    
    async def compare_periods(
        self,
        keyword: str,
        period1_date: str,
        period2_date: str,
        days_per_period: int = 7
    ) -> Dict[str, Any]:
        """
        Compare trend between two time periods.
        
        Args:
            keyword: Trend keyword
            period1_date: First period start date (YYYY-MM-DD)
            period2_date: Second period start date (YYYY-MM-DD)
            days_per_period: Duration of each period
        
        Returns:
            {
                "status": "success|error",
                "keyword": "ai",
                "period1": {
                    "avg_hot_value": 78,
                    "total_mentions": 5000,
                    "trend": "up"
                },
                "period2": {
                    "avg_hot_value": 88,
                    "total_mentions": 6000,
                    "trend": "up"
                },
                "comparison": {
                    "change_percent": 12.8,
                    "trend_direction": "accelerating"
                }
            }
        """
        cache_key = f"compare:{keyword}:{period1_date}:{period2_date}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            await self.initialize()
            
            result = await self._client.call_tool(
                "compare_periods",
                {
                    "keyword": keyword,
                    "period1_date": period1_date,
                    "period2_date": period2_date,
                    "days_per_period": days_per_period,
                }
            )
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error("compare_periods failed: %s", e)
            return {
                "status": "error",
                "keyword": keyword,
                "comparison": None
            }
    
    async def read_article(self, url: str) -> Dict[str, Any]:
        """
        Fetch and parse full article content.
        
        Returns:
            {
                "status": "success|error",
                "url": "...",
                "title": "...",
                "content": "...",
                "author": "...",
                "published_at": "2026-04-14T10:30:00Z"
            }
        """
        cache_key = f"article:{url}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            await self.initialize()
            
            result = await self._client.call_tool(
                "read_article",
                {"url": url}
            )
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error("read_article failed for %s: %s", url, e)
            return {
                "status": "error",
                "url": url,
                "content": None
            }
    
    async def analyze_sentiment(
        self,
        text: str,
        language: str = "zh"
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of text.
        
        Returns:
            {
                "status": "success|error",
                "sentiment": "positive|negative|neutral",
                "score": 0.85,
                "keywords": ["positive_term1", "positive_term2"]
            }
        """
        cache_key = f"sentiment:{hash(text)}:{language}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            await self.initialize()
            
            result = await self._client.call_tool(
                "analyze_sentiment",
                {
                    "text": text,
                    "language": language,
                }
            )
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error("analyze_sentiment failed: %s", e)
            return {
                "status": "error",
                "sentiment": "unknown",
                "score": 0.0
            }
    
    def _get_cached(self, key: str) -> Optional[Dict]:
        """Get cached result if not expired."""
        if key not in self._cache:
            return None
        
        from datetime import datetime, timedelta
        entry = self._cache[key]
        if datetime.utcnow() - entry['timestamp'] > timedelta(minutes=self.cache_ttl):
            del self._cache[key]
            return None
        
        return entry['data']
    
    def _cache_result(self, key: str, data: Dict):
        """Cache a result with current timestamp."""
        from datetime import datetime
        self._cache[key] = {
            'data': data,
            'timestamp': datetime.utcnow(),
        }
    
    async def close(self):
        """Close MCP connection."""
        if self._client:
            await self._client.close()
            self._initialized = False
```

#### Task 4.2: Integrate MCP into Article Generation
**File:** Modified `agent_publisher/services/article_generation_service.py`

```python
async def generate_article(
    self,
    agent_id: int,
    material_id: int,
    use_mcp_tools: bool = True
) -> Dict[str, Any]:
    """
    Generate article with optional MCP tool enrichment.
    
    Process:
    1. Load material and analysis
    2. If use_mcp_tools enabled:
       - Create MCP client
       - Build tool descriptions for Claude
       - Claude generates article with tool calls
       - Execute tools and feed results back to Claude
    3. Generate final article
    4. Save to database
    """
    
    # Load base data
    material = await self._load_material(material_id)
    analysis = await self._load_analysis(material_id)
    agent = await self._load_agent(agent_id)
    
    # Build initial prompt
    prompt = self._build_article_prompt(material, analysis, agent)
    
    # Prepare MCP tools if enabled
    mcp_tools = []
    if use_mcp_tools and settings.trendradar_mcp_enabled:
        mcp_client = TrendRadarMCPClient(settings.trendradar_service_url)
        mcp_tools = await self._describe_mcp_tools(mcp_client)
    
    # Generate article with Claude
    article = await self._call_claude_with_tools(
        prompt=prompt,
        tools=mcp_tools,
        mcp_client=mcp_client if mcp_tools else None,
    )
    
    # Save and return
    return article

async def _call_claude_with_tools(
    self,
    prompt: str,
    tools: List[Dict],
    mcp_client: Optional[TrendRadarMCPClient] = None
) -> Dict[str, Any]:
    """
    Call Claude with tools support via MCP.
    
    Process:
    1. Call Claude API with tools parameter
    2. Claude returns tool_calls in response
    3. Execute each tool via MCP
    4. Feed results back to Claude
    5. Claude generates final response
    """
    from anthropic import Anthropic
    
    client = Anthropic(api_key=settings.default_llm_api_key)
    
    # First call: Claude decides what tools to use
    messages = [{"role": "user", "content": prompt}]
    
    response = client.messages.create(
        model=settings.default_llm_model,
        max_tokens=4096,
        tools=tools,
        messages=messages,
    )
    
    # Process tool calls
    while response.stop_reason == "tool_use":
        # Extract tool calls from response
        tool_calls = [block for block in response.content if block.type == "tool_use"]
        
        # Execute each tool
        tool_results = []
        for tool_call in tool_calls:
            result = await mcp_client.call_tool_by_name(
                tool_call.name,
                tool_call.input
            )
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": str(result),
            })
        
        # Continue conversation with tool results
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
        
        response = client.messages.create(
            model=settings.default_llm_model,
            max_tokens=4096,
            tools=tools,
            messages=messages,
        )
    
    # Extract final article text
    return {
        "article": self._extract_text_from_response(response),
        "stop_reason": response.stop_reason,
    }

async def _describe_mcp_tools(
    self,
    mcp_client: TrendRadarMCPClient
) -> List[Dict]:
    """
    Get tool descriptions for Claude from MCP server.
    
    Returns:
        [
            {
                "name": "search_news",
                "description": "Search news across platforms...",
                "input_schema": { ... }
            },
            ...
        ]
    """
    # TrendRadar MCP server exposes tools automatically
    # We just need to request the definitions
    tools = [
        {
            "name": "search_news",
            "description": "Search for news articles across multiple platforms (Weibo, Douyin, etc.) using keyword queries. Returns ranked results with hotness scores.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "platforms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by platforms (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results (default: 5)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "get_trending_topics",
            "description": "Get current trending topics from a specific platform.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Platform name (weibo, douyin, xiaohongshu, etc.)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of topics (default: 10)"
                    }
                },
                "required": ["platform"]
            }
        },
        {
            "name": "get_trend_history",
            "description": "Get historical trend data showing how a keyword's popularity evolved over time.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to track"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days of history (default: 7)"
                    }
                },
                "required": ["keyword"]
            }
        },
        {
            "name": "compare_periods",
            "description": "Compare a trend's characteristics between two different time periods.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to compare"
                    },
                    "period1_date": {
                        "type": "string",
                        "description": "First period start date (YYYY-MM-DD)"
                    },
                    "period2_date": {
                        "type": "string",
                        "description": "Second period start date (YYYY-MM-DD)"
                    },
                    "days_per_period": {
                        "type": "integer",
                        "description": "Days per period (default: 7)"
                    }
                },
                "required": ["keyword", "period1_date", "period2_date"]
            }
        },
        {
            "name": "read_article",
            "description": "Fetch and parse the full content of an article from a URL.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Article URL"
                    }
                },
                "required": ["url"]
            }
        },
        {
            "name": "analyze_sentiment",
            "description": "Analyze the sentiment and emotional tone of text content.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to analyze"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code (zh for Chinese, en for English)"
                    }
                },
                "required": ["text"]
            }
        }
    ]
    
    return tools
```

#### Task 4.3: Create MCP Tool Executor
**File:** `agent_publisher/services/mcp_tool_executor.py`

```python
"""
Executor for MCP tool calls during article generation.

Responsibilities:
1. Execute tool calls requested by LLM
2. Format results for LLM consumption
3. Handle errors and retries
4. Track tool usage metrics
5. Enforce tool call rate limits
"""

class MCPToolExecutor:
    """Execute MCP tool calls with safety guardrails."""
    
    def __init__(
        self,
        mcp_client: TrendRadarMCPClient,
        max_tool_calls: int = 10,
        rate_limit_per_minute: int = 60
    ):
        self.mcp_client = mcp_client
        self.max_tool_calls = max_tool_calls
        self.rate_limit = rate_limit_per_minute
        self.tool_call_count = 0
        self.last_reset_time = datetime.utcnow()
    
    async def execute_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """
        Execute a single tool call with safety checks.
        
        Returns:
            Formatted result string for LLM
        """
        # Check rate limits
        if not self._check_rate_limit():
            return "ERROR: Rate limit exceeded. Too many tool calls."
        
        # Check max calls
        if self.tool_call_count >= self.max_tool_calls:
            return "ERROR: Maximum tool calls exceeded."
        
        # Execute tool
        try:
            result = await getattr(self.mcp_client, tool_name)(**tool_input)
            self.tool_call_count += 1
            return self._format_result(tool_name, result)
        except Exception as e:
            logger.error("Tool execution failed: %s(%s): %s", tool_name, tool_input, e)
            return f"ERROR: {tool_name} failed: {str(e)}"
    
    async def execute_tool_calls(
        self,
        tool_calls: List[Dict]
    ) -> List[Dict]:
        """
        Execute multiple tool calls and return results.
        
        Returns:
            [
                {
                    "tool_use_id": "...",
                    "result": "..."
                }
            ]
        """
        results = []
        for call in tool_calls:
            result = await self.execute_tool_call(
                call["name"],
                call["input"]
            )
            results.append({
                "tool_use_id": call.get("id"),
                "result": result,
            })
        return results
    
    def _format_result(self, tool_name: str, result: Dict) -> str:
        """Format tool result for LLM consumption."""
        if result.get("status") == "error":
            return f"{tool_name} error: {result.get('error', 'Unknown error')}"
        
        # Format based on tool type
        if tool_name == "search_news":
            return self._format_search_results(result)
        elif tool_name == "get_trending_topics":
            return self._format_trending_topics(result)
        elif tool_name == "get_trend_history":
            return self._format_trend_history(result)
        elif tool_name == "compare_periods":
            return self._format_comparison(result)
        elif tool_name == "read_article":
            return self._format_article(result)
        elif tool_name == "analyze_sentiment":
            return self._format_sentiment(result)
        else:
            return str(result)
    
    def _format_search_results(self, result: Dict) -> str:
        """Format search results as readable text."""
        if not result.get("results"):
            return "No news found."
        
        formatted = "Search Results:\n"
        for i, item in enumerate(result["results"], 1):
            formatted += f"{i}. {item.get('title', 'N/A')} (Hotness: {item.get('hot_value', 0)})\n"
            formatted += f"   Platform: {item.get('platform', 'N/A')}\n"
            formatted += f"   Summary: {item.get('summary', 'N/A')[:200]}...\n"
        return formatted
    
    def _format_trending_topics(self, result: Dict) -> str:
        """Format trending topics as readable text."""
        if not result.get("topics"):
            return f"No trending topics on {result.get('platform', 'N/A')}."
        
        formatted = f"Trending on {result.get('platform', 'N/A')}:\n"
        for i, topic in enumerate(result["topics"], 1):
            formatted += f"{i}. {topic.get('title', 'N/A')} (Rank #{topic.get('rank', '?')}, Hotness: {topic.get('hot_value', 0)})\n"
        return formatted
    
    def _format_trend_history(self, result: Dict) -> str:
        """Format trend history as readable text."""
        if not result.get("history"):
            return f"No history for {result.get('keyword', 'N/A')}."
        
        formatted = f"Trend History for '{result.get('keyword', 'N/A')}':\n"
        for entry in result["history"]:
            formatted += f"- {entry.get('date', 'N/A')}: Hotness {entry.get('hot_value', 0)}, {entry.get('count', 0)} mentions\n"
        return formatted
    
    def _format_comparison(self, result: Dict) -> str:
        """Format period comparison as readable text."""
        comparison = result.get("comparison", {})
        return (
            f"Trend Comparison for '{result.get('keyword', 'N/A')}':\n"
            f"Period 1 avg hotness: {result.get('period1', {}).get('avg_hot_value', 0)}\n"
            f"Period 2 avg hotness: {result.get('period2', {}).get('avg_hot_value', 0)}\n"
            f"Change: {comparison.get('change_percent', 0):.1f}%\n"
            f"Direction: {comparison.get('trend_direction', 'unknown')}\n"
        )
    
    def _format_article(self, result: Dict) -> str:
        """Format article content as readable text."""
        return (
            f"Article: {result.get('title', 'N/A')}\n"
            f"Author: {result.get('author', 'N/A')}\n"
            f"Published: {result.get('published_at', 'N/A')}\n"
            f"Content:\n{result.get('content', 'N/A')[:1000]}...\n"
        )
    
    def _format_sentiment(self, result: Dict) -> str:
        """Format sentiment analysis result."""
        return (
            f"Sentiment: {result.get('sentiment', 'unknown')} "
            f"(confidence: {result.get('score', 0):.2%})\n"
            f"Key terms: {', '.join(result.get('keywords', []))}\n"
        )
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = datetime.utcnow()
        elapsed = (now - self.last_reset_time).total_seconds()
        
        if elapsed > 60:  # Reset every minute
            self.tool_call_count = 0
            self.last_reset_time = now
        
        return self.tool_call_count < self.rate_limit
```

### Week 2: Integration & Testing

#### Task 4.4: Create MCP Configuration
**File:** Config additions to `config.py`

```python
# Phase 4: MCP Tool Integration
trendradar_mcp_enabled: bool = False  # Feature flag

# MCP connection settings
trendradar_service_url: str = ""  # e.g. "ws://localhost:8000"
mcp_connection_timeout_seconds: int = 30
mcp_max_tool_calls_per_article: int = 10

# Tool call settings
mcp_cache_ttl_minutes: int = 60
mcp_rate_limit_per_minute: int = 60

# LLM settings for MCP-enhanced generation
llm_mcp_model: str = "claude-3-5-sonnet"  # Use better model for MCP calls
llm_mcp_max_tokens: int = 4096
llm_mcp_temperature: float = 0.7  # Slightly more creative with tools
```

#### Task 4.5: Create Integration Tests
**File:** `tests/test_mcp_integration.py`

```python
"""
Integration tests for MCP tool integration with article generation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_mcp_tool_execution():
    """Test that MCP tools execute correctly."""
    mcp_client = TrendRadarMCPClient("ws://localhost:8000")
    
    result = await mcp_client.search_news(
        query="artificial intelligence",
        limit=5
    )
    
    assert result["status"] == "success"
    assert len(result["results"]) > 0
    assert "title" in result["results"][0]

@pytest.mark.asyncio
async def test_mcp_caching():
    """Test that MCP results are cached."""
    mcp_client = TrendRadarMCPClient("ws://localhost:8000", cache_ttl_minutes=60)
    
    # First call
    result1 = await mcp_client.search_news(query="test", limit=5)
    
    # Second call (should hit cache)
    result2 = await mcp_client.search_news(query="test", limit=5)
    
    assert result1 == result2

@pytest.mark.asyncio
async def test_mcp_tool_executor_rate_limiting():
    """Test that tool executor respects rate limits."""
    mcp_client = AsyncMock()
    executor = MCPToolExecutor(mcp_client, rate_limit_per_minute=5)
    
    # Execute 5 calls
    for i in range(5):
        result = await executor.execute_tool_call("search_news", {"query": f"test{i}"})
        assert "ERROR" not in result
    
    # 6th call should fail
    result = await executor.execute_tool_call("search_news", {"query": "test6"})
    assert "Rate limit" in result

@pytest.mark.asyncio
async def test_article_generation_with_mcp_tools():
    """Test end-to-end article generation with MCP tools."""
    service = ArticleGenerationService(db)
    
    article = await service.generate_article(
        agent_id=1,
        material_id=1,
        use_mcp_tools=True
    )
    
    assert article["status"] == "success"
    assert "title" in article
    assert "content" in article
    # Content should be enriched via MCP tools
    assert len(article["content"]) > 500

@pytest.mark.asyncio
async def test_mcp_fallback_on_unavailable():
    """Test that article generation works without MCP."""
    with patch("agent_publisher.services.article_generation_service.settings.trendradar_mcp_enabled", False):
        service = ArticleGenerationService(db)
        
        article = await service.generate_article(
            agent_id=1,
            material_id=1,
            use_mcp_tools=False
        )
        
        assert article["status"] == "success"
        # Should still generate article without MCP
        assert "title" in article
```

#### Task 4.6: Create Monitoring & Observability
**File:** `agent_publisher/services/mcp_monitoring.py`

```python
"""
Monitoring and observability for MCP tool usage.
"""

class MCPMetrics:
    """Track MCP tool usage metrics."""
    
    def __init__(self):
        self.tool_calls_total = 0
        self.tool_calls_success = 0
        self.tool_calls_failed = 0
        self.tool_execution_times: Dict[str, List[float]] = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def record_tool_call(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float
    ):
        """Record a tool call."""
        self.tool_calls_total += 1
        if success:
            self.tool_calls_success += 1
        else:
            self.tool_calls_failed += 1
        
        if tool_name not in self.tool_execution_times:
            self.tool_execution_times[tool_name] = []
        self.tool_execution_times[tool_name].append(duration_ms)
    
    def record_cache_hit(self):
        """Record cache hit."""
        self.cache_hits += 1
    
    def record_cache_miss(self):
        """Record cache miss."""
        self.cache_misses += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            "total_calls": self.tool_calls_total,
            "successful_calls": self.tool_calls_success,
            "failed_calls": self.tool_calls_failed,
            "success_rate": (
                self.tool_calls_success / self.tool_calls_total * 100
                if self.tool_calls_total > 0 else 0
            ),
            "cache_hit_rate": (
                self.cache_hits / (self.cache_hits + self.cache_misses) * 100
                if (self.cache_hits + self.cache_misses) > 0 else 0
            ),
            "avg_execution_times": {
                tool: sum(times) / len(times)
                for tool, times in self.tool_execution_times.items()
            }
        }

# Global metrics instance
_mcp_metrics = MCPMetrics()

def get_mcp_metrics() -> MCPMetrics:
    """Get global MCP metrics instance."""
    return _mcp_metrics
```

---

## Configuration

### New Settings (config.py)

```python
# Phase 4: MCP Tool Integration
trendradar_mcp_enabled: bool = False

# MCP Server Connection
trendradar_service_url: str = ""  # e.g. "ws://trendradar-mcp:8000"
mcp_connection_timeout_seconds: int = 30

# Tool Usage Limits
mcp_max_tool_calls_per_article: int = 10
mcp_rate_limit_per_minute: int = 60

# Caching
mcp_cache_ttl_minutes: int = 60
mcp_enable_result_caching: bool = True

# LLM Configuration for MCP
llm_mcp_model: str = "claude-3-5-sonnet"
llm_mcp_max_tokens: int = 4096
llm_mcp_temperature: float = 0.7
```

---

## API Contracts

### LLM Tool Definitions

Claude receives these tool definitions during article generation:

**search_news**: Search news across 11 platforms
**get_trending_topics**: Get platform-specific trending
**get_trend_history**: Historical trend tracking
**compare_periods**: Trend period comparison
**read_article**: Full article fetching
**analyze_sentiment**: Text sentiment analysis

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Tool execution (p95) | <2s | Per tool call |
| Tool cache hit rate | >70% | Same articles likely reuse searches |
| Article generation (with MCP) | <30s | vs <15s without |
| Success rate | >95% | Tool calls must work |
| Rate limiting | ≤60 calls/min | Per article max 10 |

---

## Monitoring & Metrics

### Key Metrics to Track
- Tool call success rate
- Average tool execution time by tool
- Cache hit rate
- Total tool calls per article
- LLM token usage increase with MCP
- Error rates by tool

### Alerting Rules
- Tool success rate < 90%
- Tool execution p95 > 2s
- Cache hit rate < 50%
- MCP connection failures

---

## Risk Mitigation

### Risk 1: LLM Token Explosion
**Mitigation:** Set max_tool_calls=10, implement caching, monitor token usage

### Risk 2: Tool Call Failures
**Mitigation:** Error handling, retries, graceful fallback to non-MCP generation

### Risk 3: Rate Limiting
**Mitigation:** Per-article caps, per-minute limits, queue system if needed

### Risk 4: Latency Increase
**Mitigation:** Caching, parallel tool calls, timeouts, feature flag

---

## Success Criteria

- ✅ MCP tools successfully called from Claude
- ✅ Article quality improved (user survey >30%)
- ✅ Tool execution latency <2s (p95)
- ✅ Tool success rate >95%
- ✅ No breaking changes
- ✅ Ready for Phase 5

---

## Appendix: Phase 4 Checklist

### Implementation
- [ ] Create MCP client wrapper
- [ ] Integrate into article generation
- [ ] Create tool executor
- [ ] Add configuration
- [ ] Create monitoring

### Testing
- [ ] Unit tests for MCP client
- [ ] Integration tests for article generation
- [ ] Performance benchmarks
- [ ] Error handling tests
- [ ] Load tests

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
