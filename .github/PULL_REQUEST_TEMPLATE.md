## Summary

<!-- 1-3 bullets: what changed and why. Link to spec / Investigation if applicable. -->

-

## Spec ref

<!-- Link to docs/specs/<file>.md §<section>, or N/A if no spec applies. -->

- spec: <!-- e.g. docs/specs/phase16-recommendation-expansion.md §2 -->
- task id: <!-- e.g. REC1, BOARD3, etc. (from .claude/Task.md Development Roadmap) -->

## Test plan

- [ ] `cd backend && pytest -x` green
- [ ] `cd frontend && npm run lint && npm run build` green
- [ ] `cd backend && python manage.py makemigrations --check --dry-run` (no pending)
- [ ] Manual smoke test in browser (if UI-affecting)
- [ ] Migration applied to local dev DB (if schema change)

## /review status

<!-- Admin runs /review in review terminal. Check the box that matches. -->

- [ ] REVIEW-PASSED (clean)
- [ ] REVIEW-PASSED with N MINOR (non-blocking; see `.claude/reviews/<sha>.md`)
- [ ] /review not yet run

## Risk zone

<!-- Check any that apply. Triggers extra reviewer/security pass per CLAUDE.md hybrid policy. -->

- [ ] Auth / token / session handling
- [ ] New external API integration (Gemini, Google OAuth, etc.)
- [ ] Migration with data backfill
- [ ] Cross-cutting refactor (≥4 unrelated apps)
- [ ] None of the above (default)

## Notes

<!-- Optional: edge cases, deployment concerns, follow-up work. -->
