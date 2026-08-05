"""test_works_upload.py — FULL-WORKS-1 upload endpoint tests.

15 original tests covering:
  1. test_presign_disabled_503
  2. test_presign_file_too_large
  3. test_presign_invalid_content_type
  4. test_presign_success
  5. test_presign_content_type_in_params_boto3_call (regression test — presigned PUT)
  6. test_presign_too_many_files
  7. test_finalize_no_copyright
  8. test_finalize_foreign_key_prefix
  9. test_finalize_key_not_in_r2
  10. test_finalize_success
  11. test_finalize_unauthenticated
  12. test_finalize_too_many_r2_keys
  13. test_finalize_invalid_project_year
  14. test_finalize_non_str_r2_key
  15. test_finalize_size_exceeds_cap

Plus BACK-WORKS-1 / BACK-WORKS-2 follow-up tests (TestList,
TestFinalizeParallelHead) covering GET /api/v1/works/ pagination + response
slimming, and deterministic ordering of the parallelized per-key R2 HEAD
loop in FinalizeView.post.

R2-verified (2026-07-17): Cloudflare R2 does not implement presigned POST
(501 NotImplemented) — the presign flow migrated to presigned PUT
(s3.generate_presigned_url('put_object', ...)). See apps/works/storage.py.

Fixtures mirror accounts/tests/test_avatar_upload.py.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile
from apps.works.views import MAX_WORK_IMAGES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user_and_profile(db):
    """Create a Django User + UserProfile."""
    from django.contrib.auth.models import User
    user = User.objects.create_user(
        username='workstest', email='works@test.com', password='pass1234',
    )
    profile = UserProfile.objects.create(user=user, display_name='Works User')
    return user, profile


@pytest.fixture
def auth_client(user_and_profile):
    """APIClient authenticated as the test user."""
    user, _profile = user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def anon_client():
    return APIClient()


# ---------------------------------------------------------------------------
# Presign tests
# ---------------------------------------------------------------------------

class TestPresign:

    @pytest.mark.django_db
    def test_presign_disabled_503(self, auth_client):
        """WORKS_R2_ENABLED=False -> 503."""
        with override_settings(WORKS_R2_ENABLED=False):
            resp = auth_client.post(
                '/api/v1/works/presign/',
                {'files': [{'file_size': 100, 'content_type': 'image/webp'}]},
                format='json',
            )
        assert resp.status_code == 503
        assert 'detail' in resp.json()

    @pytest.mark.django_db
    def test_presign_file_too_large(self, auth_client):
        """file_size > 10 MB -> 400."""
        with override_settings(WORKS_R2_ENABLED=True):
            resp = auth_client.post(
                '/api/v1/works/presign/',
                {'files': [{'file_size': 11 * 1024 * 1024, 'content_type': 'image/webp'}]},
                format='json',
            )
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'File too large'

    @pytest.mark.django_db
    def test_presign_invalid_content_type(self, auth_client):
        """content_type not starting with 'image/' -> 400."""
        with override_settings(WORKS_R2_ENABLED=True):
            resp = auth_client.post(
                '/api/v1/works/presign/',
                {'files': [{'file_size': 1024, 'content_type': 'application/pdf'}]},
                format='json',
            )
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'Only image files are accepted'

    @pytest.mark.django_db
    def test_presign_success(self, auth_client, user_and_profile):
        """Valid request with boto3 mocked -> 200 with presign_results."""
        _user, profile = user_and_profile
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = 'https://r2.example.com/upload?sig=abc'

        with override_settings(
            WORKS_R2_ENABLED=True,
            R2_WORKS_BUCKET='works-bucket',
            R2_ENDPOINT_URL='https://r2.example.com',
            R2_ACCESS_KEY_ID='key-id',
            R2_SECRET_ACCESS_KEY='secret',
        ):
            # boto3 is lazily imported inside generate_presigned_put;
            # patch at the module level so the lazy import picks up the mock.
            with patch('boto3.client', return_value=mock_s3):
                resp = auth_client.post(
                    '/api/v1/works/presign/',
                    {'files': [
                        {'file_size': 1024, 'content_type': 'image/webp'},
                        {'file_size': 512, 'content_type': 'image/jpeg'},
                    ]},
                    format='json',
                )

        assert resp.status_code == 200
        data = resp.json()
        assert 'presign_results' in data
        results = data['presign_results']
        assert len(results) == 2
        assert results[0]['key'].endswith('_cover.webp')
        assert results[1]['key'].endswith('_gallery_1.webp')
        assert results[0]['url'] == 'https://r2.example.com/upload?sig=abc'
        assert 'fields' not in results[0]

    @pytest.mark.django_db
    def test_presign_content_type_in_params_boto3_call(self, auth_client, user_and_profile):
        """Regression test: generate_presigned_put must call boto3's
        generate_presigned_url('put_object', ...) with Params containing
        ContentType == the requested content type, and the response items
        must contain 'url' + 'key' and NO 'fields' (R2 does not implement
        presigned POST — verified 2026-07-17, 501 NotImplemented)."""
        _user, profile = user_and_profile
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = 'https://r2.example.com/upload?sig=abc'

        with override_settings(
            WORKS_R2_ENABLED=True,
            R2_WORKS_BUCKET='works-bucket',
            R2_ENDPOINT_URL='https://r2.example.com',
            R2_ACCESS_KEY_ID='key-id',
            R2_SECRET_ACCESS_KEY='secret',
        ):
            with patch('boto3.client', return_value=mock_s3):
                resp = auth_client.post(
                    '/api/v1/works/presign/',
                    {'files': [{'file_size': 1024, 'content_type': 'image/webp'}]},
                    format='json',
                )

        assert resp.status_code == 200
        assert mock_s3.generate_presigned_url.called
        call_args = mock_s3.generate_presigned_url.call_args
        method = call_args.args[0] if call_args.args else call_args.kwargs.get('ClientMethod')
        assert method == 'put_object'
        params = call_args.kwargs.get('Params', {})
        assert params.get('ContentType') == 'image/webp'
        assert params.get('Bucket') == 'works-bucket'

        data = resp.json()
        results = data['presign_results']
        assert set(results[0].keys()) == {'key', 'url'}
        assert 'fields' not in results[0]

    @pytest.mark.django_db
    def test_presign_too_many_files(self, auth_client):
        """More than MAX_WORK_IMAGES files -> 400."""
        files = [
            {'file_size': 1024, 'content_type': 'image/webp'}
            for _ in range(MAX_WORK_IMAGES + 1)
        ]
        with override_settings(WORKS_R2_ENABLED=True):
            resp = auth_client.post(
                '/api/v1/works/presign/',
                {'files': files},
                format='json',
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Finalize tests
# ---------------------------------------------------------------------------

class TestFinalize:

    @pytest.mark.django_db
    def test_finalize_no_copyright(self, auth_client, user_and_profile):
        """is_copyright_confirmed=False -> 400."""
        _user, profile = user_and_profile
        resp = auth_client.post(
            '/api/v1/works/',
            {
                'title': 'My Building',
                'program': 'residential',
                'r2_keys': [f'works/{profile.id}/abc_cover.webp'],
                'is_copyright_confirmed': False,
            },
            format='json',
        )
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'Copyright confirmation required.'

    @pytest.mark.django_db
    def test_finalize_foreign_key_prefix(self, auth_client, user_and_profile):
        """Key with another user's prefix -> 403."""
        resp = auth_client.post(
            '/api/v1/works/',
            {
                'title': 'My Building',
                'program': 'residential',
                'r2_keys': ['works/99999/abc_cover.webp'],
                'is_copyright_confirmed': True,
            },
            format='json',
        )
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_finalize_key_not_in_r2(self, auth_client, user_and_profile):
        """WORKS_R2_ENABLED=True, head_object returns 404 -> 400."""
        _user, profile = user_and_profile
        key = f'works/{profile.id}/abc_cover.webp'

        # Build a ClientError-like exception without importing botocore directly
        # (botocore is a boto3 dependency; mock it at the storage module level).
        from botocore.exceptions import ClientError
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(
            {'Error': {'Code': '404', 'Message': 'Not Found'}},
            'HeadObject',
        )

        with override_settings(
            WORKS_R2_ENABLED=True,
            R2_WORKS_BUCKET='works-bucket',
            R2_ENDPOINT_URL='https://r2.example.com',
            R2_ACCESS_KEY_ID='key-id',
            R2_SECRET_ACCESS_KEY='secret',
        ):
            # boto3 is lazily imported inside verify_key_exists; patch at top level.
            with patch('boto3.client', return_value=mock_s3):
                resp = auth_client.post(
                    '/api/v1/works/',
                    {
                        'title': 'My Building',
                        'program': 'residential',
                        'r2_keys': [key],
                        'is_copyright_confirmed': True,
                    },
                    format='json',
                )

        assert resp.status_code == 400
        assert 'Upload not found in storage' in resp.json()['detail']

    @pytest.mark.django_db
    def test_finalize_size_exceeds_cap(self, auth_client, user_and_profile):
        """WORKS_R2_ENABLED=True, head_object reports ContentLength > 10MB -> 400.

        A presigned PUT cannot enforce a size cap client-side (unlike the old
        POST policy's content-length-range condition), so finalize must reject
        oversized objects server-side using the head_object ContentLength."""
        _user, profile = user_and_profile
        key = f'works/{profile.id}/abc_cover.webp'

        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {'ContentLength': 11 * 1024 * 1024}

        with override_settings(
            WORKS_R2_ENABLED=True,
            R2_WORKS_BUCKET='works-bucket',
            R2_ENDPOINT_URL='https://r2.example.com',
            R2_ACCESS_KEY_ID='key-id',
            R2_SECRET_ACCESS_KEY='secret',
        ):
            with patch('boto3.client', return_value=mock_s3):
                resp = auth_client.post(
                    '/api/v1/works/',
                    {
                        'title': 'My Building',
                        'program': 'residential',
                        'r2_keys': [key],
                        'is_copyright_confirmed': True,
                    },
                    format='json',
                )

        assert resp.status_code == 400
        assert 'exceeds 10MB' in resp.json()['detail']

    @pytest.mark.django_db
    def test_finalize_success(self, auth_client, user_and_profile):
        """Valid finalize request -> 201 + {upload_id, status: 'processing'}."""
        _user, profile = user_and_profile
        key = f'works/{profile.id}/abc_cover.webp'

        with override_settings(WORKS_R2_ENABLED=False):
            with patch('apps.works.views.threading.Thread') as mock_thread_cls:
                mock_thread = MagicMock()
                mock_thread_cls.return_value = mock_thread

                resp = auth_client.post(
                    '/api/v1/works/',
                    {
                        'title': 'My Building',
                        'program': 'residential',
                        'location_city': 'Seoul',
                        'location_country': 'South Korea',
                        'project_year': 2022,
                        'r2_keys': [key],
                        'is_copyright_confirmed': True,
                    },
                    format='json',
                )

        assert resp.status_code == 201
        data = resp.json()
        assert 'upload_id' in data
        assert data['upload_id'].startswith('usr_')
        assert data['status'] == 'processing'
        mock_thread.start.assert_called_once()

    @pytest.mark.django_db
    def test_finalize_unauthenticated(self, anon_client):
        """Unauthenticated request -> 401."""
        resp = anon_client.post(
            '/api/v1/works/',
            {
                'title': 'My Building',
                'program': 'residential',
                'r2_keys': ['works/1/abc_cover.webp'],
                'is_copyright_confirmed': True,
            },
            format='json',
        )
        assert resp.status_code == 401

    @pytest.mark.django_db
    def test_finalize_too_many_r2_keys(self, auth_client, user_and_profile):
        """More than MAX_WORK_IMAGES r2_keys -> 400."""
        _user, profile = user_and_profile
        keys = [f'works/{profile.id}/abc{i}_cover.webp' for i in range(MAX_WORK_IMAGES + 1)]
        resp = auth_client.post(
            '/api/v1/works/',
            {
                'title': 'My Building',
                'program': 'residential',
                'r2_keys': keys,
                'is_copyright_confirmed': True,
            },
            format='json',
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_finalize_invalid_project_year(self, auth_client, user_and_profile):
        """Non-int project_year -> 400 (not an unhandled 500 at INSERT)."""
        _user, profile = user_and_profile
        resp = auth_client.post(
            '/api/v1/works/',
            {
                'title': 'My Building',
                'program': 'residential',
                'project_year': 'abc',
                'r2_keys': [f'works/{profile.id}/abc_cover.webp'],
                'is_copyright_confirmed': True,
            },
            format='json',
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_finalize_non_str_r2_key(self, auth_client, user_and_profile):
        """A non-str r2_keys element -> 400 (not an unhandled 500 at .startswith)."""
        _user, profile = user_and_profile
        resp = auth_client.post(
            '/api/v1/works/',
            {
                'title': 'My Building',
                'program': 'residential',
                'r2_keys': [12345],
                'is_copyright_confirmed': True,
            },
            format='json',
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# BACK-WORKS-2 — parallelized per-key R2 HEAD loop tests
# ---------------------------------------------------------------------------

class TestFinalizeParallelHead:
    """The per-key HEAD loop in FinalizeView.post is parallelized via
    ThreadPoolExecutor (BACK-WORKS-2). Response semantics must stay exactly
    what they were serially: missing key -> 400 naming the key, oversized
    key -> 400 naming the key, storage exception -> 500 -- and when several
    keys fail, the key REPORTED must be the first bad one in the ORIGINAL
    r2_keys order, deterministically, regardless of which thread's HEAD call
    happens to resolve first."""

    @pytest.mark.django_db
    def test_finalize_parallel_head_reports_first_bad_key_in_order(self, auth_client, user_and_profile):
        """3 keys: [ok, missing(slow), oversized(fast)]. The oversized key's
        mocked HEAD call resolves first (no sleep), but the missing key --
        earlier in r2_keys -- must be the one reported, proving the code
        walks results in list order rather than reporting whichever thread
        finishes first."""
        import time

        from botocore.exceptions import ClientError

        _user, profile = user_and_profile
        key_ok = f'works/{profile.id}/aaa_cover.webp'
        key_missing = f'works/{profile.id}/bbb_gallery_1.webp'
        key_oversized = f'works/{profile.id}/ccc_gallery_2.webp'

        def mock_head_object(Bucket, Key):
            if Key == key_ok:
                return {'ContentLength': 1024}
            if Key == key_missing:
                time.sleep(0.05)  # resolves after the (fast) oversized check
                raise ClientError(
                    {'Error': {'Code': '404', 'Message': 'Not Found'}},
                    'HeadObject',
                )
            if Key == key_oversized:
                return {'ContentLength': 11 * 1024 * 1024}
            raise AssertionError(f'unexpected key: {Key}')

        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = mock_head_object

        with override_settings(
            WORKS_R2_ENABLED=True,
            R2_WORKS_BUCKET='works-bucket',
            R2_ENDPOINT_URL='https://r2.example.com',
            R2_ACCESS_KEY_ID='key-id',
            R2_SECRET_ACCESS_KEY='secret',
        ):
            with patch('boto3.client', return_value=mock_s3):
                resp = auth_client.post(
                    '/api/v1/works/',
                    {
                        'title': 'My Building',
                        'program': 'residential',
                        'r2_keys': [key_ok, key_missing, key_oversized],
                        'is_copyright_confirmed': True,
                    },
                    format='json',
                )

        assert resp.status_code == 400
        detail = resp.json()['detail']
        assert 'Upload not found in storage' in detail
        assert key_missing in detail
        assert key_oversized not in detail

    @pytest.mark.django_db
    def test_finalize_parallel_head_storage_exception_500(self, auth_client, user_and_profile):
        """A non-404 ClientError (or any other exception) from head_object ->
        500 naming the key, same as the pre-parallelization behavior."""
        _user, profile = user_and_profile
        key = f'works/{profile.id}/abc_cover.webp'

        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = RuntimeError('boom')

        with override_settings(
            WORKS_R2_ENABLED=True,
            R2_WORKS_BUCKET='works-bucket',
            R2_ENDPOINT_URL='https://r2.example.com',
            R2_ACCESS_KEY_ID='key-id',
            R2_SECRET_ACCESS_KEY='secret',
        ):
            with patch('boto3.client', return_value=mock_s3):
                resp = auth_client.post(
                    '/api/v1/works/',
                    {
                        'title': 'My Building',
                        'program': 'residential',
                        'r2_keys': [key],
                        'is_copyright_confirmed': True,
                    },
                    format='json',
                )

        assert resp.status_code == 500
        assert 'Storage check failed for key' in resp.json()['detail']


# ---------------------------------------------------------------------------
# BACK-WORKS-1 — GET /api/v1/works/ list tests (pagination + response slimming)
# ---------------------------------------------------------------------------

class TestList:

    @pytest.mark.django_db
    def test_list_response_shape_no_r2_keys(self, auth_client, user_and_profile):
        """Items expose only the fields the frontend Created tab consumes --
        r2_keys is dropped from each serialized item -- and the envelope
        carries page/page_size alongside works/total."""
        from apps.works.models import Work

        _user, profile = user_and_profile
        Work.objects.create(
            owner=profile,
            upload_id=Work.generate_upload_id(),
            title='House A',
            program='residential',
            r2_keys=[f'works/{profile.id}/abc_cover.webp'],
            is_copyright_confirmed=True,
            is_publishable=True,
        )

        resp = auth_client.get('/api/v1/works/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['total'] == 1
        assert data['page'] == 1
        assert data['page_size'] == 50
        item = data['works'][0]
        assert set(item.keys()) == {
            'upload_id', 'title', 'program', 'cover_url',
            'is_publishable', 'gate_reason', 'created_at',
        }
        assert 'r2_keys' not in item

    @pytest.mark.django_db
    def test_list_pagination(self, auth_client, user_and_profile):
        """?page=1&page_size=2 returns 2 items + correct total (newest first);
        page 2 returns the remainder."""
        import datetime

        from django.utils import timezone

        from apps.works.models import Work

        _user, profile = user_and_profile
        base = timezone.now()
        for i in range(3):
            w = Work.objects.create(
                owner=profile,
                upload_id=Work.generate_upload_id(),
                title=f'House {i}',
                program='residential',
                r2_keys=[],
                is_copyright_confirmed=True,
                is_publishable=True,
            )
            # auto_now_add ignores any value passed to .create(); backfill via
            # .update() so creation order is deterministic in the assertion.
            Work.objects.filter(pk=w.pk).update(created_at=base + datetime.timedelta(seconds=i))

        resp = auth_client.get('/api/v1/works/', {'page': 1, 'page_size': 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data['total'] == 3
        assert data['page'] == 1
        assert data['page_size'] == 2
        assert [w['title'] for w in data['works']] == ['House 2', 'House 1']

        resp2 = auth_client.get('/api/v1/works/', {'page': 2, 'page_size': 2})
        data2 = resp2.json()
        assert data2['total'] == 3
        assert [w['title'] for w in data2['works']] == ['House 0']

    @pytest.mark.django_db
    def test_list_page_size_clamped_at_50(self, auth_client, user_and_profile):
        """A requested page_size above the cap is clamped to 50."""
        from apps.works.models import Work

        _user, profile = user_and_profile
        Work.objects.create(
            owner=profile,
            upload_id=Work.generate_upload_id(),
            title='House A',
            program='residential',
            r2_keys=[],
            is_copyright_confirmed=True,
            is_publishable=True,
        )

        resp = auth_client.get('/api/v1/works/', {'page_size': 999})
        assert resp.status_code == 200
        assert resp.json()['page_size'] == 50

    @pytest.mark.django_db
    def test_list_only_own_works(self, auth_client, user_and_profile):
        """Another user's works are never returned (owner filter untouched)."""
        from django.contrib.auth.models import User

        from apps.works.models import Work

        other_user = User.objects.create_user(
            username='otherworksowner', email='other-works@test.com', password='pass1234',
        )
        other_profile = UserProfile.objects.create(user=other_user, display_name='Other Works User')
        Work.objects.create(
            owner=other_profile,
            upload_id=Work.generate_upload_id(),
            title='Not Mine',
            program='residential',
            r2_keys=[],
            is_copyright_confirmed=True,
            is_publishable=True,
        )

        resp = auth_client.get('/api/v1/works/')
        assert resp.status_code == 200
        assert resp.json()['total'] == 0
