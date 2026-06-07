"""
test_conversation_history.py — BACK-LLM-2: LLM chat history persistence on Project.

Coverage:
  (a) owner PATCHes conversation_history → 200, persisted, returned on detail GET
  (b) oversized blob (>64 KB) → 400
  (c) too many messages → 400; too many history items → 400
  (d) a different user cannot PATCH (404 — owner-filter folded into lock)
  (e) conversation_history ABSENT from project list response (no bloat)
"""
import json
import pytest
from apps.recommendation.models import Project
from apps.recommendation.serializers import (
    _MAX_BLOB_BYTES,
    _MAX_CHAT_MESSAGES,
    _MAX_HISTORY_LEN,
    _MAX_TEXT_LEN,
)


# ── TestConversationHistoryPersistence ────────────────────────────────────────

@pytest.mark.django_db
class TestConversationHistoryPersistence:
    """(a) owner PATCH + GET round-trip."""

    def test_owner_patch_persists_and_returns_on_detail(self, auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='LLMBoard')
        payload = {
            'messages': [
                {'role': 'user', 'text': 'minimalist concrete'},
                {'role': 'model', 'text': 'Got it — filtering for raw concrete aesthetics.'},
            ],
            'history': [
                {'role': 'user', 'text': 'show me more brutalist'},
            ],
        }
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': payload},
            format='json',
        )
        assert resp.status_code == 200, resp.json()
        # Returned in PATCH response
        data = resp.json()
        assert 'conversation_history' in data
        assert data['conversation_history'] == payload

        # Persisted to DB
        p.refresh_from_db()
        assert p.conversation_history == payload

        # Returned on subsequent GET (detail)
        get_resp = auth_client.get(f'/api/v1/projects/{p.project_id}/')
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert 'conversation_history' in get_data
        assert get_data['conversation_history'] == payload

    def test_patch_empty_dict_is_valid(self, auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='Empty')
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {}},
            format='json',
        )
        assert resp.status_code == 200
        p.refresh_from_db()
        assert p.conversation_history == {}

    def test_patch_extra_keys_tolerated(self, auth_client, user_profile):
        """Frontend owns the blob shape — extra keys must not be rejected."""
        p = Project.objects.create(user=user_profile, name='ExtraKeys')
        payload = {
            'messages': [],
            'history': [],
            'mode': 'conversational',
            'latestQuery': 'glass + steel',
        }
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': payload},
            format='json',
        )
        assert resp.status_code == 200


# ── TestConversationHistoryValidation ─────────────────────────────────────────

@pytest.mark.django_db
class TestConversationHistoryValidation:
    """(b)(c) size + count rejection → 400."""

    def test_oversized_blob_rejected(self, auth_client, user_profile):
        """(b) blob > 64 KB → 400."""
        p = Project.objects.create(user=user_profile, name='OversizeTest')
        # Build a blob guaranteed to exceed _MAX_BLOB_BYTES
        big_text = 'x' * (_MAX_BLOB_BYTES + 1)
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'payload': big_text}},
            format='json',
        )
        assert resp.status_code == 400, resp.json()
        err = json.dumps(resp.json()).lower()
        assert 'large' in err or 'bytes' in err or 'conversation_history' in err

    def test_korean_text_within_utf8_limit_accepted(self, auth_client, user_profile):
        """FIX 2: Korean chars must not be ascii-inflated when measuring blob size.

        '가' is 3 bytes in UTF-8 but 6 bytes as \\uXXXX (ensure_ascii=True).
        15 000 '가' chars = ~45 KB UTF-8 (under 64 KB cap).
        Under the old ensure_ascii=True measurement, json.dumps would produce
        ~90 KB of \\uAC00 escapes, falsely tripping the 400 gate.
        After FIX 2 the UTF-8 byte count is used and this must return 200.
        The key is a top-level extra key so the messages/history per-item
        _MAX_TEXT_LEN guard is not triggered.
        """
        p = Project.objects.create(user=user_profile, name='KoreanBlob')
        korean_text = '가' * 15_000  # ~45 KB UTF-8, ~90 KB ascii-escaped
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'note': korean_text}},
            format='json',
        )
        assert resp.status_code == 200, (
            'Korean text within 64 KB UTF-8 limit must not be rejected '
            '(was falsely failing due to ensure_ascii=True inflation)'
        )

    def test_too_many_messages_rejected(self, auth_client, user_profile):
        """(c) messages list exceeds _MAX_CHAT_MESSAGES → 400."""
        p = Project.objects.create(user=user_profile, name='TooManyMsg')
        messages = [{'role': 'user', 'text': f'msg{i}'} for i in range(_MAX_CHAT_MESSAGES + 1)]
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'messages': messages}},
            format='json',
        )
        assert resp.status_code == 400, resp.json()
        err = json.dumps(resp.json()).lower()
        assert 'messages' in err or 'long' in err

    def test_too_many_history_items_rejected(self, auth_client, user_profile):
        """(c) history list exceeds _MAX_HISTORY_LEN → 400."""
        p = Project.objects.create(user=user_profile, name='TooManyHist')
        history = [{'role': 'user', 'text': f'turn{i}'} for i in range(_MAX_HISTORY_LEN + 1)]
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'history': history}},
            format='json',
        )
        assert resp.status_code == 400, resp.json()
        err = json.dumps(resp.json()).lower()
        assert 'history' in err or 'long' in err

    def test_message_text_too_long_rejected(self, auth_client, user_profile):
        """Individual message.text > _MAX_TEXT_LEN → 400."""
        p = Project.objects.create(user=user_profile, name='LongText')
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'messages': [{'role': 'user', 'text': 'a' * (_MAX_TEXT_LEN + 1)}]}},
            format='json',
        )
        assert resp.status_code == 400, resp.json()

    def test_history_text_too_long_rejected(self, auth_client, user_profile):
        """Individual history.text > _MAX_TEXT_LEN → 400."""
        p = Project.objects.create(user=user_profile, name='LongHistText')
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'history': [{'role': 'user', 'text': 'b' * (_MAX_TEXT_LEN + 1)}]}},
            format='json',
        )
        assert resp.status_code == 400, resp.json()

    def test_non_dict_rejected(self, auth_client, user_profile):
        """conversation_history must be a dict — list top-level → 400."""
        p = Project.objects.create(user=user_profile, name='NonDict')
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': [{'role': 'user', 'text': 'hi'}]},
            format='json',
        )
        assert resp.status_code == 400, resp.json()

    def test_messages_not_list_rejected(self, auth_client, user_profile):
        """conversation_history['messages'] must be a list."""
        p = Project.objects.create(user=user_profile, name='MsgNotList')
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'messages': 'not a list'}},
            format='json',
        )
        assert resp.status_code == 400, resp.json()

    def test_history_not_list_rejected(self, auth_client, user_profile):
        """conversation_history['history'] must be a list."""
        p = Project.objects.create(user=user_profile, name='HistNotList')
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'history': 'not a list'}},
            format='json',
        )
        assert resp.status_code == 400, resp.json()

    def test_exactly_at_limits_accepted(self, auth_client, user_profile):
        """Exactly at the caps should pass."""
        p = Project.objects.create(user=user_profile, name='AtLimit')
        messages = [{'role': 'user', 'text': 'ok'} for _ in range(_MAX_CHAT_MESSAGES)]
        history = [{'role': 'user', 'text': 'ok'} for _ in range(_MAX_HISTORY_LEN)]
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'messages': messages, 'history': history}},
            format='json',
        )
        assert resp.status_code == 200, resp.json()


# ── TestConversationHistoryOwnership ─────────────────────────────────────────

@pytest.mark.django_db
class TestConversationHistoryOwnership:
    """(d) non-owner PATCH returns 404 (owner-filter TOCTOU fix — same as name/visibility)."""

    def test_other_user_cannot_patch_conversation_history(self, other_auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='NotMine')
        resp = other_auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'messages': [{'role': 'user', 'text': 'hacked'}]}},
            format='json',
        )
        assert resp.status_code == 404

        # DB untouched
        p.refresh_from_db()
        assert p.conversation_history == {}

    def test_unauthenticated_patch_returns_401(self, api_client, user_profile):
        p = Project.objects.create(user=user_profile, name='Anon')
        resp = api_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'conversation_history': {'messages': []}},
            format='json',
        )
        assert resp.status_code == 401


# ── TestConversationHistoryPrivacy ────────────────────────────────────────────

@pytest.mark.django_db
class TestConversationHistoryPrivacy:
    """FIX 1: non-owner GET on public board must NOT receive conversation_history."""

    def test_non_owner_gets_no_conversation_history(self, auth_client, other_auth_client, user_profile):
        """Non-owner GET on a PUBLIC board → 200 but no conversation_history."""
        hist = {'messages': [{'role': 'user', 'text': 'private thought'}]}
        p = Project.objects.create(
            user=user_profile,
            name='PublicBoard',
            visibility='public',
            conversation_history=hist,
        )
        resp = other_auth_client.get(f'/api/v1/projects/{p.project_id}/')
        assert resp.status_code == 200, resp.json()
        assert 'conversation_history' not in resp.json(), (
            'non-owner must NOT receive conversation_history on public board GET'
        )

    def test_owner_gets_conversation_history(self, auth_client, user_profile):
        """Owner GET on their own board → conversation_history present."""
        hist = {'messages': [{'role': 'user', 'text': 'my private thought'}]}
        p = Project.objects.create(
            user=user_profile,
            name='OwnerBoard',
            visibility='public',
            conversation_history=hist,
        )
        resp = auth_client.get(f'/api/v1/projects/{p.project_id}/')
        assert resp.status_code == 200, resp.json()
        assert 'conversation_history' in resp.json(), (
            'owner must receive conversation_history on their own board GET'
        )
        assert resp.json()['conversation_history'] == hist

    def test_anonymous_gets_no_conversation_history(self, api_client, user_profile):
        """Anonymous GET on a public board → 200 but no conversation_history."""
        hist = {'messages': [{'role': 'user', 'text': 'secret'}]}
        p = Project.objects.create(
            user=user_profile,
            name='AnonBoard',
            visibility='public',
            conversation_history=hist,
        )
        resp = api_client.get(f'/api/v1/projects/{p.project_id}/')
        assert resp.status_code == 200, resp.json()
        assert 'conversation_history' not in resp.json(), (
            'anonymous caller must NOT receive conversation_history'
        )


# ── TestConversationHistoryListAbsent ─────────────────────────────────────────

@pytest.mark.django_db
class TestConversationHistoryListAbsent:
    """(e) conversation_history must NOT appear in list responses."""

    def test_absent_from_projects_list(self, auth_client, user_profile):
        """GET /api/v1/projects/ — no conversation_history in any item."""
        Project.objects.create(
            user=user_profile, name='L1',
            conversation_history={'messages': [{'role': 'user', 'text': 'test'}]},
        )
        resp = auth_client.get('/api/v1/projects/')
        assert resp.status_code == 200
        for item in resp.json()['results']:
            assert 'conversation_history' not in item, (
                'conversation_history must be excluded from project list responses'
            )

    def test_absent_from_user_projects_list(self, api_client, user_profile):
        """GET /api/v1/users/{id}/projects/ — no conversation_history in any item."""
        Project.objects.create(
            user=user_profile, name='L2', visibility='public',
            conversation_history={'history': [{'role': 'user', 'text': 'test'}]},
        )
        uid = user_profile.user.id
        resp = api_client.get(f'/api/v1/users/{uid}/projects/')
        assert resp.status_code == 200
        for item in resp.json()['results']:
            assert 'conversation_history' not in item, (
                'conversation_history must be excluded from user project list responses'
            )

    def test_present_on_detail_get(self, auth_client, user_profile):
        """Sanity: conversation_history IS present on the detail endpoint."""
        hist = {'messages': [{'role': 'user', 'text': 'detail check'}]}
        p = Project.objects.create(
            user=user_profile, name='DetailCheck', conversation_history=hist,
        )
        resp = auth_client.get(f'/api/v1/projects/{p.project_id}/')
        assert resp.status_code == 200
        assert 'conversation_history' in resp.json()
        assert resp.json()['conversation_history'] == hist

    def test_absent_from_post_create_response(self, auth_client):
        """POST /api/v1/projects/ response includes conversation_history as empty dict."""
        # conversation_history IS in ProjectSerializer.fields (read-only), so it
        # should be present with default {} on POST response — not absent.
        # This confirms it's readable (not silently dropped) even on create path.
        resp = auth_client.post(
            '/api/v1/projects/',
            {'name': 'CreateConvTest', 'filters': {}},
            format='json',
        )
        assert resp.status_code == 201
        data = resp.json()
        # Must be present as empty dict (default)
        assert 'conversation_history' in data
        assert data['conversation_history'] == {}
