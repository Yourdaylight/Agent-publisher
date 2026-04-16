# Phase 2: AI Analysis Integration
## Display TrendRadar's 5-Section AI Insights in Agent Publisher UI

**Phase Duration:** 2 weeks  
**Timeline:** Week 3-4 of integration project  
**Depends On:** Phase 1 (Data collection) ✅ Complete  
**Status:** Planning  

---

## Objectives

### Primary Goals
1. **Display TrendRadar AI Analysis** - Show 5-section insights in Agent Publisher UI
2. **Enrich Content Decisions** - Let users see trend analysis before article generation
3. **Enable Smart Filtering** - Material selection based on AI-powered signals
4. **Prepare Phase 3** - Store analysis results for unified material pool

### Success Criteria
- ✅ AI analysis fetched and displayed within 2 seconds
- ✅ 5 analysis sections visible in UI (trends, sentiment, controversy, signals, outlook)
- ✅ Material-specific fit scores calculated and displayed
- ✅ API response time <500ms (p95)
- ✅ 99%+ display reliability
- ✅ Zero breaking changes to existing workflows

---

## Architecture Overview

### System Flow (Phase 2)

```
TrendRadar Analysis Engine
        ↓
   AI Analysis Service
   (5-section breakdown)
        ↓
   API Endpoint: GET /api/hotspots/ai-insights
        ↓
   Agent Publisher UI
   (Display analysis + filtering)
        ↓
   User Decision Making
   (Which materials to use)
```

### 5-Section Analysis Breakdown

**1. Core Trends & Sentiment (40% of insights)**
- Dominant trend direction (up/down/stable)
- Sentiment distribution (positive/neutral/negative %)
- Trend momentum (accelerating/decelerating)
- Key influencers driving the trend

**2. Controversy & Debate (20% of insights)**
- Heated topics within the trend
- Conflicting viewpoints
- Debate intensity score
- Related controversy signals

**3. Weak Signals & Opportunities (20% of insights)**
- Emerging patterns (early-stage signals)
- Opportunity windows (timing for action)
- Cross-platform anomalies
- Early trend reversals

**4. Strategic Outlook & Recommendations (15% of insights)**
- Next 7-day projection
- Recommended content angles
- Optimal publication timing
- Risk assessment

**5. Material-Specific Fit Scores (5% of insights)**
- Per-material relevance (0-100)
- Content angle fit (0-100)
- Timing fit (0-100)
- Combined material score (0-100)

---

## Implementation Plan

### Week 1: Backend Infrastructure

#### Task 2.1: Create AI Analysis Data Model
**File:** `agent_publisher/models/material_analysis.py`

```python
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from agent_publisher.models.base import Base

class MaterialAnalysis(Base):
    """AI analysis results from TrendRadar for trending materials."""
    
    __tablename__ = "material_analyses"
    
    # Primary key
    id: int = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to CandidateMaterial
    material_id: int = Column(Integer, ForeignKey("candidate_material.id"), index=True)
    candidate_material: relationship = relationship("CandidateMaterial", back_populates="analyses")
    
    # Analysis metadata
    platform: str = Column(String(50), index=True)  # weibo, douyin, etc.
    analysis_date: datetime = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 5-section analysis scores (0-100)
    trend_direction: str = Column(String(20))  # "up", "down", "stable"
    trend_momentum: float = Column(Float)  # 0-100
    sentiment_positive: float = Column(Float)  # 0-100
    sentiment_neutral: float = Column(Float)  # 0-100
    sentiment_negative: float = Column(Float)  # 0-100
    
    controversy_score: float = Column(Float)  # 0-100
    debate_intensity: float = Column(Float)  # 0-100
    
    weak_signal_score: float = Column(Float)  # 0-100
    opportunity_score: float = Column(Float)  # 0-100
    
    outlook_7day_projection: str = Column(String(100))  # "increasing", "decreasing", "stable"
    outlook_risk_level: str = Column(String(20))  # "low", "medium", "high"
    
    # Material-specific fit scores
    material_relevance: float = Column(Float)  # 0-100
    content_angle_fit: float = Column(Float)  # 0-100
    timing_fit: float = Column(Float)  # 0-100
    combined_score: float = Column(Float)  # 0-100
    
    # Full analysis data (JSON)
    full_analysis: Dict[str, Any] = Column(JSON)
    
    # Timestamps
    created_at: datetime = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Soft delete
    deleted_at: Optional[datetime] = Column(DateTime, nullable=True)
```

**Database Migration:**
```bash
alembic revision --autogenerate -m "Add MaterialAnalysis table for Phase 2"
alembic upgrade head
```

#### Task 2.2: Create TrendRadar Analysis Service
**File:** `agent_publisher/services/trendradar_analysis_service.py`

```python
"""
TrendRadar AI Analysis Service

Responsibilities:
1. Fetch AI analysis from TrendRadar service
2. Transform to MaterialAnalysis format
3. Cache analysis results (24h)
4. Provide scoring APIs for UI/filtering
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class TrendRadarAnalysisService:
    """Service for AI analysis integration."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache: Dict[int, Dict] = {}  # material_id -> analysis
        self.cache_ttl = timedelta(hours=24)
    
    async def analyze_material(self, material_id: int) -> Optional[Dict[str, Any]]:
        """
        Get or fetch AI analysis for a material.
        
        Returns:
            {
                "trend_direction": "up|down|stable",
                "trend_momentum": 0-100,
                "sentiment": {"positive": 0-100, "neutral": 0-100, "negative": 0-100},
                "controversy_score": 0-100,
                "weak_signals": {"score": 0-100, "opportunities": ["text", ...]},
                "outlook": {
                    "7day_projection": "increasing|decreasing|stable",
                    "risk_level": "low|medium|high",
                    "recommendations": ["text", ...]
                },
                "material_fit": {
                    "relevance": 0-100,
                    "content_angle_fit": 0-100,
                    "timing_fit": 0-100,
                    "combined_score": 0-100
                }
            }
        """
        # Check cache first
        if material_id in self.cache:
            return self.cache[material_id]
        
        # Fetch from database
        from agent_publisher.models.material_analysis import MaterialAnalysis
        stmt = select(MaterialAnalysis).where(
            MaterialAnalysis.material_id == material_id,
            MaterialAnalysis.deleted_at.is_(None)
        ).order_by(MaterialAnalysis.created_at.desc())
        
        result = await self.db.execute(stmt)
        analysis = result.scalars().first()
        
        if analysis:
            return self._format_analysis(analysis)
        
        return None
    
    async def batch_analyze_materials(self, material_ids: List[int]) -> Dict[int, Dict]:
        """Fetch analysis for multiple materials efficiently."""
        from agent_publisher.models.material_analysis import MaterialAnalysis
        
        stmt = select(MaterialAnalysis).where(
            MaterialAnalysis.material_id.in_(material_ids),
            MaterialAnalysis.deleted_at.is_(None)
        )
        
        result = await self.db.execute(stmt)
        analyses = result.scalars().all()
        
        return {
            a.material_id: self._format_analysis(a) 
            for a in analyses
        }
    
    def _format_analysis(self, analysis: 'MaterialAnalysis') -> Dict[str, Any]:
        """Transform database record to API format."""
        return {
            "id": analysis.id,
            "material_id": analysis.material_id,
            "platform": analysis.platform,
            "analysis_date": analysis.analysis_date.isoformat(),
            "trend": {
                "direction": analysis.trend_direction,
                "momentum": analysis.trend_momentum,
            },
            "sentiment": {
                "positive": analysis.sentiment_positive,
                "neutral": analysis.sentiment_neutral,
                "negative": analysis.sentiment_negative,
            },
            "controversy": {
                "score": analysis.controversy_score,
                "debate_intensity": analysis.debate_intensity,
            },
            "weak_signals": {
                "score": analysis.weak_signal_score,
                "opportunity_score": analysis.opportunity_score,
            },
            "outlook": {
                "projection_7day": analysis.outlook_7day_projection,
                "risk_level": analysis.outlook_risk_level,
            },
            "material_fit": {
                "relevance": analysis.material_relevance,
                "content_angle_fit": analysis.content_angle_fit,
                "timing_fit": analysis.timing_fit,
                "combined_score": analysis.combined_score,
            },
            "full_analysis": analysis.full_analysis,
        }
```

#### Task 2.3: Create AI Analysis API Endpoints
**File:** `agent_publisher/api/routes/hotspots_analysis.py`

```python
"""
AI Analysis API endpoints for hotspots/trending materials.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from agent_publisher.api.dependencies import get_db, verify_access_key
from agent_publisher.services.trendradar_analysis_service import TrendRadarAnalysisService

router = APIRouter(prefix="/api/hotspots", tags=["analysis"])

@router.get("/ai-insights/{material_id}")
async def get_material_analysis(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """
    Get AI analysis for a single material.
    
    Returns 5-section analysis with material-specific fit scores.
    """
    service = TrendRadarAnalysisService(db)
    analysis = await service.analyze_material(material_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return analysis

@router.post("/ai-insights/batch")
async def get_batch_analysis(
    request: BatchAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """
    Get AI analysis for multiple materials.
    
    Useful for dashboard display of trending topics with analyses.
    """
    service = TrendRadarAnalysisService(db)
    analyses = await service.batch_analyze_materials(request.material_ids)
    
    return {
        "total": len(request.material_ids),
        "found": len(analyses),
        "analyses": analyses,
    }
```

### Week 2: Frontend & Integration

#### Task 2.4: Create Analysis Display Component
**File:** `web/src/components/HotspotAnalysis.vue`

```vue
<template>
  <div class="hotspot-analysis">
    <!-- Loading state -->
    <t-loading v-if="loading" size="small" />
    
    <!-- Analysis unavailable -->
    <t-alert v-if="error" type="error" :title="error" />
    
    <!-- Analysis panels -->
    <div v-if="analysis" class="analysis-panels">
      <!-- Trend & Sentiment Panel -->
      <t-card class="analysis-card" title="趋势与情感">
        <div class="metric-group">
          <div class="metric">
            <span class="label">趋势方向:</span>
            <t-tag :theme="getTrendTheme(analysis.trend.direction)">
              {{ analysis.trend.direction }}
            </t-tag>
          </div>
          <div class="metric">
            <span class="label">趋势动量:</span>
            <t-progress :percentage="analysis.trend.momentum" />
          </div>
        </div>
        
        <!-- Sentiment distribution -->
        <div class="sentiment-chart">
          <t-progress :percentage="analysis.sentiment.positive" label="正面" />
          <t-progress :percentage="analysis.sentiment.neutral" label="中立" />
          <t-progress :percentage="analysis.sentiment.negative" label="负面" />
        </div>
      </t-card>
      
      <!-- Controversy Panel -->
      <t-card class="analysis-card" title="争议与热议">
        <div class="metric">
          <span class="label">争议程度:</span>
          <t-progress :percentage="analysis.controversy.score" />
        </div>
        <div class="metric">
          <span class="label">热议强度:</span>
          <t-progress :percentage="analysis.controversy.debate_intensity" />
        </div>
      </t-card>
      
      <!-- Weak Signals Panel -->
      <t-card class="analysis-card" title="弱信号与机会">
        <div class="metric">
          <span class="label">弱信号得分:</span>
          <t-progress :percentage="analysis.weak_signals.score" />
        </div>
        <div class="metric">
          <span class="label">机会得分:</span>
          <t-progress :percentage="analysis.weak_signals.opportunity_score" />
        </div>
      </t-card>
      
      <!-- Outlook Panel -->
      <t-card class="analysis-card" title="前景展望">
        <div class="metric">
          <span class="label">7天趋势预测:</span>
          <t-tag :theme="getOutlookTheme(analysis.outlook.projection_7day)">
            {{ analysis.outlook.projection_7day }}
          </t-tag>
        </div>
        <div class="metric">
          <span class="label">风险等级:</span>
          <t-tag :theme="getRiskTheme(analysis.outlook.risk_level)">
            {{ analysis.outlook.risk_level }}
          </t-tag>
        </div>
      </t-card>
      
      <!-- Material Fit Panel -->
      <t-card class="analysis-card" title="内容适配度">
        <div class="fit-scores">
          <div class="fit-item">
            <span class="label">相关性:</span>
            <t-progress :percentage="analysis.material_fit.relevance" />
          </div>
          <div class="fit-item">
            <span class="label">角度适配:</span>
            <t-progress :percentage="analysis.material_fit.content_angle_fit" />
          </div>
          <div class="fit-item">
            <span class="label">时机适配:</span>
            <t-progress :percentage="analysis.material_fit.timing_fit" />
          </div>
          <div class="fit-item combined">
            <span class="label">综合得分:</span>
            <t-progress 
              :percentage="analysis.material_fit.combined_score"
              :color="getCombinedScoreColor(analysis.material_fit.combined_score)"
            />
          </div>
        </div>
      </t-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'

const props = defineProps<{
  materialId: number
}>()

const loading = ref(false)
const error = ref('')
const analysis = ref(null)

onMounted(async () => {
  loading.value = true
  try {
    const response = await api.get(`/api/hotspots/ai-insights/${props.materialId}`)
    analysis.value = response.data
  } catch (err) {
    error.value = '分析加载失败'
    console.error(err)
  } finally {
    loading.value = false
  }
})

const getTrendTheme = (direction: string) => {
  return {
    'up': 'success',
    'down': 'warning',
    'stable': 'default',
  }[direction] || 'default'
}

const getOutlookTheme = (projection: string) => {
  return {
    'increasing': 'success',
    'decreasing': 'warning',
    'stable': 'default',
  }[projection] || 'default'
}

const getRiskTheme = (level: string) => {
  return {
    'low': 'success',
    'medium': 'warning',
    'high': 'danger',
  }[level] || 'default'
}

const getCombinedScoreColor = (score: number) => {
  if (score >= 80) return '#0ec995'
  if (score >= 60) return '#fac858'
  return '#ff7f50'
}
</script>

<style scoped lang="scss">
.hotspot-analysis {
  margin-top: 16px;
  
  .analysis-panels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
  }
  
  .analysis-card {
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }
  
  .metric-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .metric {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .label {
      font-weight: 500;
      min-width: 80px;
    }
  }
  
  .sentiment-chart {
    margin-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .fit-scores {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .fit-item {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .label {
      font-weight: 500;
      min-width: 80px;
    }
    
    &.combined {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid #e5e7eb;
      
      .label {
        font-weight: 700;
        color: #0969da;
      }
    }
  }
}
</style>
```

#### Task 2.5: Integrate Analysis into Material List
**File:** Modified `web/src/pages/Hotspots.vue`

```vue
<!-- In material list item template -->
<t-card v-for="material in materials" :key="material.id" class="material-card">
  <t-row class="card-header">
    <t-col :span="12">
      <h3>{{ material.title }}</h3>
    </t-col>
    <t-col :span="12" align="right">
      <t-tag v-if="material.platform">{{ material.platform }}</t-tag>
    </t-col>
  </t-row>
  
  <!-- AI Analysis Summary (NEW) -->
  <t-collapse v-if="materialsWithAnalysis.includes(material.id)">
    <t-collapse-panel 
      header="🤖 AI分析" 
      value="analysis"
    >
      <HotspotAnalysis :material-id="material.id" />
    </t-collapse-panel>
  </t-collapse>
  
  <!-- Existing content -->
  <p class="material-summary">{{ material.summary }}</p>
  <t-row :gutter="8" class="material-actions">
    <t-col>
      <t-button theme="primary" @click="selectMaterial(material)">
        选用内容
      </t-button>
    </t-col>
    <t-col>
      <t-button theme="default" @click="viewAnalysis(material)">
        查看分析
      </t-button>
    </t-col>
  </t-row>
</t-card>
```

#### Task 2.6: Create Analysis Fetch & Cache Layer
**File:** `agent_publisher/services/trendradar_analysis_cache.py`

```python
"""
Analysis caching and background refresh service.

Responsibilities:
1. Cache AI analysis in memory (1h TTL)
2. Periodically refresh analyses in background
3. Provide fast API response times
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

class AnalysisCache:
    """In-memory cache for AI analysis with TTL."""
    
    def __init__(self, ttl_minutes: int = 60):
        self.cache: Dict[int, Dict] = {}  # material_id -> {data, timestamp}
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def get(self, material_id: int) -> Optional[Dict]:
        """Get cached analysis if not expired."""
        if material_id not in self.cache:
            return None
        
        entry = self.cache[material_id]
        if datetime.utcnow() - entry['timestamp'] > self.ttl:
            del self.cache[material_id]
            return None
        
        return entry['data']
    
    def set(self, material_id: int, data: Dict):
        """Cache analysis with current timestamp."""
        self.cache[material_id] = {
            'data': data,
            'timestamp': datetime.utcnow(),
        }
    
    def clear_expired(self):
        """Remove expired entries."""
        now = datetime.utcnow()
        expired = [
            mid for mid, entry in self.cache.items()
            if now - entry['timestamp'] > self.ttl
        ]
        for mid in expired:
            del self.cache[mid]

# Global cache instance
_analysis_cache = AnalysisCache(ttl_minutes=60)

async def get_analysis_with_cache(
    material_id: int, 
    db: AsyncSession,
    service: 'TrendRadarAnalysisService'
) -> Optional[Dict]:
    """Get analysis from cache or database."""
    cached = _analysis_cache.get(material_id)
    if cached:
        logger.debug(f"Analysis cache hit for material {material_id}")
        return cached
    
    analysis = await service.analyze_material(material_id)
    if analysis:
        _analysis_cache.set(material_id, analysis)
    
    return analysis
```

### Testing Plan (Week 2)

#### Unit Tests
- Analysis data model validation
- Score calculation correctness
- Cache TTL behavior
- API endpoint response format

#### Integration Tests
- End-to-end material analysis flow
- Cache invalidation on updates
- Batch analysis performance (<500ms for 50 materials)
- Error handling and fallback behavior

#### UI Tests
- Component rendering with sample data
- All 5 analysis panels visible
- Material fit score display accuracy
- Responsive design on mobile

---

## Database Schema Changes

### New Table: material_analyses

```sql
CREATE TABLE material_analyses (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  material_id BIGINT NOT NULL,
  platform VARCHAR(50) NOT NULL,
  analysis_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  -- Trend & Sentiment
  trend_direction VARCHAR(20),
  trend_momentum FLOAT,
  sentiment_positive FLOAT,
  sentiment_neutral FLOAT,
  sentiment_negative FLOAT,
  
  -- Controversy & Debate
  controversy_score FLOAT,
  debate_intensity FLOAT,
  
  -- Weak Signals & Opportunities
  weak_signal_score FLOAT,
  opportunity_score FLOAT,
  
  -- Outlook & Recommendations
  outlook_7day_projection VARCHAR(100),
  outlook_risk_level VARCHAR(20),
  
  -- Material-specific Fit
  material_relevance FLOAT,
  content_angle_fit FLOAT,
  timing_fit FLOAT,
  combined_score FLOAT,
  
  -- Full analysis JSON
  full_analysis JSON,
  
  -- Audit
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at DATETIME NULL,
  
  INDEX idx_material_id (material_id),
  INDEX idx_platform (platform),
  INDEX idx_analysis_date (analysis_date),
  FOREIGN KEY (material_id) REFERENCES candidate_material(id)
);
```

### New Indexes

```sql
-- Fast lookups by analysis date (for sorting)
CREATE INDEX idx_material_analysis_date ON material_analyses(material_id, created_at DESC);

-- Fast lookups by quality (for filtering by score)
CREATE INDEX idx_material_fit_score ON material_analyses(combined_score DESC);
```

---

## API Contract

### Endpoint: GET /api/hotspots/ai-insights/{material_id}

**Request:**
```
GET /api/hotspots/ai-insights/123
Authorization: Bearer <access_key>
```

**Response (200 OK):**
```json
{
  "id": 456,
  "material_id": 123,
  "platform": "weibo",
  "analysis_date": "2026-04-14T10:30:00Z",
  "trend": {
    "direction": "up",
    "momentum": 87
  },
  "sentiment": {
    "positive": 65,
    "neutral": 25,
    "negative": 10
  },
  "controversy": {
    "score": 42,
    "debate_intensity": 38
  },
  "weak_signals": {
    "score": 72,
    "opportunity_score": 68
  },
  "outlook": {
    "projection_7day": "increasing",
    "risk_level": "low"
  },
  "material_fit": {
    "relevance": 88,
    "content_angle_fit": 75,
    "timing_fit": 82,
    "combined_score": 81
  },
  "full_analysis": {
    "key_influencers": ["user1", "user2"],
    "related_tags": ["tag1", "tag2"],
    "recommendations": ["angle1", "angle2"]
  }
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Analysis not found"
}
```

### Endpoint: POST /api/hotspots/ai-insights/batch

**Request:**
```json
{
  "material_ids": [123, 124, 125]
}
```

**Response (200 OK):**
```json
{
  "total": 3,
  "found": 3,
  "analyses": {
    "123": { /* analysis object */ },
    "124": { /* analysis object */ },
    "125": { /* analysis object */ }
  }
}
```

---

## Configuration

### New Settings (config.py)

```python
# Phase 2: AI Analysis Integration
trendradar_ai_analysis_enabled: bool = False  # Feature flag

# Analysis caching
analysis_cache_ttl_minutes: int = 60
analysis_batch_size_max: int = 100

# Analysis refresh interval
analysis_refresh_interval_minutes: int = 360  # 6 hours

# Score thresholds for filtering
min_fit_score_for_recommendation: float = 0.6  # 60%
min_relevance_for_display: float = 0.4  # 40%
```

---

## Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Single analysis fetch | <100ms | Cache hit common case |
| Batch analysis (50 items) | <500ms | Acceptable for UI refresh |
| Cache hit rate | >80% | Reduces database load |
| Memory per analysis | <10KB | ~1GB for 100k materials |
| API response p95 | <200ms | Meets UI expectations |

---

## Migration Path

### 1. Feature Flag Disabled (Week 1)
- Code deployed with feature flag OFF
- No analysis displayed in UI
- Zero impact on existing workflows

### 2. Internal Testing (Early Week 2)
- Enable for test agents only
- Verify analysis quality and performance
- Iterate on UI/UX

### 3. Beta Rollout (Mid Week 2)
- Enable for 25% of users
- Monitor performance metrics
- Collect feedback

### 4. Full Release (End Week 2)
- Enable for all users
- Analysis visible on all materials
- Documentation available

---

## Monitoring & Metrics

### Key Metrics to Track
- Analysis API latency (p50, p95, p99)
- Cache hit rate
- Analysis accuracy (via user feedback ratings)
- UI component load time
- Database query performance

### Logging Points
```python
# In TrendRadarAnalysisService
logger.info("Analysis fetched for material %d (cache_hit=%s)", material_id, hit)
logger.debug("Analysis batch size: %d, time: %.2fs", len(ids), duration)
logger.warning("Analysis not found for material %d", material_id)
logger.error("Analysis fetch failed: %s", error, exc_info=True)
```

### Alerting Rules
- Analysis API p95 latency > 500ms
- Cache hit rate < 70%
- Database query time > 1s
- Error rate > 1%

---

## Risk Mitigation

### Risk 1: Analysis Quality Issues
**Mitigation:** User feedback ratings on analyses, manual review before display

### Risk 2: Performance Degradation
**Mitigation:** Aggressive caching, batch queries, index optimization

### Risk 3: Data Consistency
**Mitigation:** Unique constraints on (material_id, analysis_date), TTL-based freshness

### Risk 4: User Confusion
**Mitigation:** Clear UI labels, tooltips explaining each section, help documentation

---

## Success Criteria

- ✅ All 5 analysis sections displayed correctly
- ✅ API response time consistently <500ms
- ✅ Cache hit rate >80%
- ✅ Zero breaking changes
- ✅ User satisfaction >4/5 (feedback survey)
- ✅ Performance benchmarks met
- ✅ All unit tests passing
- ✅ Integration tests passing
- ✅ Ready for Phase 3

---

## Next Steps

### Immediate (End of Week 2)
1. ✅ Code review Phase 2 implementation
2. ✅ Staging deployment
3. ✅ QA testing
4. ✅ Beta rollout to 25% users

### Week 3
1. ⏭️ Monitor metrics and user feedback
2. ⏭️ Fix any issues discovered
3. ⏭️ Full release to 100% users
4. ⏭️ Begin Phase 3 planning

---

## Appendix: Phase 2 Checklist

### Planning ✅
- [x] Architecture design
- [x] Data model specification
- [x] API contract definition
- [x] UI/UX mockups
- [x] Testing strategy

### Implementation
- [ ] Create MaterialAnalysis model
- [ ] Create TrendRadarAnalysisService
- [ ] Create API endpoints
- [ ] Create Vue component
- [ ] Integrate into Hotspots page
- [ ] Create cache layer
- [ ] Add database migrations

### Testing
- [ ] Unit tests for models
- [ ] Unit tests for service
- [ ] Integration tests for flow
- [ ] UI component tests
- [ ] Performance benchmarks
- [ ] Load testing

### Deployment
- [ ] Code review
- [ ] Staging deployment
- [ ] QA testing
- [ ] Beta rollout (25%)
- [ ] Monitoring setup
- [ ] Full release (100%)

---

**Document Version:** 1.0  
**Created:** 2026-04-14  
**Status:** READY FOR IMPLEMENTATION
