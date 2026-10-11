## Summary

<!-- 1-3 bullets: what changed and why. Link to spec / Investigation if applicable. -->

-

## Spec / task ref

<!-- `Closes #N` for every issue this PR resolves (closes it on merge). Link a
     design record under docs/decisions/ when one exists. N/A if none. -->

- Closes #
- design: <!-- docs/decisions/<file>.md §N, or N/A -->

## Test plan

- [ ] `cd backend && pytest -x` green
- [ ] `cd frontend && npm run lint && npm run build` green
- [ ] `cd backend && python manage.py makemigrations --check --dry-run` (no pending)
- [ ] Manual smoke test in browser (if UI-affecting)
- [ ] Migration applied to local dev DB (if schema change)

## Review status

<!-- Claude: code-review + security-manager run inside the feature workflow
     before the commit; app-test is the separate pre-push gate. Codex / humans:
     state which review ran. -->

- [ ] code-review + security PASS (clean)
- [ ] PASS with N MINOR (non-blocking; list them under Notes)
- [ ] app-test PASS / skipped (docs-only or 4-gate pass) — state which
- [ ] not yet reviewed

## Risk zone

<!-- Check any that apply. Triggers an extra code-review + security-manager pass. -->

- [ ] Auth / token / session handling
- [ ] New external API integration (Gemini, Google OAuth, etc.)
- [ ] Migration with data backfill
- [ ] Cross-cutting refactor (≥4 unrelated apps)
- [ ] None of the above (default)

## Notes

<!-- Optional: edge cases, deployment concerns, follow-up work. -->
