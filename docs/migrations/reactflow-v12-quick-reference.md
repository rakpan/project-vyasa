# React Flow v12 Migration - Quick Reference

**Quick checklist for executing the migration from `reactflow@^11` to `@xyflow/react@^12`**

## Pre-Flight Checklist

- [ ] Feature branch created: `git checkout -b migrate/reactflow-v12`
- [ ] Current state tagged: `git tag pre-reactflow-v12-migration`
- [ ] Test coverage reviewed for `LiveGraphWorkbench`

## Step 1: Update Dependencies

```bash
cd src/console
npm uninstall reactflow @reactflow/controls @reactflow/background
npm install @xyflow/react@^12.0.0
```

## Step 2: Update Imports

**File**: `src/console/components/LiveGraphWorkbench.tsx`

### Import Changes

**Before**:
```typescript
import ReactFlow, { ... } from "reactflow"
import "reactflow/dist/style.css"
import { useStoreApi } from "reactflow"
```

**After**:
```typescript
import { ReactFlow, ..., useStoreApi } from "@xyflow/react"
import "@xyflow/react/dist/style.css"
```

### Specific Changes Needed

1. **Line 4-20**: Change import source from `"reactflow"` to `"@xyflow/react"`
2. **Line 21**: Change CSS import from `"reactflow/dist/style.css"` to `"@xyflow/react/dist/style.css"`
3. **Line 35**: Remove separate `useStoreApi` import (now in main import)

## Step 3: Verify No Breaking Changes

- [ ] Check for `node.width` or `node.height` usage (should use `node.measured?.width` if found)
- [ ] Verify CSS class names still work (`.react-flow__*` classes)
- [ ] Test all event handlers still function

## Step 4: Test

```bash
npm run build  # Should succeed
npm run dev     # Test in browser
```

### Test Scenarios

- [ ] Graph renders with nodes/edges
- [ ] Node click opens detail sheet
- [ ] Context menu toggles verification
- [ ] Redline mode works (delete/update)
- [ ] SSE updates work
- [ ] Layout algorithm positions correctly
- [ ] Zoom/pan works
- [ ] MiniMap displays

## Step 5: Rollback (if needed)

```bash
git revert <commit>
npm install reactflow@^11.11.4 @reactflow/controls@^11.2.14 @reactflow/background@^11.3.6
```

## Key Differences

| Aspect | v11 | v12 |
|--------|-----|-----|
| Package | `reactflow` | `@xyflow/react` |
| CSS Import | `reactflow/dist/style.css` | `@xyflow/react/dist/style.css` |
| Controls | `@reactflow/controls` (separate) | Included in main package |
| Background | `@reactflow/background` (separate) | Included in main package |
| Node Dimensions | `node.width` | `node.measured?.width` |

## Files Modified

- `src/console/package.json` - Dependency updates
- `src/console/components/LiveGraphWorkbench.tsx` - Import updates

## Estimated Time

- **Quick migration**: 30-45 minutes
- **With thorough testing**: 2-3 hours

---

**See full migration plan**: `docs/migrations/reactflow-v12-migration-plan.md`

