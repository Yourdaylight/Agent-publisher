# Agent Publisher - Test Coverage Improvements Roadmap

## Current Status

- ✅ **226 tests passing** (100% pass rate)
- ✅ **18 test files** with focused coverage
- ✅ **Zero runtime warnings**
- ⚠️ **18 core services** without dedicated tests
- ⚠️ **High-priority gaps** in material ingestion and governance

## Phase 1: Critical Service Coverage (High Priority)

### 1.1 CandidateMaterialService Tests
**Status**: NOT COVERED (Core CRUD operations)  
**Importance**: 🔴 CRITICAL

The `CandidateMaterialService` is the central hub for material ingestion across all sources. 
It handles duplicate detection, quality gating, and tagging.

**Test Cases to Add** (15-20 tests):
```python
# Core CRUD operations
- test_ingest_creates_new_material()
- test_ingest_detects_duplicate_url()
- test_ingest_detects_duplicate_title()
- test_ingest_applies_auto_tags()
- test_ingest_with_agent_identity_tag()
- test_ingest_quality_gate_filtering()
- test_ingest_with_source_type_tag()

# Listing and filtering
- test_get_list_by_source_type()
- test_get_list_by_platform()
- test_get_list_by_tags()
- test_get_list_pagination()
- test_get_list_sorting()

# Tag management
- test_tag_update_adds_single_tag()
- test_tag_update_adds_multiple_tags()
- test_tag_update_removes_tag()
- test_tag_update_preserves_existing_tags()

# Status workflow
- test_material_status_transitions()
- test_mark_used_updates_status()

# Edge cases
- test_ingest_with_unicode_content()
- test_ingest_with_long_title()
- test_ingest_null_metadata()
```

**File Location**: `tests/test_candidate_material_service.py` (new)

**Dependencies**: SQLAlchemy session mock, CandidateMaterial model

---

### 1.2 SystemLogService Tests
**Status**: NOT COVERED (Audit and governance)  
**Importance**: 🟠 HIGH

The system logs are critical for audit trails and compliance.

**Test Cases to Add** (10-12 tests):
```python
# Log creation
- test_create_log_entry()
- test_create_log_with_all_fields()
- test_create_log_sanitizes_sensitive_data()

# Querying
- test_get_logs_by_email()
- test_get_logs_by_operation()
- test_get_logs_by_resource_type()
- test_get_logs_time_range_filter()
- test_get_logs_pagination()

# Filtering
- test_logs_admin_sees_all()
- test_logs_user_sees_only_own()

# Cleanup
- test_cleanup_old_logs()
```

**File Location**: `tests/test_system_log_service.py` (new)

---

### 1.3 GovernanceService Tests
**Status**: PARTIAL COVERAGE (analytics only)  
**Importance**: 🟠 HIGH

Coverage for stats generation and analytics.

**Test Cases to Add** (12-15 tests):
```python
# Source mode stats
- test_get_source_mode_stats_admin_sees_all()
- test_get_source_mode_stats_user_sees_only_own()
- test_source_mode_stats_with_zero_data()

# Tag analytics
- test_get_tag_stats_counts()
- test_get_tag_stats_sorting()
- test_tag_stats_with_special_characters()

# Intake trends
- test_get_daily_intake_trend()
- test_get_daily_intake_trend_with_gaps()
- test_get_daily_intake_trend_time_range()

# Platform analysis
- test_get_platform_distribution()
- test_get_platform_distribution_by_user()

# Quality metrics
- test_get_average_quality_scores()
- test_get_duplicate_rate()
```

**File Location**: `tests/test_governance_service.py` (new)

---

## Phase 2: Supporting Service Coverage (Medium Priority)

### 2.1 CreditsService Tests (8-10 tests)
**Importance**: 🟡 MEDIUM

Focus on transaction atomicity and balance management.

**Key Tests**:
- Balance retrieval
- Credit deduction with rollback on error
- Concurrent transaction handling
- Insufficient balance error handling

---

### 2.2 MembershipService Tests (6-8 tests)
**Importance**: 🟡 MEDIUM

Plan management and user tier validation.

**Key Tests**:
- Get default plans
- Plan upgrade flow
- Feature access by tier
- Billing period calculations

---

### 2.3 PromptTemplateService Tests (8-10 tests)
**Importance**: 🟡 MEDIUM

Template CRUD and validation.

**Key Tests**:
- Init built-in templates
- Template retrieval by ID
- Template listing with filters
- Template updates
- Built-in template protection

---

## Phase 3: Advanced Feature Coverage (Lower Priority)

### 3.1 SearchCollectorService Tests (15-20 tests)
**Status**: STUB ONLY (Not implemented)  
**Importance**: 🟡 MEDIUM (when implemented)

When search implementation arrives, add comprehensive tests for:
- Keyword search
- Site constraint filtering
- Result ranking and scoring
- Search config validation

---

### 3.2 AgentInitService Tests (5-8 tests)
**Importance**: 🟢 LOW

Built-in agent initialization.

**Key Tests**:
- Initialize built-in agent
- Idempotency check
- Default settings validation

---

## Test Infrastructure Improvements

### Configuration Management
- Add fixtures for different user roles (admin, regular user, guest)
- Create reusable database state factories
- Add test data builders for complex objects

### Performance Testing
- Add benchmarks for slow queries
- Monitor test execution time trends
- Profile memory usage during tests

### Coverage Reporting
- Add pytest-cov to development dependencies
- Generate coverage reports in CI/CD
- Track coverage trends over time

---

## Implementation Strategy

### Week 1: Critical Services
1. Start with `CandidateMaterialService` (most widely used)
2. Add `SystemLogService` tests (audit compliance)
3. Begin `GovernanceService` tests

**Target**: 40-50 new tests

### Week 2: Supporting Services
1. `CreditsService` tests
2. `MembershipService` tests
3. `PromptTemplateService` tests

**Target**: 20-30 new tests

### Week 3: Advanced Features & Polish
1. `SearchCollectorService` placeholder tests
2. `AgentInitService` tests
3. Test infrastructure improvements

**Target**: 15-20 new tests

### Final: Documentation & Validation
- Update test README with new patterns
- Run full suite validation
- Generate coverage metrics
- Update CI/CD pipeline

---

## Expected Outcomes

### After Implementation
- **~300-350 total tests** (up from 226)
- **~98% code coverage** for core services
- **Comprehensive audit trail validation**
- **Full CRUD operation coverage**
- **Better error handling validation**

### Reliability Improvements
- Catch edge cases before production
- Validate state transitions properly
- Ensure proper cleanup and rollback
- Validate multi-tenant isolation

---

## Testing Best Practices to Maintain

### 1. Naming Convention
```python
# Good: Describes behavior, not implementation
async def test_ingest_detects_duplicate_url_and_marks_as_duplicate():
    pass

# Bad: Too vague or implementation-focused
async def test_ingest():
    pass
```

### 2. Async Test Pattern
```python
@pytest.mark.asyncio
async def test_something():
    # Always use AsyncMock for async operations
    # Never mix sync and async without proper handling
    pass
```

### 3. Mock Database Pattern
```python
db = AsyncMock()
# Fix for non-async SQLAlchemy methods:
db.add = MagicMock()
db.execute.return_value = MagicMock()
```

### 4. Test Documentation
```python
async def test_some_feature():
    """Short description of what is tested.
    
    This test validates:
    - Behavior 1
    - Behavior 2
    - Edge case handling
    """
```

---

## Success Metrics

1. ✅ All new tests pass
2. ✅ No runtime warnings
3. ✅ Test execution time < 10 seconds
4. ✅ Code coverage > 95% for tested services
5. ✅ CI/CD integration successful

---

## Notes

- Tests should be independent and can run in any order
- Use fixtures for common setup (database, mocks, tokens)
- Document complex test scenarios
- Keep test data small and realistic
- Avoid hardcoded values; use constants or factories
