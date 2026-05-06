# Codex Task 002 — Reactors list endpoint (mixed file: views + urls + tests)

## Why this task

Second empirical test (per advisor's 3-PASS rule) of Codex as back-maker substitute. Goal: see if Codex handles a **mixed-file mechanical task** (views + url + tests) as well as it handled the single-file v2 (UserProfile validators).

Real codebase need: SOC2 ships `POST /projects/{id}/react/` and `DELETE /projects/{id}/react/`, but there's no way to **list users who reacted** to a project. This is a missing user-facing endpoint that mirrors the existing `GET /users/{id}/followers/` pattern.

## What to do

Add **`GET /api/v1/projects/{project_id}/reactors/`** — paginated list of users who reacted to a project, mirroring `FollowersListView` exactly in structure.

### File 1 — `backend/apps/social/views.py` (modify)

Add a new class `ProjectReactorsListView(APIView)` near the existing `ReactionView` (after `ReactionView` is fine). Mirror `FollowersListView` exactly in structure. Spec:

```python
class ProjectReactorsListView(APIView):
    """GET /api/v1/projects/{project_id}/reactors/ — users who reacted to a project.

    Visibility gate (mirrors POST):
      - public project: anyone can list (200)
      - private project + owner viewing: 200 with full list
      - private project + non-owner / anonymous: 403

    Query params:
      page (default 1), page_size (default 50, max 50) — same as _paginate_queryset.

    Response 200:
      {results: [UserMiniSerializer...], page, page_size, has_more, total}
    """
    permission_classes = [AllowAny]

    def get(self, request, project_id):
        from apps.recommendation.models import Project
        project = get_object_or_404(Project, project_id=project_id)

        # Visibility gate (mirror POST in ReactionView)
        if project.visibility != 'public':
            requester = getattr(request.user, 'profile', None) if request.user.is_authenticated else None
            if requester is None or project.user_id != requester.pk:
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        qs = (
            UserProfile.objects
            .filter(reactions__project=project)
            .select_related('user')
            .order_by('-reactions__created_at')
        )
        items, meta = _paginate_queryset(qs, request)
        return Response({
            'results': UserMiniSerializer(items, many=True).data,
            **meta,
        })
```

**Key gotchas verified against the codebase**:
1. `UserProfile.objects.filter(reactions__project=project)` — confirmed: `Reaction.user` has `related_name='reactions'` (plural). Use `reactions__project`, not `reaction__project`.
2. `order_by('-reactions__created_at')` — same: `reactions__created_at` (plural).
3. Imports: `UserProfile`, `UserMiniSerializer`, `_paginate_queryset`, `status`, `Response`, `AllowAny`, `APIView`, `get_object_or_404` — all already imported in `apps/social/views.py`. No new imports needed for the view itself. (Be careful with `Project` import — the existing `ReactionView.post` does a **lazy local import** `from apps.recommendation.models import Project` inside the method to avoid a circular dependency. Mirror that pattern in `ProjectReactorsListView.get`.)

### File 2 — `backend/apps/social/urls.py` (modify)

Add a new path entry for the endpoint, after the existing `path('projects/<uuid:project_id>/react/', ...)` line:

```python
path('projects/<uuid:project_id>/reactors/', ProjectReactorsListView.as_view(), name='project-reactors'),
```

Don't forget to import `ProjectReactorsListView` at the top of urls.py — extend the existing `from .views import` line.

### File 3 — `backend/apps/social/tests/test_reaction.py` (modify)

Add a new class `TestReactorsList` near the bottom of the file (after `TestReactionEdgeCases` is fine). Mirror the style of existing classes (`TestReactionCreate` etc.) — same fixtures (`user_a`, `user_b`, `auth_client_a`, `auth_client_b`, `anon_client`), same use of `pytest.mark.django_db`, same `from rest_framework.test import APIClient` if needed.

**4 tests required**:

1. **`test_reactors_list_public_project_returns_200_with_reactor`**:
   - user_a reacts to user_b's public project.
   - Anyone (anon_client OR auth_client_a) calls `GET /api/v1/projects/{project_id}/reactors/`.
   - Expect 200.
   - Response `results` array contains exactly 1 entry; that entry's `user_id` matches user_a.

2. **`test_reactors_list_private_project_owner_returns_200`**:
   - user_b's project is private. user_b reacts to it (own project).
   - user_b calls reactors endpoint via `auth_client_b`.
   - Expect 200, `results` has 1 entry.

3. **`test_reactors_list_private_project_non_owner_returns_403`**:
   - user_b's project is private. user_a tries `GET /api/v1/projects/{project_id}/reactors/` via `auth_client_a`.
   - Expect 403.
   - Response body has `detail: 'Forbidden'` or similar.

4. **`test_reactors_list_nonexistent_project_returns_404`**:
   - `GET /api/v1/projects/00000000-0000-0000-0000-000000000000/reactors/` (random UUID).
   - Expect 404.

Pagination test is optional (5th test) — if you want to add it, create 3 reactors and verify default `page_size=50` returns all 3 + `has_more: false`.

## Constraints (hard)

1. **Touch only these three files**: `backend/apps/social/views.py`, `backend/apps/social/urls.py`, `backend/apps/social/tests/test_reaction.py`.
2. **No model changes, no migrations, no new dependencies.**
3. **Match existing code style**: same docstring tone as `FollowersListView`, same exception type, same response shape `{results, page, page_size, has_more, total}`.
4. **Visibility gate mirrors POST in `ReactionView`** — important for security parity.
5. **No avatar fields, no extra reaction metadata in the response** — just `UserMiniSerializer` shape (`{user_id, display_name, avatar_url}`).

## CRITICAL: Autonomous test-loop requirement

Same as Plan 001 v2:

You **MUST** run pytest and verify ALL tests pass before signaling DONE. If any test fails:
1. Read the failure carefully.
2. Decide: code bug or test issue?
3. Fix the appropriate side. Don't rewrite the spec.
4. Run pytest again. Repeat until green.
5. **Do NOT signal DONE on a red bar.**

If 3 fix iterations don't get to green and you can't diagnose without changing the plan, signal `===CODEX-TASK-002-BLOCKED===` with reason and stop.

**Before signaling DONE, you must also run flake8 on the new lines and confirm zero new violations**. The plan from v1 had a W503 nit on multi-line `or` in tests — avoid that pattern in this task; use single-line assertions where possible.

## Acceptance

```bash
cd backend && python3 -m pytest apps/social/tests/test_reaction.py -v 2>&1 | tail -30
```

Expected: previous test count + 4 (or +5 if pagination test added). All green.

```bash
cd backend && python3 -m flake8 apps/social/views.py apps/social/urls.py apps/social/tests/test_reaction.py
```

Expected: 0 NEW violations on lines you added. Pre-existing violations may remain.

## Output protocol

Same as v2 — when complete, output exactly:
```
===CODEX-TASK-002-DONE===
```

If blocked:
```
===CODEX-TASK-002-BLOCKED=== <one-line reason>
```

## Permission scope

Read/Edit only the 3 files listed. Read `apps/social/models.py` (for FK related_name verification — read-only) and `apps/recommendation/models.py` (Project import path). Run pytest + flake8.

Do NOT:
- Modify model files, migrations, or settings.py
- Run `git commit` / git mutations
- Install packages
- Touch frontend / docs / research/
