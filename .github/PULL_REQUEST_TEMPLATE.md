## Summary

<!-- 1-3 bullets: what changed and why. Link to spec / Investigation if applicable. -->

-

## Spec / task ref

<!-- Link to the relevant `.claude/Task.md` entry, or N/A if none applies.
     (The old docs/specs/*.md folder was absorbed into .claude/Task.md 2026-05-24.) -->

- task: <!-- e.g. `.claude/Task.md` #### BACK-RECOMMEND-4 (from ## Now / ## Next) -->

## Test plan

- [ ] `cd backend && pytest -x` green
- [ ] `cd frontend && npm run lint && npm run build` green
- [ ] `cd backend && python manage.py makemigrations --check --dry-run` (no pending)
- [ ] Manual smoke test in browser (if UI-affecting)
- [ ] Migration applied to local dev DB (if schema change)

## Review status

<!-- code-review + security-manager agents run pre-push (no slash command). -->

- [ ] code-review + security PASS (clean)
- [ ] PASS with N MINOR (non-blocking; see `.claude/reviews/<sha>.md`)
- [ ] not yet reviewed

## Risk zone

<!-- Check any that apply. Triggers extra reviewer/security pass per CLAUDE.md hybrid policy. -->

- [ ] Auth / token / session handling
- [ ] New external API integration (Gemini, Google OAuth, etc.)
- [ ] Migration with data backfill
- [ ] Cross-cutting refactor (≥4 unrelated apps)
- [ ] None of the above (default)

## Notes

<!-- Optional: edge cases, deployment concerns, follow-up work. -->
