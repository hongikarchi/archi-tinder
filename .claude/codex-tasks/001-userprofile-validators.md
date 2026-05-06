# Codex Task 001 — UserProfile self-update validators (display_name + bio)

## Why this task

This is the **first empirical test** of using Codex as a back-maker substitute (per advisor recommendation in our architecture deliberation). Goal: see if Codex can produce reviewer-PASS code on a small mechanical Python task in this codebase.

## What to do

Add **two new `validate_<field>` methods** to `UserProfileSelfUpdateSerializer` in `backend/apps/accounts/serializers.py` and **3-4 corresponding tests** in `backend/apps/accounts/tests/test_phase13_userprofile.py`.

The serializer currently has `validate_mbti` and `validate_external_links` but **no validators** for `display_name` or `bio` — they accept any string up to model `max_length`. Codex must mirror the existing pattern.

## Constraints (hard)

1. **Touch only these two files**: `backend/apps/accounts/serializers.py` and `backend/apps/accounts/tests/test_phase13_userprofile.py`. Do not modify any other file. Do not add migrations.
2. **No new dependencies.**
3. **Match existing code style**: same imports, same exception type (`serializers.ValidationError`), same docstring tone as `validate_mbti`.
4. **Backwards compatible**: empty `display_name` is currently allowed by the model layer; the serializer's editable fields list includes `display_name` — keep this writable. `bio` is also already model-level optional.
5. **Test file is `tests/test_phase13_userprofile.py`** (already exists, contains `TestUserProfileSelfUpdateView`). Append new tests inside that class. Do not create a new test class.

## Spec — `validate_display_name`

```python
def validate_display_name(self, value):
    """display_name: 1-30 chars after .strip(); reject whitespace-only."""
    # Accept empty value (means "leave unchanged" — clients omit the field
    # entirely if they don't want to change it; DRF treats explicit None
    # the same way for nullable=False CharField). But if a client SENDS the
    # field as a string, we validate the trimmed length.
    if value is None:
        return value
    stripped = value.strip()
    if len(stripped) == 0:
        raise serializers.ValidationError('display_name cannot be whitespace-only.')
    if len(stripped) > 30:
        raise serializers.ValidationError('display_name must be 30 characters or fewer.')
    return stripped
```

Logic notes:
- Whitespace-only ("   ") is rejected (clear UX failure mode otherwise).
- Lengths 1-30 (after strip) accepted.
- Trim happens server-side so the database never stores leading/trailing whitespace.
- Emojis count as their full UTF-8 char count (no special-case).

## Spec — `validate_bio`

```python
def validate_bio(self, value):
    """bio: max 500 chars; whitespace-only → empty string (cleared)."""
    if value is None:
        return value
    stripped = value.strip()
    if len(stripped) > 500:
        raise serializers.ValidationError('bio must be 500 characters or fewer.')
    # Whitespace-only is treated as "clear the bio" rather than rejected,
    # so users can wipe their bio by submitting a space (or just empty).
    return stripped
```

Logic notes:
- max 500 chars (matches model `max_length=500`).
- Whitespace-only → empty string (different from display_name; bio is allowed empty).
- No length-floor.

## Spec — tests to append (4 tests)

Append inside `class TestUserProfileSelfUpdateView` in `backend/apps/accounts/tests/test_phase13_userprofile.py`. Mirror style of existing tests (e.g. `test_mbti_invalid_length`).

**Test 1 — `test_display_name_whitespace_only_rejected`**:
- PATCH `/api/v1/users/me/` with `{'display_name': '   '}` (3 spaces) as authenticated owner.
- Expect HTTP 400.
- Response should contain field-level error mentioning "whitespace" or similar.

**Test 2 — `test_display_name_too_long_rejected`**:
- PATCH `/api/v1/users/me/` with `{'display_name': 'a' * 31}` (31 chars).
- Expect HTTP 400.
- Response error mentions "30 characters".

**Test 3 — `test_display_name_trimmed_on_save`**:
- PATCH with `{'display_name': '  Alice  '}` (leading/trailing spaces).
- Expect HTTP 200.
- Reload the UserProfile from DB and assert `display_name == 'Alice'` (no spaces).

**Test 4 — `test_bio_too_long_rejected`**:
- PATCH with `{'bio': 'x' * 501}`.
- Expect HTTP 400.
- Error mentions "500 characters".

(No need to test bio whitespace-only acceptance — implicit in 500-cap pass case if you want to add a 5th test, do so, but 4 is the floor.)

## Acceptance

After your changes, this command must pass with new tests counted:

```bash
cd backend && python3 -m pytest apps/accounts/tests/test_phase13_userprofile.py -v
```

Expected: previous test count + 4 (or +5 if you added bio-whitespace test). All passing.

Lint check:
```bash
cd backend && flake8 apps/accounts/serializers.py apps/accounts/tests/test_phase13_userprofile.py
```

Expected: 0 errors.

## Output protocol

When you finish, your last visible output line in this terminal should be exactly:

```
===CODEX-TASK-001-DONE===
```

Then idle (don't start another task). The orchestrator (main pane) will read your output via `cmux read-screen`, run reviewer + security agents, and report verdict.

If you encounter a blocker (test fixture missing, unclear constraint, etc.), output exactly:

```
===CODEX-TASK-001-BLOCKED=== <one-line reason>
```

and stop.

## Permission scope

You may freely Read/Edit the two files listed above and run pytest + flake8. Do NOT:
- Modify any other source file
- Create migrations
- Run `git commit` or any git mutation
- Install packages
- Modify `.env` or settings.py
