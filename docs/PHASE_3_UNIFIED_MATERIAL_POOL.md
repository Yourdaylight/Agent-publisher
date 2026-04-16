# Phase 3: Unified Material Pool
## Consolidate Trending, RSS, and Manual Sources into Single Container

**Phase Duration:** 1 week  
**Timeline:** Week 4-5 of integration project  
**Depends On:** Phase 1 ✅, Phase 2 ✅  
**Status:** Planning  

---

## Objectives

### Primary Goals
1. **Unify Material Sources** - Single container for trending (TrendRadar), RSS, and manual materials
2. **Consistent Scoring** - Normalized quality scoring (0-1) across all sources
3. **Smart Deduplication** - Cross-source duplicate detection and merging
4. **Simplified UI** - Single material selection experience regardless of source
5. **Bridge to Phase 4** - Prepared data structure for MCP enrichment

### Success Criteria
- ✅ All materials accessible via unified pool API
- ✅ Quality scores normalized and comparable (0-1 scale)
- ✅ Cross-source deduplication rate >90%
- ✅ API response time <300ms (p95)
- ✅ Migration of existing materials transparent to users
- ✅ Zero breaking changes to article generation flow
- ✅ Backward compatibility maintained throughout

---

## Problem Statement

### Current Architecture Issues

**Before Phase 3:**
```
Agent Publisher Material Sources
│
├─ TrendRadar Collection (Phase 1)
│  └─ CandidateMaterial (source_type="trending")
│     ├─ Quality score: inconsistent
│     ├─ Metadata: platform-specific format
│     └─ Duplicates: not deduplicated across sources
│
├─ RSS Feeds (existing)
│  └─ CandidateMaterial (source_type="rss")
│     ├─ Quality score: inconsistent
│     ├─ Metadata: minimal
│     └─ No cross-platform dedup
│
└─ Manual Addition (existing)
   └─ CandidateMaterial (source_type="manual")
      ├─ Quality score: user-provided
      ├─ Metadata: user-provided
      └─ Potential duplicates with trending/RSS
```

**Problems:**
1. **Inconsistent Quality Scores** - Different sources use different scoring ranges
2. **Metadata Fragmentation** - TrendRadar metadata != RSS metadata
3. **Poor Deduplication** - Same story from Weibo AND RSS stored separately
4. **Complex Filtering** - Must query across 3 source_types
5. **Mixed Experiences** - Users see same content multiple times
6. **Scaling Issues** - As sources grow, duplicate problem compounds

### After Phase 3: Unified Pool

```
Agent Publisher - Unified Material Pool
│
├─ UnifiedMaterial Container
│  ├─ source_type: "trending" | "rss" | "manual"
│  ├─ quality_score: 0-1 (normalized)
│  ├─ tags: ["auto-extracted", "source-type", ...]
│  ├─ metadata: {platform, keywords, relevance, ...}
│  ├─ duplicates: [list of merged material IDs]
│  ├─ is_deduplicated: boolean
│  ├─ unified_source_id: unique identifier across all sources
│  └─ analyses: [related AI analyses from Phase 2]
│
└─ Benefits:
   ✅ Single query for all materials
   ✅ Consistent quality scoring
   ✅ Cross-source deduplication
   ✅ Unified filtering/sorting
   ✅ Better user experience
   ✅ Simpler article generation
```

---

## Architecture Overview

### Phase 3 System Design

```
┌─────────────────────────────────────────────────────┐
│          Phase 3: Unified Material Pool             │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Phase 1 Data                Phase 2 Analyses      │
│  (TrendRadar, RSS)           (5-section insights)  │
│        │                            │              │
│        └──────────┬─────────────────┘              │
│                   │                                │
│        ┌──────────▼────────────┐                  │
│        │ Deduplication Engine  │                  │
│        │ - URL matching        │                  │
│        │ - Title similarity    │                  │
│        │ - Source merging      │                  │
│        │ - Conflict resolution │                  │
│        └──────────┬────────────┘                  │
│                   │                                │
│        ┌──────────▼──────────────┐                │
│        │ Quality Normalization   │                │
│        │ - Trending: hot_value   │                │
│        │ - RSS: user_score       │                │
│        │ - Manual: provided      │                │
│        │ - AI: fit_scores        │                │
│        │ → Unified [0-1] scale   │                │
│        └──────────┬──────────────┘                │
│                   │                                │
│        ┌──────────▼─────────────────┐             │
│        │ UnifiedMaterial Container  │             │
│        │ - agent_id                 │             │
│        │ - unified_source_id (NEW)  │             │
│        │ - source_type              │             │
│        │ - quality_score_normalized │             │
│        │ - tags / metadata          │             │
│        │ - is_deduplicated          │             │
│        │ - duplicates: []           │             │
│        └──────────┬─────────────────┘             │
│                   │                                │
│        ┌──────────▼──────────────────┐            │
│        │   Unified Pool API          │            │
│        │ - GET /api/materials        │            │
│        │ - GET /api/materials/:id    │            │
│        │ - POST /api/materials/batch │            │
│        │ - GET /api/materials/stats  │            │
│        └──────────┬──────────────────┘            │
│                   │                                │
│        ┌──────────▼──────────────┐                │
│        │   Agent Publisher UI    │                │
│        │ - Single material view  │                │
│        │ - Unified filtering     │                │
│        │ - No duplicate listings │                │
│        └───────────────────────┘                │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Data Model: UnifiedMaterial

```python
class UnifiedMaterial(Base):
    """Unified container for all material sources."""
    
    __tablename__ = "unified_materials"
    
    # Primary identification
    id: int = Column(Integer, primary_key=True)
    agent_id: int = Column(Integer, ForeignKey("agent.id"), index=True)
    
    # Unified identifier across all sources
    unified_source_id: str = Column(String(255), unique=True, index=True)
    # Format: "{source_type}:{platform}:{hash}" 
    # E.g.: "trending:weibo:abc123" or "rss:techcrunch:def456"
    
    # Content
    title: str = Column(String(500))
    summary: str = Column(String(2000), nullable=True)
    original_url: str = Column(String(2000), unique=True)
    
    # Source information
    source_type: str = Column(String(50), index=True)  # "trending", "rss", "manual"
    source_platform: str = Column(String(100), nullable=True)  # "weibo", "techcrunch", etc.
    source_identity: str = Column(String(255), nullable=True)
    
    # Quality scoring (normalized 0-1)
    quality_score_normalized: float = Column(Float, index=True, default=0.5)
    # Calculated from:
    # - Original source score (depends on type)
    # - AI fit score (from Phase 2, if available)
    # - Age and recency
    # - Engagement metrics
    
    # Deduplication metadata
    is_deduplicated: bool = Column(Boolean, default=False, index=True)
    primary_material_id: Optional[int] = Column(Integer, nullable=True)  # If this is a duplicate
    duplicate_material_ids: List[int] = Column(JSON)  # Materials merged into this one
    deduplication_score: float = Column(Float, default=0.0)  # 0-1: confidence of merge
    
    # Tags and metadata
    tags: List[str] = Column(JSON, default=[])
    # Auto-generated tags:
    # - Source: "trending", "rss", "manual"
    # - Platform: "weibo", "douyin", etc.
    # - Quality: "high", "medium", "low"
    # - Age: "trending", "recent", "archived"
    
    metadata: Dict[str, Any] = Column(JSON)
    # Stores source-specific data:
    # {
    #   "platform": "weibo",
    #   "hot_value": 85,
    #   "rank": 3,
    #   "ai_fit_score": 0.81,
    #   "sentiment": "positive",
    #   "engagement_count": 15000,
    #   "rss_feed_source": "techcrunch"
    # }
    
    # AI Analysis relationship (from Phase 2)
    analyses: Relationship = relationship("MaterialAnalysis")
    
    # Audit trail
    created_at: datetime = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    used_in_articles: int = Column(Integer, default=0)  # How many articles used this
    usage_history: List[Dict] = Column(JSON, default=[])  # {article_id, timestamp}
    
    # Soft delete
    deleted_at: Optional[datetime] = Column(DateTime, nullable=True)
```

---

## Implementation Plan

### Week 1: Core Infrastructure

#### Task 3.1: Create UnifiedMaterial Model
**File:** `agent_publisher/models/unified_material.py`

- Define UnifiedMaterial SQLAlchemy ORM model
- Add relationships to CandidateMaterial (for backward compat)
- Add relationships to MaterialAnalysis (from Phase 2)
- Create database migration

**Key fields:**
- `unified_source_id` - unique identifier across all sources
- `quality_score_normalized` - 0-1 scale
- `is_deduplicated` - tracking merge status
- `duplicate_material_ids` - list of merged IDs
- `deduplication_score` - confidence 0-1

#### Task 3.2: Create Deduplication Engine
**File:** `agent_publisher/services/material_deduplication_service.py`

```python
class MaterialDeduplicationService:
    """
    Cross-source duplicate detection and merging.
    
    Strategy:
    1. Exact URL matching (highest confidence)
    2. Title similarity (80%+ Levenshtein distance)
    3. Combined scoring with source context
    """
    
    async def deduplicate_materials(
        self, 
        materials: List[CandidateMaterial],
        agent_id: int,
        min_similarity: float = 0.8
    ) -> List[UnifiedMaterial]:
        """
        Detect and merge duplicates across sources.
        
        Returns list of primary materials with duplicates merged.
        """
        pass
    
    async def find_duplicates(
        self, 
        material: CandidateMaterial,
        existing_materials: List[CandidateMaterial],
        min_similarity: float = 0.8
    ) -> List[CandidateMaterial]:
        """Find potential duplicates for a single material."""
        pass
    
    async def merge_duplicates(
        self,
        primary: CandidateMaterial,
        duplicates: List[CandidateMaterial]
    ) -> UnifiedMaterial:
        """Merge duplicate materials into primary."""
        pass
```

**Deduplication Algorithm:**
```
For each material M in collection:
  1. Check URL exact match against all existing URLs
     - If found: MERGE with high confidence (0.95)
  
  2. Extract title keywords (remove stop words)
  
  3. For each existing material E:
     - Calculate Levenshtein distance(M.title, E.title)
     - If distance > min_similarity (0.8):
       - Check source combination (trending + rss more likely dup)
       - Calculate combined confidence score
       - If confidence > threshold: MERGE
  
  4. If no duplicates found: CREATE new UnifiedMaterial
```

#### Task 3.3: Create Quality Score Normalization
**File:** `agent_publisher/services/material_quality_normalizer.py`

```python
class MaterialQualityNormalizer:
    """
    Normalize quality scores from different sources to [0, 1].
    
    Scoring formulas by source:
    - TrendRadar trending: (hot_value/100) * 0.6 + (ai_fit/100) * 0.4
    - RSS: user_score (already 0-1)
    - Manual: provided_score
    - Combined: weighted average considering source reliability
    """
    
    async def normalize_score(
        self,
        material: CandidateMaterial,
        analysis: Optional[MaterialAnalysis] = None
    ) -> float:
        """
        Calculate normalized quality score for a material.
        
        Returns float in [0, 1] range.
        """
        source_type = material.source_type
        
        if source_type == "trending":
            return self._normalize_trending_score(material, analysis)
        elif source_type == "rss":
            return self._normalize_rss_score(material)
        elif source_type == "manual":
            return self._normalize_manual_score(material)
        else:
            return 0.5  # Default
    
    def _normalize_trending_score(
        self,
        material: CandidateMaterial,
        analysis: Optional[MaterialAnalysis] = None
    ) -> float:
        """
        Trending score = (hot_value * 0.6) + (ai_fit * 0.4)
        
        Components:
        - hot_value: from TrendRadar (0-100) → normalize to 0-1
        - ai_fit: from MaterialAnalysis (0-100) → normalize to 0-1
        """
        hot_value = material.metadata.get("hot_value", 50)
        hot_score = min(hot_value / 100.0, 1.0)
        
        ai_score = 0.5  # Default if no analysis
        if analysis:
            ai_score = min(analysis.combined_score / 100.0, 1.0)
        
        return (hot_score * 0.6) + (ai_score * 0.4)
    
    def _normalize_rss_score(self, material: CandidateMaterial) -> float:
        """
        RSS score already in 0-1 range, just validate.
        """
        score = material.metadata.get("quality_score", 0.5)
        return min(max(score, 0.0), 1.0)
    
    def _normalize_manual_score(self, material: CandidateMaterial) -> float:
        """
        Manual score provided by user.
        """
        score = material.metadata.get("quality_score", 0.5)
        return min(max(score, 0.0), 1.0)
```

**Scoring Formula Examples:**

| Material | Source | hot_value | ai_fit | age_factor | formula | result |
|----------|--------|-----------|--------|-----------|---------|---------|
| Weibo trending | trending | 85 | 0.81 | 0.95 | (0.85 × 0.6) + (0.81 × 0.4) × 0.95 | 0.75 |
| TechCrunch article | rss | N/A | N/A | 0.8 | 0.75 × 0.8 | 0.60 |
| Manual selection | manual | N/A | N/A | 1.0 | 0.9 × 1.0 | 0.90 |

#### Task 3.4: Create Unified Material Pool Service
**File:** `agent_publisher/services/unified_material_pool_service.py`

```python
class UnifiedMaterialPoolService:
    """
    Main service for managing unified material pool.
    
    Responsibilities:
    1. Convert CandidateMaterial → UnifiedMaterial
    2. Apply deduplication
    3. Calculate normalized quality scores
    4. Maintain backward compatibility
    5. Provide unified query APIs
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dedup_service = MaterialDeduplicationService(db)
        self.normalizer = MaterialQualityNormalizer()
    
    async def migrate_to_unified_pool(self, agent_id: int) -> Dict[str, int]:
        """
        One-time migration: convert all CandidateMaterial to UnifiedMaterial.
        
        Returns: {
            "total_materials": X,
            "duplicates_found": Y,
            "merged_materials": Z,
            "unified_created": W
        }
        """
        pass
    
    async def add_material_to_pool(
        self,
        agent_id: int,
        candidate_material: CandidateMaterial,
        analysis: Optional[MaterialAnalysis] = None
    ) -> UnifiedMaterial:
        """
        Add a new material to unified pool.
        
        Handles:
        1. Check for duplicates
        2. Merge if found
        3. Calculate quality score
        4. Create UnifiedMaterial
        """
        pass
    
    async def get_pool_materials(
        self,
        agent_id: int,
        source_types: Optional[List[str]] = None,
        min_quality: float = 0.0,
        limit: int = 100,
        offset: int = 0
    ) -> List[UnifiedMaterial]:
        """Get materials from unified pool with filtering."""
        pass
    
    async def get_pool_stats(self, agent_id: int) -> Dict[str, Any]:
        """
        Get statistics about pool.
        
        Returns: {
            "total_materials": X,
            "by_source_type": {"trending": X, "rss": Y, "manual": Z},
            "by_platform": {"weibo": X, "douyin": Y, ...},
            "quality_distribution": {"high": X, "medium": Y, "low": Z},
            "deduplication_stats": {
                "total_duplicates": X,
                "avg_duplicate_per_primary": Y
            }
        }
        """
        pass
```

### Week 1 (Continued): Migration & Integration

#### Task 3.5: Create Migration Service
**File:** `agent_publisher/services/material_migration_service.py`

```python
class MaterialMigrationService:
    """
    Safe migration from CandidateMaterial to UnifiedMaterial.
    
    Strategy:
    1. Create UnifiedMaterial records for all existing CandidateMaterial
    2. Detect and merge duplicates
    3. Maintain backward compatibility links
    4. Validate data integrity
    5. Support rollback if needed
    """
    
    async def migrate_all_materials(self, batch_size: int = 1000) -> Dict:
        """
        Migrate all CandidateMaterial to UnifiedMaterial.
        
        Process:
        1. Process in batches to avoid memory issues
        2. For each batch:
           - Convert to UnifiedMaterial
           - Run deduplication
           - Calculate quality scores
           - Commit to database
        3. Create audit log
        4. Return migration statistics
        """
        pass
    
    async def validate_migration(self) -> Dict[str, Any]:
        """
        Validate that migration completed successfully.
        
        Checks:
        1. Total count: UnifiedMaterial >= CandidateMaterial
        2. No data loss: URLs preserved
        3. Quality scores: all in [0, 1]
        4. Duplicates: properly marked
        """
        pass
    
    async def rollback_migration(self) -> None:
        """
        Rollback migration if needed (restore CandidateMaterial as source).
        """
        pass
```

#### Task 3.6: Create Unified Material API
**File:** `agent_publisher/api/routes/unified_materials.py`

```python
router = APIRouter(prefix="/api/materials", tags=["unified_materials"])

@router.get("/")
async def list_materials(
    agent_id: int,
    source_types: Optional[str] = None,  # comma-separated
    min_quality: float = 0.0,
    sort_by: str = "quality_score_normalized",  # or "created_at", "hot_value"
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """
    Get unified materials for an agent.
    
    Query parameters:
    - source_types: filter by "trending,rss,manual"
    - min_quality: filter by quality score (0-1)
    - sort_by: "quality_score_normalized", "created_at", "hot_value"
    - limit/offset: pagination
    """
    service = UnifiedMaterialPoolService(db)
    materials = await service.get_pool_materials(
        agent_id=agent_id,
        source_types=source_types.split(",") if source_types else None,
        min_quality=min_quality,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    return {"materials": materials, "total": len(materials)}

@router.get("/{material_id}")
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """Get detailed information about a unified material."""
    material = await db.get(UnifiedMaterial, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material

@router.post("/batch")
async def get_batch_materials(
    request: BatchMaterialsRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """Get details for multiple materials efficiently."""
    service = UnifiedMaterialPoolService(db)
    materials = await service.get_batch_materials(request.material_ids)
    return {"materials": materials}

@router.get("/stats")
async def get_pool_stats(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_access_key),
):
    """Get statistics about the material pool."""
    service = UnifiedMaterialPoolService(db)
    stats = await service.get_pool_stats(agent_id)
    return stats
```

---

## Database Schema

### New Table: unified_materials

```sql
CREATE TABLE unified_materials (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  agent_id BIGINT NOT NULL,
  
  -- Unified identification
  unified_source_id VARCHAR(255) UNIQUE NOT NULL,
  
  -- Content
  title VARCHAR(500) NOT NULL,
  summary VARCHAR(2000),
  original_url VARCHAR(2000) UNIQUE NOT NULL,
  
  -- Source information
  source_type VARCHAR(50) NOT NULL,  -- "trending", "rss", "manual"
  source_platform VARCHAR(100),      -- "weibo", "techcrunch", etc.
  source_identity VARCHAR(255),
  
  -- Quality scoring (normalized 0-1)
  quality_score_normalized FLOAT NOT NULL DEFAULT 0.5,
  
  -- Deduplication
  is_deduplicated BOOLEAN DEFAULT FALSE,
  primary_material_id BIGINT,
  duplicate_material_ids JSON,
  deduplication_score FLOAT DEFAULT 0.0,
  
  -- Tags and metadata
  tags JSON,
  metadata JSON,
  
  -- Usage tracking
  used_in_articles INT DEFAULT 0,
  usage_history JSON,
  
  -- Audit
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at DATETIME NULL,
  
  -- Indexes for fast queries
  INDEX idx_agent_id (agent_id),
  INDEX idx_unified_source_id (unified_source_id),
  INDEX idx_source_type (source_type),
  INDEX idx_quality_score (quality_score_normalized DESC),
  INDEX idx_created_at (created_at DESC),
  INDEX idx_is_deduplicated (is_deduplicated),
  
  FOREIGN KEY (agent_id) REFERENCES agent(id)
);
```

### Modified Table: candidate_material

```sql
-- Add new columns for backward compatibility
ALTER TABLE candidate_material
ADD COLUMN unified_material_id BIGINT,
ADD COLUMN quality_score_normalized FLOAT DEFAULT 0.5,
ADD FOREIGN KEY (unified_material_id) REFERENCES unified_materials(id);

-- Create index for fast lookups
CREATE INDEX idx_candidate_unified_material_id 
  ON candidate_material(unified_material_id);
```

---

## API Contract

### Endpoint: GET /api/materials/

**Request:**
```
GET /api/materials/?agent_id=1&source_types=trending,rss&min_quality=0.6&sort_by=quality_score_normalized&limit=50&offset=0
Authorization: Bearer <access_key>
```

**Response (200 OK):**
```json
{
  "materials": [
    {
      "id": 123,
      "agent_id": 1,
      "unified_source_id": "trending:weibo:abc123",
      "title": "Breaking news about tech",
      "summary": "A summary of the news...",
      "original_url": "https://weibo.com/...",
      "source_type": "trending",
      "source_platform": "weibo",
      "quality_score_normalized": 0.82,
      "is_deduplicated": true,
      "duplicate_material_ids": [456, 789],
      "deduplication_score": 0.92,
      "tags": ["trending", "weibo", "high", "recent"],
      "metadata": {
        "platform": "weibo",
        "hot_value": 82,
        "rank": 3,
        "ai_fit_score": 0.81
      },
      "created_at": "2026-04-14T10:30:00Z",
      "used_in_articles": 2
    }
  ],
  "total": 1
}
```

### Endpoint: GET /api/materials/stats

**Response:**
```json
{
  "total_materials": 1250,
  "by_source_type": {
    "trending": 800,
    "rss": 350,
    "manual": 100
  },
  "by_platform": {
    "weibo": 400,
    "douyin": 300,
    "xiaohongshu": 100,
    "techcrunch": 150
  },
  "quality_distribution": {
    "high": 450,      // >= 0.75
    "medium": 550,    // 0.5-0.75
    "low": 250        // < 0.5
  },
  "deduplication_stats": {
    "total_materials": 1250,
    "deduplicated": 1100,
    "total_duplicates_found": 350,
    "avg_duplicates_per_primary": 0.32
  }
}
```

---

## Configuration

### New Settings (config.py)

```python
# Phase 3: Unified Material Pool
trendradar_unified_pool_enabled: bool = False  # Feature flag

# Deduplication settings
material_deduplication_min_similarity: float = 0.8  # Title similarity threshold
material_dedup_url_exact_match_confidence: float = 0.95
material_dedup_title_similarity_confidence: float = 0.80

# Quality score settings
material_trending_source_weight: float = 0.6  # Weight for hot_value component
material_ai_fit_source_weight: float = 0.4    # Weight for AI analysis component
material_age_factor_enabled: bool = True       # Apply age decay to scores

# Batch processing
material_migration_batch_size: int = 1000
material_query_batch_size_max: int = 500
```

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Deduplication accuracy | >90% | False positive rate <10% |
| List materials query | <300ms | For 50 items with filtering |
| Batch materials query | <500ms | For 100 items |
| Pool stats query | <1s | Aggregation across all materials |
| Migration time | <10 minutes | For 100k materials |
| Memory usage (migration) | <1GB | Batch processing |

---

## Migration Strategy

### Phase 3 Rollout: Gradual Migration

```
Week 1:
- Deploy code with feature flag OFF (unified_pool_enabled=False)
- Old queries still use CandidateMaterial
- No production impact

Week 2:
- Internal testing with test agents only
- Run one-time migration for test agents
- Verify data integrity
- Collect performance metrics

Week 3:
- Enable for 25% of production agents
- Monitor deduplication accuracy
- Collect user feedback
- Fix any issues

Week 4:
- Enable for 100% of agents
- Monitor metrics continuously
- Begin Phase 4 planning
```

### Backward Compatibility

```python
# Old code path (still works)
from agent_publisher.models.candidate_material import CandidateMaterial

# New code path (recommended)
from agent_publisher.models.unified_material import UnifiedMaterial

# Dual query support
# Both can work simultaneously during migration
```

---

## Testing Strategy

### Unit Tests
- Deduplication algorithm: exact match, similarity, edge cases
- Quality normalization: all source types, boundary values
- Migration service: data preservation, integrity checks

### Integration Tests
- End-to-end migration: CandidateMaterial → UnifiedMaterial
- Deduplication with real data
- API query performance
- Backward compatibility with article generation

### Data Quality Tests
- No data loss during migration
- URL uniqueness after deduplication
- Score ranges validation (0-1)
- Metadata consistency

---

## Monitoring & Metrics

### Key Metrics
- **Deduplication metrics:**
  - Duplicate detection rate (%)
  - False positive rate (%)
  - Average duplicates per primary (count)
  
- **Performance metrics:**
  - Query latency (p50, p95, p99)
  - Migration time (total, per batch)
  - Database size (before/after)
  
- **Data quality:**
  - Materials without analyses (%)
  - Orphaned duplicate references (count)
  - Score distribution (histogram)

### Alerting Rules
- Query latency p95 > 500ms
- Deduplication false positive rate > 10%
- Migration failure
- Database constraint violations

---

## Risk Mitigation

### Risk 1: Data Loss During Migration
**Mitigation:** Backup database, test on staging, gradual rollout, ability to rollback

### Risk 2: Deduplication Errors
**Mitigation:** Conservative thresholds (0.8+), manual review option, metrics tracking

### Risk 3: Performance Degradation
**Mitigation:** Proper indexing, batch processing, query optimization

### Risk 4: User Confusion
**Mitigation:** Transparent migration, clear documentation, user communication

---

## Success Criteria

- ✅ All materials accessible via unified API
- ✅ >90% deduplication accuracy
- ✅ Quality scores normalized and comparable
- ✅ API latency <300ms (p95)
- ✅ Zero data loss
- ✅ Backward compatibility maintained
- ✅ All tests passing
- ✅ Ready for Phase 4

---

## Next Steps

### Immediate (End of Week 1)
1. Code review Phase 3 implementation
2. Staging deployment
3. Data quality validation
4. QA testing

### Week 2-3
1. Production rollout (0% → 25% → 100%)
2. Monitor deduplication metrics
3. Collect user feedback
4. Begin Phase 4 planning

---

## Appendix: Phase 3 Checklist

### Planning ✅
- [x] Architecture design
- [x] Data model specification
- [x] API contract definition
- [x] Migration strategy
- [x] Testing strategy

### Implementation
- [ ] Create UnifiedMaterial model
- [ ] Create DeduplicationService
- [ ] Create QualityNormalizer
- [ ] Create UnifiedMaterialPoolService
- [ ] Create MigrationService
- [ ] Create API endpoints
- [ ] Add database migrations

### Testing
- [ ] Unit tests for deduplication
- [ ] Unit tests for normalization
- [ ] Integration tests for migration
- [ ] API tests
- [ ] Data quality tests
- [ ] Performance benchmarks

### Deployment
- [ ] Code review
- [ ] Staging deployment
- [ ] QA testing
- [ ] Production rollout (0% → 25% → 100%)
- [ ] Monitoring setup

---

**Document Version:** 1.0  
**Created:** 2026-04-14  
**Status:** READY FOR IMPLEMENTATION
