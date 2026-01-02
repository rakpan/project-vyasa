# React Flow v11 → v12+ Migration Plan

**Status**: Planning  
**Target Version**: `@xyflow/react@^12.0.0`  
**Current Version**: `reactflow@^11.11.4`  
**Risk Level**: Medium  
**Estimated Effort**: 2-4 hours

---

## Executive Summary

React Flow v11 (`reactflow`) is being migrated to v12+ (`@xyflow/react`) to:
- **Mitigate security risks** from outdated dependencies
- **Leverage performance improvements** (SSR support, optimized rendering)
- **Access new features** (built-in dark mode, improved state management)
- **Maintain long-term maintainability** with active upstream support

**Critical Breaking Change**: Package renamed from `reactflow` to `@xyflow/react` - all imports must be updated.

---

## Current State Assessment

### Dependencies
```json
{
  "reactflow": "^11.11.4",
  "@reactflow/controls": "^11.2.14",
  "@reactflow/background": "^11.3.6"
}
```

### Usage Locations
1. **Primary Component**: `src/console/components/LiveGraphWorkbench.tsx`
   - Uses: `ReactFlow`, `useNodesState`, `useEdgesState`, `useStoreApi`
   - Imports: `Node`, `Edge`, `Background`, `Controls`, `MiniMap`, `Connection`, `addEdge`
   - Event Handlers: `NodeMouseHandler`, `EdgeMouseHandler`, `OnNodesDelete`, `OnEdgesDelete`, `OnEdgeUpdateFunc`
   - CSS: `reactflow/dist/style.css`

### React Compatibility
- **Current**: React 19 ✅
- **v12 Requirement**: React 18+ ✅ (compatible)

### Next.js Compatibility
- **Current**: Next.js 15.2.4 ✅
- **v12 Requirement**: Next.js 13+ ✅ (compatible)

---

## Breaking Changes & Migration Requirements

### 1. Package Renaming (CRITICAL)
**Old**:
```typescript
import ReactFlow from "reactflow"
import { useNodesState, useEdgesState } from "reactflow"
import "reactflow/dist/style.css"
```

**New**:
```typescript
import { ReactFlow } from "@xyflow/react"
import { useNodesState, useEdgesState } from "@xyflow/react"
import "@xyflow/react/dist/style.css"
```

### 2. Node Measurement Attributes
**Old**:
```typescript
const width = node.width
const height = node.height
```

**New**:
```typescript
const width = node.measured?.width
const height = node.measured?.height
```

**Impact**: Low - Current codebase doesn't appear to access node dimensions directly.

### 3. Hook API Changes
- `useStoreApi()` - **No change** (still available)
- `useNodesState()` - **No change** (still available)
- `useEdgesState()` - **No change** (still available)
- `useReactFlow()` - **No change** (still available)

### 4. Component Props
- `ReactFlow` component props - **Mostly unchanged**
- `Background` - **No change**
- `Controls` - **No change** (now part of `@xyflow/react`, not separate package)
- `MiniMap` - **No change**

### 5. Type Definitions
- Type imports remain the same (e.g., `Node`, `Edge`, `Connection`)
- All types now exported from `@xyflow/react`

---

## Migration Steps

### Phase 1: Pre-Migration Preparation

#### Step 1.1: Create Feature Branch
```bash
git checkout -b migrate/reactflow-v12
```

#### Step 1.2: Backup Current State
```bash
# Tag current working state
git tag pre-reactflow-v12-migration
```

#### Step 1.3: Review Test Coverage
- [ ] Verify `LiveGraphWorkbench` component has test coverage
- [ ] Document current behavior (screenshots/videos if needed)
- [ ] Identify manual test scenarios:
  - Graph rendering with nodes/edges
  - Node/edge interactions (click, context menu)
  - Redline mode functionality
  - SSE graph updates
  - Layout calculations (dagre)

### Phase 2: Dependency Updates

#### Step 2.1: Remove Old Packages
```bash
cd src/console
npm uninstall reactflow @reactflow/controls @reactflow/background
```

#### Step 2.2: Install New Package
```bash
npm install @xyflow/react@^12.0.0
```

**Note**: `@reactflow/controls` and `@reactflow/background` are now included in `@xyflow/react` - no separate packages needed.

#### Step 2.3: Verify Package Installation
```bash
npm list @xyflow/react
# Should show: @xyflow/react@12.x.x
```

### Phase 3: Code Migration

#### Step 3.1: Update Import Statements

**File**: `src/console/components/LiveGraphWorkbench.tsx`

**Change 1 - Main imports** (Lines 4-20):
```typescript
// OLD
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Connection,
  addEdge,
  NodeMouseHandler,
  MarkerType,
  EdgeMouseHandler,
  OnNodesDelete,
  OnEdgesDelete,
  OnEdgeUpdateFunc,
} from "reactflow"
import "reactflow/dist/style.css"
import { useStoreApi } from "reactflow"

// NEW
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Connection,
  addEdge,
  NodeMouseHandler,
  MarkerType,
  EdgeMouseHandler,
  OnNodesDelete,
  OnEdgesDelete,
  OnEdgeUpdateFunc,
  useStoreApi,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
```

**Change 2 - CSS class names** (Line 404):
```typescript
// OLD
.react-flow__edge-label {
  display: ${showDetails ? "block" : "none"};
}

// NEW (if class names changed - verify in v12 docs)
.react-flow__edge-label {
  display: ${showDetails ? "block" : "none"};
}
```

**Note**: CSS class names may remain the same, but verify in v12 documentation.

#### Step 3.2: Verify Component Usage
- [ ] `ReactFlow` component - verify all props are still valid
- [ ] `Background` - verify rendering
- [ ] `Controls` - verify toolbar functionality
- [ ] `MiniMap` - verify minimap rendering

#### Step 3.3: Update TypeScript Types (if needed)
- [ ] Check if any custom type extensions need updates
- [ ] Verify `Node`, `Edge` type definitions are compatible

### Phase 4: Testing & Validation

#### Step 4.1: Build Verification
```bash
cd src/console
npm run build
# Should complete without errors
```

#### Step 4.2: Development Server Test
```bash
npm run dev
# Navigate to graph workbench page
# Verify:
# - Graph renders correctly
# - Nodes/edges display properly
# - Interactions work (click, hover, context menu)
# - Redline mode functions
# - SSE updates work
```

#### Step 4.3: Functional Testing Checklist

**Graph Rendering**:
- [ ] Nodes render with correct labels
- [ ] Edges render with correct connections
- [ ] Layout algorithm (dagre) positions nodes correctly
- [ ] Zoom/pan functionality works
- [ ] MiniMap displays correctly

**Interactions**:
- [ ] Node click opens detail sheet
- [ ] Node context menu toggles verification
- [ ] Edge click highlights PDF evidence
- [ ] Edge context menu toggles verification
- [ ] Node/edge deletion works in redline mode
- [ ] Edge updates work in redline mode

**SSE Integration**:
- [ ] Graph updates from SSE stream correctly
- [ ] New nodes/edges appear dynamically
- [ ] Connection status indicator works
- [ ] Error handling works on connection loss

**Performance**:
- [ ] Large graphs (100+ nodes) render smoothly
- [ ] Layout recalculation doesn't cause jank
- [ ] Memory usage is acceptable

#### Step 4.4: Visual Regression Testing
- [ ] Compare graph appearance before/after
- [ ] Verify styling (colors, fonts, spacing)
- [ ] Check responsive behavior

### Phase 5: Documentation Updates

#### Step 5.1: Update README
- [ ] Update `src/console/README.md` with new package name
- [ ] Update dependency list in main `README.md`

#### Step 5.2: Update Architecture Docs
- [ ] Update `docs/architecture/system-map.md` if React Flow is mentioned
- [ ] Update technology stack references

### Phase 6: Deployment

#### Step 6.1: Pre-Deployment Checklist
- [ ] All tests pass
- [ ] Build succeeds
- [ ] Manual testing complete
- [ ] Documentation updated
- [ ] Code review completed

#### Step 6.2: Deploy to Staging
```bash
# Test in Docker environment
cd deploy
./start.sh
# Verify console loads and graph workbench functions
```

#### Step 6.3: Production Deployment
- [ ] Merge feature branch to main
- [ ] Tag release
- [ ] Deploy via standard process
- [ ] Monitor for errors in production logs

---

## Risk Assessment

### High Risk Areas
1. **Import Path Changes** - All imports must be updated correctly
   - **Mitigation**: Use find/replace with careful verification
   - **Rollback**: Git revert if issues arise

2. **CSS Class Name Changes** - Styling may break if class names changed
   - **Mitigation**: Test visual appearance thoroughly
   - **Rollback**: Revert CSS import if needed

### Medium Risk Areas
1. **Node Measurement API** - If code accesses node dimensions
   - **Mitigation**: Search codebase for `node.width`/`node.height` usage
   - **Current Status**: ✅ No usage found in current codebase

2. **Hook Behavior Changes** - Subtle API changes in hooks
   - **Mitigation**: Comprehensive testing of state management
   - **Rollback**: Revert if state management breaks

### Low Risk Areas
1. **Type Definitions** - Should be backward compatible
2. **Component Props** - Most props unchanged
3. **Event Handlers** - API appears stable

---

## Rollback Plan

If migration fails:

1. **Immediate Rollback**:
   ```bash
   git revert <migration-commit>
   npm install reactflow@^11.11.4 @reactflow/controls@^11.2.14 @reactflow/background@^11.3.6
   ```

2. **Partial Rollback** (if only specific features break):
   - Keep new package but add compatibility shims
   - Document known issues for future fix

3. **Post-Rollback Actions**:
   - Document failure reasons
   - Create issues for blocking problems
   - Revisit migration plan with lessons learned

---

## Success Criteria

Migration is considered successful when:
- ✅ All dependencies updated to v12+
- ✅ Application builds without errors
- ✅ Graph workbench renders correctly
- ✅ All interactions function as before
- ✅ SSE integration works
- ✅ No performance regressions
- ✅ Documentation updated
- ✅ Production deployment successful

---

## Timeline Estimate

| Phase | Estimated Time | Dependencies |
|-------|---------------|--------------|
| Pre-Migration Prep | 30 min | None |
| Dependency Updates | 15 min | None |
| Code Migration | 45 min | Dependency updates |
| Testing & Validation | 60-90 min | Code migration |
| Documentation | 15 min | Testing complete |
| Deployment | 30 min | All above |
| **Total** | **3-4 hours** | |

---

## Additional Resources

- [React Flow v12 Release Notes](https://xyflow.com/blog/react-flow-12-release)
- [Migration Guide](https://reactflow.dev/learn/troubleshooting/migrate-to-v12)
- [v12 Documentation](https://reactflow.dev/)
- [GitHub Issues](https://github.com/xyflow/xyflow/issues) - Search for v12 migration issues

---

## Notes

- **React 19 Compatibility**: v12 supports React 18+, and React 19 should work, but verify if any issues arise
- **Next.js 15 Compatibility**: Should be compatible, but test SSR behavior if using server components
- **Performance**: v12 includes performance improvements - monitor for positive impact
- **Future Maintenance**: v12+ is actively maintained; v11 will receive only security patches

---

**Last Updated**: 2025-01-01  
**Migration Owner**: TBD  
**Review Status**: Pending

