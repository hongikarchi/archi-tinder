"""
test_avatar_upload.py -- POST /api/v1/users/me/avatar/ (FRONT-AVATAR-1)

Covers:
  TestAvatarUpload (7 tests)
    - valid PNG upload (authenticated) -> 200, response has avatar_url (absolute
      http URL), file exists on disk, saved image is WEBP + 512x512 square.
    - RGBA/transparent PNG -> 200 (mode conversion without crash).
    - oversized file (>5 MB) -> 400, avatar_url unchanged.
    - non-image bytes with .png name -> 400 (Pillow rejects magic bytes), not 500.
    - unauthenticated -> 401.
    - decompression bomb guard: image with pixel count > AVATAR_MAX_PIXELS -> 400.
    - no file field provided -> 400 with helpful detail.

All tests use the filesystem fallback path (no R2 env vars set in CI).
"""
import io

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Clear throttle + test cache state before and after each test.

    AvatarUploadThrottle (10/min) counts via the Django cache. The root
    conftest _clear_cache autouse does NOT reach apps/accounts/tests/;
    follow the pattern from test_guest_role_affiliation.py.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user_and_profile(db):
    """Create a Django User + UserProfile."""
    from django.contrib.auth.models import User
    user = User.objects.create_user(
        username='avatartest', email='avatar@test.com', password='pass1234',
    )
    profile = UserProfile.objects.create(user=user, display_name='Avatar User')
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
# Helpers
# ---------------------------------------------------------------------------

def _png_uploaded_file(width=100, height=100, mode='RGB', name='avatar.png'):
    """Build a SimpleUploadedFile containing a PNG at the given dimensions."""
    buf = io.BytesIO()
    fill = (128, 128, 128) if mode == 'RGB' else (128, 128, 128, 200)
    Image.new(mode, (width, height), color=fill).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def _rgba_uploaded_file(width=80, height=80):
    """Build a SimpleUploadedFile containing a small RGBA PNG."""
    buf = io.BytesIO()
    Image.new('RGBA', (width, height), (255, 0, 0, 100)).save(buf, format='PNG')
    return SimpleUploadedFile('avatar.png', buf.getvalue(), content_type='image/png')


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAvatarUpload:

    @pytest.mark.django_db
    def test_valid_png_upload_returns_200_and_webp_square(self, auth_client, user_and_profile, tmp_path):
        """Valid PNG upload -> 200, avatar_url absolute URL, WEBP 512x512 on disk."""
        _user, profile = user_and_profile
        upload = _png_uploaded_file(200, 200)

        with override_settings(MEDIA_ROOT=tmp_path, AVATAR_R2_ENABLED=False):
            response = auth_client.post(
                '/api/v1/users/me/avatar/',
                {'avatar': upload},
                format='multipart',
            )

        assert response.status_code == 200
        data = response.json()

        # Response shape: UserSerializer (same as /auth/me/)
        assert 'avatar_url' in data
        url = data['avatar_url']

        # Must be an absolute URL (http or https — test client uses http)
        assert url.startswith('http://') or url.startswith('https://')

        # File must exist on disk under tmp_path.
        # URL pattern: http://testserver/media/avatars/<uuid>.webp
        from urllib.parse import urlparse
        parsed = urlparse(url)
        # e.g. /media/avatars/abc123.webp
        relative = parsed.path
        media_prefix = '/media/'
        assert relative.startswith(media_prefix), f'Expected /media/ prefix, got {relative}'
        storage_key = relative[len(media_prefix):]  # avatars/<uuid>.webp
        saved_path = tmp_path / storage_key
        assert saved_path.exists(), f'Expected file at {saved_path}'

        # Saved file must be WEBP and 512x512 square.
        saved_img = Image.open(str(saved_path))
        assert saved_img.format == 'WEBP'
        assert saved_img.width == 512
        assert saved_img.height == 512

        # Profile avatar_url must be updated in the database.
        profile.refresh_from_db()
        assert profile.avatar_url == url

    @pytest.mark.django_db
    def test_rgba_png_no_crash(self, auth_client, tmp_path):
        """RGBA/transparent PNG -> 200 (mode conversion must not crash)."""
        upload = _rgba_uploaded_file()

        with override_settings(MEDIA_ROOT=tmp_path, AVATAR_R2_ENABLED=False):
            response = auth_client.post(
                '/api/v1/users/me/avatar/',
                {'avatar': upload},
                format='multipart',
            )

        assert response.status_code == 200
        data = response.json()
        assert data.get('avatar_url', '').startswith('http')

    @pytest.mark.django_db
    def test_oversized_file_rejected_400(self, auth_client, user_and_profile, tmp_path):
        """File >5 MB -> 400, avatar_url unchanged (size gate fires before Pillow)."""
        _user, profile = user_and_profile
        original_url = profile.avatar_url

        # Build bytes > 5 MB — PNG header prefix so content_type is consistent,
        # but big enough to trip the explicit size check before Pillow touches it.
        oversized_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * (5 * 1024 * 1024 + 1)
        upload = SimpleUploadedFile('big.png', oversized_bytes, content_type='image/png')

        with override_settings(MEDIA_ROOT=tmp_path, AVATAR_R2_ENABLED=False):
            response = auth_client.post(
                '/api/v1/users/me/avatar/',
                {'avatar': upload},
                format='multipart',
            )

        assert response.status_code == 400
        # avatar_url must not have changed.
        profile.refresh_from_db()
        assert profile.avatar_url == original_url

    @pytest.mark.django_db
    def test_non_image_bytes_rejected_400(self, auth_client, tmp_path):
        """Text content with .png filename -> 400 (Pillow rejects invalid magic bytes)."""
        garbage = b'This is not an image. ' * 100
        upload = SimpleUploadedFile('fake.png', garbage, content_type='image/png')

        with override_settings(MEDIA_ROOT=tmp_path, AVATAR_R2_ENABLED=False):
            response = auth_client.post(
                '/api/v1/users/me/avatar/',
                {'avatar': upload},
                format='multipart',
            )

        assert response.status_code == 400
        data = response.json()
        assert 'detail' in data

    @pytest.mark.django_db
    def test_unauthenticated_returns_401(self, anon_client, tmp_path):
        """Unauthenticated request -> 401."""
        upload = _png_uploaded_file()

        with override_settings(MEDIA_ROOT=tmp_path, AVATAR_R2_ENABLED=False):
            response = anon_client.post(
                '/api/v1/users/me/avatar/',
                {'avatar': upload},
                format='multipart',
            )

        assert response.status_code == 401

    @pytest.mark.django_db
    def test_decompression_bomb_dimension_guard(self, auth_client, tmp_path):
        """Image whose pixel count exceeds AVATAR_MAX_PIXELS -> 400.

        Patches PIL.Image.open to return a mock with oversized .size so the
        explicit w*h guard fires without allocating a multi-GB real image.
        The test PNG is a real but tiny 10x10 image so the upload itself works.
        """
        from unittest.mock import MagicMock, patch

        from django.conf import settings as djsettings

        max_px = djsettings.AVATAR_MAX_PIXELS
        # 10_000 x (max_px // 10_000 + 1) > max_px by construction.
        width = 10_000
        height = max_px // width + 1
        assert width * height > max_px

        # A real tiny PNG so DRF's multipart parser sees a valid upload object.
        upload = _png_uploaded_file(10, 10)

        # Patch Image.open globally so the view's lazy-open call gets the mock.
        mock_img = MagicMock()
        mock_img.size = (width, height)
        mock_img.verify = MagicMock()  # no-op

        with override_settings(MEDIA_ROOT=tmp_path, AVATAR_R2_ENABLED=False):
            with patch('PIL.Image.open', return_value=mock_img):
                response = auth_client.post(
                    '/api/v1/users/me/avatar/',
                    {'avatar': upload},
                    format='multipart',
                )

        assert response.status_code == 400
        data = response.json()
        assert 'detail' in data

    @pytest.mark.django_db
    def test_no_file_field_returns_400(self, auth_client, tmp_path):
        """POST with no file field -> 400 with helpful detail message."""
        with override_settings(MEDIA_ROOT=tmp_path, AVATAR_R2_ENABLED=False):
            response = auth_client.post(
                '/api/v1/users/me/avatar/',
                {},
                format='multipart',
            )

        assert response.status_code == 400
        data = response.json()
        assert 'detail' in data
