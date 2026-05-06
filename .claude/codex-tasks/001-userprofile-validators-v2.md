# Codex Task 001 v2 — UserProfile self-update validators (display_name + bio)

## Why this is v2

Plan v1 missed an important DRF default: `CharField` defaults to `trim_whitespace=True, allow_blank=False`, which causes DRF to **strip the value and reject empty strings BEFORE** the custom `validate_<field>` method runs. The whitespace-only branch in `validate_display_name` was unreachable, and the test asserting our custom error message failed.

v2 fixes the spec and adds an explicit autonomous-test-loop requirement.

## What to do

Add **two new fields** + **two `validate_<field>` methods** to `UserProfileSelfUpdateSerializer` in `backend/apps/accounts/serializers.py` and **4 corresponding tests** in `backend/apps/accounts/tests/test_phase13_userprofile.py`.

The serializer currently has `validate_mbti` and `validate_external_links` but **no validators** for `display_name` or `bio`. Mirror the existing pattern.

## Constraints (hard)

1. **Touch only these two files**: `backend/apps/accounts/serializers.py` and `backend/apps/accounts/tests/test_phase13_userprofile.py`. Do not modify any other file. Do not add migrations.
2. **No new dependencies.**
3. **Match existing code style**: same imports, same exception type (`serializers.ValidationError`), same docstring tone as `validate_mbti`.
4. **Backwards compatible**: the editable fields list `['display_name', 'bio', 'mbti', 'external_links']` stays the same.
5. **Test file is `tests/test_phase13_userprofile.py`** (already exists, contains `TestUserProfileSelfUpdateView`). Append new tests inside that class. Do not create a new test class.

## NEW IN v2 — Required field declarations

DRF `CharField` defaults silently strip whitespace and reject empty strings before our custom `validate_<field>` methods run. To make our validator's whitespace-only branch reachable, **declare the fields explicitly with overrides**:

Inside `class UserProfileSelfUpdateSerializer(serializers.ModelSerializer):`, ABOVE the `class Meta:` block, add:

```python
# Override DRF CharField defaults so our validate_<field> methods see the raw
# user-supplied string (DRF would otherwise strip whitespace + reject empty
# strings before our validator runs, making the whitespace-only branch dead
# code).
display_name = serializers.CharField(
    trim_whitespace=False, allow_blank=True, required=False, max_length=30,
)
bio = serializers.CharField(
    trim_whitespace=False, allow_blank=True, required=False, max_length=500,
)
```

Notes:
- `trim_whitespace=False` — preserves user input as-is so our validator decides what to do.
- `allow_blank=True` — empty string `''` is acceptable input (we treat it as "clear the field" for bio; for display_name we reject in validator).
- `required=False` — PATCH semantics; the field is optional in any given request.
- `max_length=30` and `max_length=500` are explicit upper bounds matching the model. They act as a backstop in case the validator's length check has a bug.

## Spec — `validate_display_name`

```python
def validate_display_name(self, value):
    """display_name: 1-30 chars after .strip(); reject whitespace-only."""
    if value is None:
        return value
    stripped = value.strip()
    if len(stripped) == 0:
        raise serializers.ValidationError('display_name cannot be whitespace-only.')
    if len(stripped) > 30:
        raise serializers.ValidationError('display_name must be 30 characters or fewer.')
    return stripped
```

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

## Spec — tests to append (4 tests)

Append inside `class TestUserProfileSelfUpdateView` in `backend/apps/accounts/tests/test_phase13_userprofile.py`. Mirror style of existing tests.

**Test 1 — `test_display_name_whitespace_only_rejected`**:
- PATCH `/api/v1/users/me/` with `{'display_name': '   '}` (3 spaces) as authenticated owner.
- Expect HTTP 400.
- Response error message must contain "whitespace" (i.e. `'whitespace' in str(errors)` where errors = response.json()['display_name']).

**Test 2 — `test_display_name_too_long_rejected`**:
- PATCH with `{'display_name': 'a' * 31}` (31 chars).
- Expect HTTP 400.
- Response error contains "30 characters" OR "no more than 30 characters" (the field-level max_length error message — DRF auto-generates one when the explicit max_length kicks in BEFORE our custom validator at 31 chars; whichever message wins, the test should pass on either).

**Test 3 — `test_display_name_trimmed_on_save`**:
- PATCH with `{'display_name': '  Alice  '}` (leading/trailing spaces).
- Expect HTTP 200.
- Reload the UserProfile from DB and assert `display_name == 'Alice'` (no spaces).

**Test 4 — `test_bio_too_long_rejected`**:
- PATCH with `{'bio': 'x' * 501}`.
- Expect HTTP 400.
- Response error contains "500 characters" OR DRF's auto-message about max_length.

## CRITICAL: Autonomous test-loop requirement (NEW IN v2)

You **MUST** run pytest and verify ALL tests pass before signaling DONE. If any test fails:
1. Read the failure message carefully.
2. Decide: is the failure a code bug or a test assertion that's too tight for what we actually built?
3. If code bug: fix the code. If test bug: adjust the test (within plan spec). Never rewrite the spec.
4. Run pytest again. Repeat until green.
5. **DO NOT signal DONE while pytest is red.** A red-bar DONE wastes the orchestrator's review time and erodes trust in the agent.

If after 3 fix iterations the tests still fail and you cannot diagnose the cause without changing the plan, signal `===CODEX-TASK-001-V2-BLOCKED===` with a one-line reason and stop.

## Acceptance

After your changes, this command must pass — and you must run it yourself before signaling DONE:

```bash
cd backend && python3 -m pytest apps/accounts/tests/test_phase13_userprofile.py -v 2>&1 | tail -30
```

Expected: previous test count + 4 (i.e. 22 + 4 = 26). All green.

Lint check:
```bash
cd backend && python3 -m flake8 apps/accounts/serializers.py apps/accounts/tests/test_phase13_userprofile.py
```

The repo has pre-existing flake8 violations in serializers.py from before this task — those are not your responsibility. Your **new** lines must not introduce additional violations. If your new lines clean up some lines you happened to touch, that's fine, but don't go on a flake8 cleanup spree of pre-existing code.

## Output protocol

Before signaling DONE, you MUST have:
- ✅ Run pytest and seen all 26 tests green
- ✅ Run flake8 and confirmed your new lines have 0 violations

Then your last visible output line should be exactly:

```
===CODEX-TASK-001-V2-DONE===
```

Then idle. The orchestrator will pick up via `cmux read-screen`.

If blocked after 3 fix iterations, output exactly:
```
===CODEX-TASK-001-V2-BLOCKED=== <one-line reason>
```

## Permission scope

You may freely Read/Edit the two files listed above and run pytest + flake8. Do NOT:
- Modify any other source file
- Create migrations
- Run `git commit` or any git mutation
- Install packages
- Modify `.env` or settings.py
