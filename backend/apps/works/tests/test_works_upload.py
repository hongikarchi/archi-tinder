"""test_works_upload.py — FULL-WORKS-1 upload endpoint tests.

9 tests covering:
  1. test_presign_disabled_503
  2. test_presign_file_too_large
  3. test_presign_invalid_content_type
  4. test_presign_success
  5. test_finalize_no_copyright
  6. test_finalize_foreign_key_prefix
  7. test_finalize_key_not_in_r2
  8. test_finalize_success
  9. test_finalize_unauthenticated

Fixtures mirror accounts/tests/test_avatar_upload.py.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile


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
        mock_s3.generate_presigned_post.return_value = {
            'url': 'https://r2.example.com/upload',
            'fields': {'key': 'works/test_key', 'Policy': 'abc', 'X-Amz-Signature': 'sig'},
        }

        with override_settings(
            WORKS_R2_ENABLED=True,
            R2_WORKS_BUCKET='works-bucket',
            R2_ENDPOINT_URL='https://r2.example.com',
            R2_ACCESS_KEY_ID='key-id',
            R2_SECRET_ACCESS_KEY='secret',
        ):
            # boto3 is lazily imported inside generate_presigned_post;
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
        assert results[0]['url'] == 'https://r2.example.com/upload'
        assert 'fields' in results[0]


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
