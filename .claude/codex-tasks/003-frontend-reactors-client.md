# Codex Task 003 — Frontend API client + hook for reactors list

## Why this task

**Third empirical test of Codex as back-maker substitute.** Tests 001 v2 and 002 PASSed (both backend). This task moves to **frontend** to verify Codex handles a different codebase area + the **designer-territory boundary** (frontend UI layer is owned by designer agent — Codex must NOT touch styles, JSX rendering, MOCK_* constants, animations, colors, layout).

Real codebase need: `GET /api/v1/projects/{id}/reactors/` was just shipped (commit 042bed4). Frontend has no client function or hook to consume it. This task adds the **data-layer plumbing** so future UI work (separate, by design pipeline) can wire it up.

## What to do

Two files, both **data layer only**:

### File 1 — `frontend/src/api/social.js` (modify)

Add a new function `getProjectReactors(projectId, params)` to the existing module. Follow the existing style (look at `followUser` / `unfollowUser`). After your change, the file should look like:

```javascript
/**
 * api/social.js
 * Social graph: follow / unfollow + project reactors.
 */

import { callApi } from './core.js'

export async function followUser(userId) {
  return await callApi('POST', `/users/${userId}/follow/`)
}

export async function unfollowUser(userId) {
  await callApi('DELETE', `/users/${userId}/follow/`)
}

export async function getProjectReactors(projectId, { page = 1, pageSize = 50 } = {}) {
  return await callApi('GET', `/projects/${projectId}/reactors/?page=${page}&page_size=${pageSize}`)
}
```

Notes:
- Default args via destructuring with defaults: `{ page = 1, pageSize = 50 } = {}`.
- Build the query string inline (other functions in this codebase do similarly). Don't pull in `URLSearchParams` for two simple params.
- Snake-case `page_size` in the query string matches backend's `_paginate_queryset` keys.
- Return shape from backend is `{results: [...], page, page_size, has_more, total}` — pass through unchanged.

### File 2 — `frontend/src/hooks/useProjectReactors.js` (NEW)

Create a new file. Follow the existing `useImageTelemetry.js` style (see `frontend/src/hooks/useImageTelemetry.js` for tone, comments, and structure). Spec:

```javascript
import { useState, useEffect, useCallback } from 'react'
import { getProjectReactors } from '../api/social.js'

/**
 * useProjectReactors — fetch and paginate the reactor list for a project.
 *
 * Returns:
 *   reactors    — accumulated list of reactor user objects across loaded pages
 *   loading     — true while fetching the next page
 *   error       — Error or null
 *   hasMore     — true if more pages exist on the server
 *   total       — total reactor count from latest response (or null before first load)
 *   loadMore()  — fetch the next page
 *   reset()     — clear state (use when projectId changes; effect calls this automatically)
 *
 * Usage:
 *   const { reactors, hasMore, loadMore } = useProjectReactors(projectId)
 *   <button onClick={loadMore} disabled={!hasMore}>Load more</button>
 *
 * No automatic refetch on focus or interval — caller decides when to loadMore.
 * 403 responses surface as `error.message === 'Forbidden'` (or whatever message
 * callApi propagates); the hook does not branch on status code.
 */
export function useProjectReactors(projectId, { pageSize = 50 } = {}) {
  const [reactors, setReactors] = useState([])
  const [page, setPage] = useState(0)         // 0 = nothing loaded yet
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hasMore, setHasMore] = useState(true)
  const [total, setTotal] = useState(null)

  const reset = useCallback(() => {
    setReactors([])
    setPage(0)
    setError(null)
    setHasMore(true)
    setTotal(null)
  }, [])

  const loadMore = useCallback(async () => {
    if (loading || !hasMore || !projectId) return
    const nextPage = page + 1
    setLoading(true)
    setError(null)
    try {
      const resp = await getProjectReactors(projectId, { page: nextPage, pageSize })
      setReactors(prev => [...prev, ...(resp.results || [])])
      setPage(nextPage)
      setHasMore(!!resp.has_more)
      setTotal(resp.total ?? null)
    } catch (err) {
      setError(err)
      setHasMore(false)
    } finally {
      setLoading(false)
    }
  }, [projectId, page, pageSize, loading, hasMore])

  // Reset when projectId changes (don't auto-fetch — caller decides)
  useEffect(() => {
    reset()
  }, [projectId, reset])

  return { reactors, loading, error, hasMore, total, loadMore, reset }
}
```

**Key correctness notes** (Codex must verify):
1. The hook does NOT auto-fetch on mount. The reset effect runs on `projectId` change, but `loadMore` is what triggers an actual API call. This matches the existing pattern in this codebase (callers explicitly call `initSession`, `loadProjects`, etc.).
2. State setters: avoid stale-closure bugs. `loadMore` depends on `page` and re-creates when page changes — this is intentional for React 18 batching.
3. Error handling: when API throws, set error AND set `hasMore=false` to prevent loops. Caller can call `reset()` to retry.

## Constraints (hard)

1. **Touch only these two files**: `frontend/src/api/social.js` (modify) and `frontend/src/hooks/useProjectReactors.js` (create).
2. **NO UI changes anywhere**. Designer territory: do NOT touch any `.jsx` file, do NOT add MOCK_* constants, do NOT touch styles. If you find yourself writing JSX, STOP — you're out of scope.
3. **NO new dependencies**. Use only React hooks (already in project) + existing `callApi` + the new `getProjectReactors`.
4. **No automated tests required** — the frontend has no jest/vitest setup. Validation is ESLint + Vite build green.
5. **Match existing code style**: 2-space indent, single quotes for strings, JSDoc-style comments at top, named export (no default export) for both the api function and the hook.

## CRITICAL: Autonomous validation loop

You MUST run BOTH of these and verify zero errors before signaling DONE:

```bash
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: both exit 0. ESLint output: 0 problems. Vite build: succeeds.

If either fails:
1. Read the error.
2. Fix it (within plan scope — don't rewrite spec).
3. Run again.
4. Repeat until both green.

**Do NOT signal DONE on red.** If 3 fix iterations don't get to green, signal `===CODEX-TASK-003-BLOCKED===` with one-line reason and stop.

## Acceptance

After your changes, both commands must exit 0:

```bash
cd frontend && npm run lint
cd frontend && npm run build
```

The new hook file should be importable from any page via:
```javascript
import { useProjectReactors } from '../hooks/useProjectReactors.js'
```

(Don't actually wire it into any page — that's separate UI work owned by designer.)

## Output protocol

When complete, output exactly:
```
===CODEX-TASK-003-DONE===
```

If blocked:
```
===CODEX-TASK-003-BLOCKED=== <one-line reason>
```

## Permission scope

Read/Edit only the 2 files listed. Read existing `frontend/src/api/core.js`, `frontend/src/api/social.js` (current state), and `frontend/src/hooks/useImageTelemetry.js` (style reference) — read-only. Run `npm run lint` and `npm run build` from `frontend/` directory.

Do NOT:
- Modify any `.jsx` file
- Touch backend
- Add packages (no `npm install`)
- Run git commands
- Touch `DESIGN.md` or anything in `.claude/agents/design-*`
