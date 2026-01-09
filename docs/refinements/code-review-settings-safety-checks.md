# Code Review: Settings Safety Checks Implementation

**Date:** 2025-01-XX  
**Reviewer:** AI Assistant  
**Scope:** Uncommitted changes for Settings page and prompt validation safety checks

## Summary

This review covers the implementation of:
1. Settings page UI (Runtime Budgets, Prompt Profiles, Manuscript Defaults, Health)
2. Prompt validation enhancements (JSON schema checks, Markdown requirements)
3. Activation gating (validation status + timestamp checks)
4. Audit log fields (updated_by, updated_at)

## Critical Issues

### 1. ⚠️ **Frontend Type Mismatch: Missing Validation Fields**

**File:** `src/console/components/settings/PromptProfilesTab.tsx`

**Issue:** The `PromptProfile` interface (lines 34-47) is missing validation fields that are used later in the code:
- `validation_status?: string`
- `validation_timestamp?: string`
- `validation_errors?: string[]`

**Impact:** TypeScript will not catch type errors when accessing these fields (lines 520-521, 540+).

**Fix Required:**
```typescript
interface PromptProfile {
  prompt_id: string
  version: number
  template: string
  output_type: "json" | "markdown"
  required_fields: string[]
  constraints: {
    citation_token_format?: string
    bounded_retry?: boolean
    packet_a_facts_only?: boolean
  }
  created_at?: string
  created_by?: string
  // ADD THESE:
  validation_status?: string | null
  validation_timestamp?: string | null
  validation_errors?: string[]
}
```

### 2. ⚠️ **Validation Status Update Only on Success**

**File:** `src/orchestrator/api/settings.py` (line 419)

**Issue:** `update_validation_status` is only called when `result.get("valid")` is True:
```python
if prompt_id and version and result.get("valid"):
    try:
        service.update_validation_status(prompt_id, version, result)
```

**Impact:** If validation fails, the status is not updated in the database. This means:
- Failed validations don't persist
- User can't see why activation is blocked
- Stale "valid" status might remain from previous validation

**Fix Required:**
```python
# Update validation status regardless of result
if prompt_id and version:
    try:
        service.update_validation_status(prompt_id, version, result)
    except Exception as e:
        logger.warning(f"Failed to update validation status: {e}", exc_info=True)
        # Non-fatal: validation result still returned
```

### 3. ⚠️ **Timezone Handling Inconsistency**

**File:** `src/orchestrator/services/prompt_profile_service.py` (lines 170, 347-352)

**Issue:** 
- `update_validation_status` stores timestamp as ISO string: `get_utc_now().isoformat()`
- `activate_version` parses it and handles timezone, but the logic is complex:
  ```python
  validation_time = datetime.fromisoformat(validation_time.replace("Z", "+00:00"))
  # ...
  age = now - validation_time.replace(tzinfo=timezone.utc) if validation_time.tzinfo is None else now - validation_time
  ```

**Impact:** Potential timezone bugs if ArangoDB returns timestamps in different formats.

**Recommendation:** Standardize on storing `datetime` objects (not strings) or ensure consistent ISO format with timezone.

### 4. ⚠️ **Missing Error Handling for Invalid Timestamp Format**

**File:** `src/orchestrator/services/prompt_profile_service.py` (lines 213, 262, 347-349)

**Issue:** Timestamp parsing has try/except in `get_profile` and `list_profiles`, but `activate_version` only handles string case:
```python
if isinstance(validation_time, str):
    from datetime import datetime
    validation_time = datetime.fromisoformat(validation_time.replace("Z", "+00:00"))
```

**Impact:** If `validation_timestamp` is already a `datetime` but has wrong timezone, the code will fail.

**Fix Required:** Add try/except around parsing, similar to other methods.

## Medium Priority Issues

### 5. **Inconsistent Error Messages**

**File:** `src/orchestrator/api/settings.py`

**Issue:** Some endpoints return generic errors, others return detailed errors:
- Line 88: `return jsonify({"error": "Failed to get forbidden words"}), 500` (generic)
- Line 430: `return jsonify({"error": str(e)}), 500` (detailed)

**Recommendation:** Standardize on either generic (security) or detailed (debugging) based on environment.

### 6. **Missing Input Validation**

**File:** `src/orchestrator/api/settings.py` (line 404)

**Issue:** `template`, `output_type`, `required_fields` are extracted but not validated before calling `validate_template`:
```python
template = data.get("template", "")
output_type = data.get("output_type", "")
required_fields = data.get("required_fields", [])
```

**Impact:** Empty strings/None values might cause confusing validation errors.

**Recommendation:** Add basic validation:
```python
if not template:
    return jsonify({"error": "template is required"}), 400
if not output_type:
    return jsonify({"error": "output_type is required"}), 400
```

### 7. **Frontend: Missing Validation Status Display**

**File:** `src/console/components/settings/PromptProfilesTab.tsx`

**Issue:** The code references `selectedProfile.validation_status` and `selectedProfile.validation_timestamp` (lines 520-521, 540+) but the UI doesn't show this information clearly in the version dropdown or editor.

**Recommendation:** Add visual indicators:
- Badge in version dropdown showing "Validated" / "Invalid" / "Not Validated"
- Timestamp display in editor panel

## Low Priority / Suggestions

### 8. **Code Duplication: Timestamp Parsing**

**File:** `src/orchestrator/services/prompt_profile_service.py`

**Issue:** Timestamp parsing logic is duplicated in `get_profile` (lines 210-216) and `list_profiles` (lines 259-265).

**Recommendation:** Extract to helper method:
```python
def _parse_validation_timestamp(self, doc: Dict[str, Any]) -> None:
    """Parse validation_timestamp from string to datetime if needed."""
    if "validation_timestamp" in doc and isinstance(doc["validation_timestamp"], str):
        try:
            from datetime import datetime
            doc["validation_timestamp"] = datetime.fromisoformat(
                doc["validation_timestamp"].replace("Z", "+00:00")
            )
        except Exception:
            pass  # Keep as string if parsing fails
```

### 9. **Missing Unit Tests**

**Files:** New services and API endpoints

**Issue:** No unit tests found for:
- `PromptProfileService.update_validation_status()`
- `PromptProfileService.activate_version()` safety checks
- `SettingsService.update_settings()` audit fields

**Recommendation:** Add tests for:
- Validation status update (valid/invalid)
- Activation blocking (stale validation, invalid status)
- Timestamp parsing edge cases

### 10. **Documentation Gaps**

**Files:** API endpoints

**Issue:** Some endpoints lack examples in docstrings:
- `/api/settings/prompts/validate` - no example request/response
- `/api/settings/prompts/activate` - no example error responses

**Recommendation:** Add example request/response bodies to docstrings.

## Positive Observations

✅ **Good separation of concerns:** Service layer handles business logic, API layer handles HTTP  
✅ **Comprehensive validation:** JSON and Markdown validation covers key requirements  
✅ **Clear error messages:** Activation blocking provides actionable feedback  
✅ **Audit trail:** `updated_by` and `updated_at` properly tracked  
✅ **Frontend UX:** Validation warnings displayed, activation button properly disabled

## Testing Recommendations

1. **Test validation status persistence:**
   - Validate a prompt → check DB has `validation_status="valid"`
   - Validate with errors → check DB has `validation_status="invalid"` and `validation_errors`

2. **Test activation gating:**
   - Try to activate without validation → should fail
   - Try to activate with stale validation (>30 min) → should fail
   - Try to activate with recent valid validation → should succeed

3. **Test timezone handling:**
   - Store validation with UTC timestamp
   - Retrieve and check age calculation is correct
   - Test with different timezone formats from ArangoDB

4. **Test frontend:**
   - Load prompt with validation status → check UI displays correctly
   - Validate prompt → check status updates in UI
   - Try to activate invalid prompt → check error message displays

## Summary of Required Fixes

**Critical (Must Fix Before Merge):**
1. ✅ **FIXED:** Add validation fields to `PromptProfile` interface in frontend
2. ✅ **FIXED:** Update validation status even when validation fails
3. ✅ **FIXED:** Add error handling for timestamp parsing in `activate_version`
4. ✅ **FIXED:** Add input validation for validate endpoint

**Medium Priority (Should Fix):**
4. Standardize error message format
5. Add input validation for validate endpoint
6. Improve UI display of validation status

**Low Priority (Nice to Have):**
7. Extract timestamp parsing to helper method
8. Add unit tests
9. Enhance API documentation

## Overall Assessment

**Status:** ⚠️ **Needs Fixes Before Merge**

The implementation is solid overall, but has a few critical type safety and logic issues that need to be addressed. The validation and activation gating logic is well-designed, but needs better error handling and consistency.

**Estimated Fix Time:** 1-2 hours for critical issues, 2-3 hours for medium priority.
