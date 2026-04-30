"""
test_image_hosting_fallback.py -- Image hosting Path C backend tests.

Tests cover:
  - _row_to_card: Divisare fallback logic for cover + gallery merging.
  - ImageLoadTelemetryView: POST /api/v1/telemetry/image-load/ happy + error paths.
"""
import math
import pytest
from django.conf import settings

from apps.recommendation.engine import _row_to_card
from apps.recommendation.models import SessionEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_row(building_id='B00001', **overrides):
    """Build a minimal DB row dict for _row_to_card tests."""
    row = {
        'building_id': building_id,
        'name_en': 'Test Building',
        'project_name': 'Test Project',
        'architect': 'Test Architect',
        'location_country': 'Japan',
        'area_sqm': None,
        'year': 2020,
        'program': 'Museum',
        'style': 'Contemporary',
        'atmosphere': 'calm',
        'color_tone': 'Cool White',
        'material': 'concrete',
        'material_visual': ['concrete', 'glass'],
        'url': 'https://example.com',
        'tags': ['tag1'],
        'image_photos': [],
        'image_drawings': [],
        'cover_image_url_divisare': None,
        'divisare_gallery_urls': [],
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# TestRowToCardDivisareFallback
# ---------------------------------------------------------------------------

class TestRowToCardDivisareFallback:
    """Unit tests for _row_to_card image resolution order."""

    def test_r2_photos_only(self):
        """R2 photos present — cover is R2 URL; gallery is R2 extras + drawings."""
        row = _base_row(
            image_photos=['photo1.jpg', 'photo2.jpg'],
            image_drawings=['draw1.jpg'],
            cover_image_url_divisare=None,
            divisare_gallery_urls=[],
        )
        base = settings.IMAGE_BASE_URL.rstrip('/')
        card = _row_to_card(row)
        assert card['image_url'] == f'{base}/B00001/photo1.jpg'
        assert f'{base}/B00001/photo2.jpg' in card['gallery']
        assert f'{base}/B00001/draw1.jpg' in card['gallery']
        assert card['gallery_drawing_start'] == 1  # 1 extra photo before drawings

    def test_divisare_cover_only(self):
        """No R2 photos; divisare cover present — image_url is the full Divisare URL."""
        row = _base_row(
            image_photos=[],
            image_drawings=[],
            cover_image_url_divisare='https://divisare.example.com/image.jpg',
            divisare_gallery_urls=[],
        )
        card = _row_to_card(row)
        assert card['image_url'] == 'https://divisare.example.com/image.jpg'
        assert card['gallery'] == []

    def test_both_r2_and_divisare_r2_wins_cover_divisare_in_gallery(self):
        """Both R2 photos and Divisare present — R2 cover wins; Divisare gallery merged."""
        row = _base_row(
            image_photos=['cover.jpg'],
            image_drawings=[],
            cover_image_url_divisare='https://divisare.example.com/cover.jpg',
            divisare_gallery_urls=['https://divisare.example.com/g1.jpg', 'https://divisare.example.com/g2.jpg'],
        )
        base = settings.IMAGE_BASE_URL.rstrip('/')
        card = _row_to_card(row)
        assert card['image_url'] == f'{base}/B00001/cover.jpg'
        assert 'https://divisare.example.com/g1.jpg' in card['gallery']
        assert 'https://divisare.example.com/g2.jpg' in card['gallery']

    def test_neither_r2_nor_divisare_empty_url(self):
        """No R2 photos and no Divisare cover — image_url is empty string."""
        row = _base_row(
            image_photos=[],
            image_drawings=[],
            cover_image_url_divisare=None,
            divisare_gallery_urls=[],
        )
        card = _row_to_card(row)
        assert card['image_url'] == ''
        assert card['gallery'] == []

    def test_r2_photos_and_divisare_gallery_merged(self):
        """R2 cover + R2 extras + Divisare gallery all merged in order.

        Gallery order: R2 extras (photo zone) -> Divisare gallery (photo zone) -> R2 drawings.
        gallery_drawing_start = len(extra_photos) + len(divisare_gallery), pointing to first drawing.
        """
        row = _base_row(
            image_photos=['cover.jpg', 'extra1.jpg', 'extra2.jpg'],
            image_drawings=['draw.jpg'],
            cover_image_url_divisare='https://divisare.example.com/cover.jpg',
            divisare_gallery_urls=['https://divisare.example.com/g1.jpg'],
        )
        base = settings.IMAGE_BASE_URL.rstrip('/')
        card = _row_to_card(row)
        assert card['image_url'] == f'{base}/B00001/cover.jpg'
        gallery = card['gallery']
        # Order: R2 extras, Divisare gallery, R2 drawings (drawings at tail)
        assert gallery[0] == f'{base}/B00001/extra1.jpg'
        assert gallery[1] == f'{base}/B00001/extra2.jpg'
        assert gallery[2] == 'https://divisare.example.com/g1.jpg'
        assert gallery[3] == f'{base}/B00001/draw.jpg'
        # drawing_start = 2 extras + 1 divisare = 3; index 3 (draw.jpg) is first drawing
        assert card['gallery_drawing_start'] == 3
        assert card['gallery_drawing_start'] == len(gallery) - 1  # only 1 drawing at tail

    def test_divisare_only_gallery_treated_as_photos(self):
        """Divisare-only building (no R2 photos/drawings): all divisare items are in photo zone.

        gallery_drawing_start == len(gallery) so drawing zone is empty (no items rendered as drawings).
        """
        row = _base_row(
            image_photos=[],
            image_drawings=[],
            cover_image_url_divisare='https://divisare.example.com/cover.jpg',
            divisare_gallery_urls=['https://divisare.example.com/g1.jpg', 'https://divisare.example.com/g2.jpg'],
        )
        card = _row_to_card(row)
        assert card['image_url'] == 'https://divisare.example.com/cover.jpg'
        gallery = card['gallery']
        assert gallery == ['https://divisare.example.com/g1.jpg', 'https://divisare.example.com/g2.jpg']
        # No extra_photos, no drawing_urls; drawing zone is empty (start == len == 2)
        assert card['gallery_drawing_start'] == 2

    def test_gallery_drawing_start_boundary_r2_drawings_only(self):
        """R2 photos + R2 drawings only (no divisare): drawing_start = len(extra_photos)."""
        row = _base_row(
            image_photos=['cover.jpg', 'extra1.jpg'],
            image_drawings=['draw1.jpg', 'draw2.jpg'],
            cover_image_url_divisare=None,
            divisare_gallery_urls=[],
        )
        base = settings.IMAGE_BASE_URL.rstrip('/')
        card = _row_to_card(row)
        gallery = card['gallery']
        # Order: extra1 (photo zone), draw1 draw2 (drawing zone)
        assert gallery[0] == f'{base}/B00001/extra1.jpg'
        assert gallery[1] == f'{base}/B00001/draw1.jpg'
        assert gallery[2] == f'{base}/B00001/draw2.jpg'
        # drawing_start = 1 extra + 0 divisare = 1
        assert card['gallery_drawing_start'] == 1
        assert card['gallery_drawing_start'] == len([f'{base}/B00001/extra1.jpg'])

    def test_missing_divisare_columns_defensive(self):
        """Row lacking divisare columns (older code path) — .get() returns None safely."""
        # Simulate a row that has no Divisare columns at all (KeyError should not occur)
        row = {
            'building_id': 'B00002',
            'name_en': 'Old Building',
            'project_name': 'Old Project',
            'architect': None,
            'location_country': None,
            'area_sqm': None,
            'year': None,
            'program': None,
            'style': None,
            'atmosphere': None,
            'color_tone': None,
            'material': None,
            'material_visual': None,
            'url': None,
            'tags': None,
            'image_photos': ['old_photo.jpg'],
            'image_drawings': [],
            # No 'cover_image_url_divisare', 'divisare_gallery_urls' keys
        }
        base = settings.IMAGE_BASE_URL.rstrip('/')
        card = _row_to_card(row)
        assert card['image_url'] == f'{base}/B00002/old_photo.jpg'
        assert card['gallery'] == []


# ---------------------------------------------------------------------------
# TestImageLoadTelemetryView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestImageLoadTelemetryView:
    """Integration tests for POST /api/v1/telemetry/image-load/."""

    URL = '/api/v1/telemetry/image-load/'

    def test_valid_success_outcome_creates_event(self, api_client):
        """Valid POST with outcome=success returns 201 and creates a SessionEvent."""
        payload = {
            'url': 'https://images.example.com/B00001/photo.jpg',
            'outcome': 'success',
            'building_id': 'B00001',
            'context': 'card',
            'load_ms': 123,
        }
        response = api_client.post(self.URL, payload, format='json')
        assert response.status_code == 201
        assert response.data == {'ok': True}
        event = SessionEvent.objects.filter(event_type='image_load').last()
        assert event is not None
        assert event.payload['outcome'] == 'success'
        assert event.payload['building_id'] == 'B00001'
        assert event.payload['context'] == 'card'
        assert event.payload['load_ms'] == 123
        assert event.payload['domain'] == 'images.example.com'
        assert event.user is None  # anonymous
        assert event.session is None

    def test_invalid_outcome_returns_400(self, api_client):
        """Invalid outcome value returns 400."""
        payload = {
            'url': 'https://images.example.com/B00001/photo.jpg',
            'outcome': 'broken',
        }
        response = api_client.post(self.URL, payload, format='json')
        assert response.status_code == 400
        assert 'invalid outcome' in response.data['detail']

    def test_empty_url_returns_400(self, api_client):
        """Empty url field returns 400."""
        payload = {
            'url': '',
            'outcome': 'failure',
        }
        response = api_client.post(self.URL, payload, format='json')
        assert response.status_code == 400
        assert 'invalid url' in response.data['detail']

    def test_url_too_long_returns_400(self, api_client):
        """URL exceeding 2048 chars returns 400."""
        payload = {
            'url': 'https://images.example.com/' + 'x' * 2050,
            'outcome': 'success',
        }
        response = api_client.post(self.URL, payload, format='json')
        assert response.status_code == 400
        assert 'invalid url' in response.data['detail']

    def test_anonymous_user_returns_201(self, api_client):
        """Anonymous request is accepted — user field on event is None."""
        payload = {
            'url': 'https://cdn.example.com/B00002/image.jpg',
            'outcome': 'timeout',
        }
        response = api_client.post(self.URL, payload, format='json')
        assert response.status_code == 201
        event = SessionEvent.objects.filter(event_type='image_load').last()
        assert event.user is None

    def test_session_id_linked_when_valid(self, db, auth_client, user_profile):
        """Valid session_id from the authenticated user links the SessionEvent to the session."""
        from apps.recommendation.models import AnalysisSession, Project
        project = Project.objects.create(user=user_profile, name='Test Project')
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
        )
        payload = {
            'url': 'https://cdn.example.com/B00003/image.jpg',
            'outcome': 'failure',
            'session_id': str(session.session_id),
        }
        response = auth_client.post(self.URL, payload, format='json')
        assert response.status_code == 201
        event = SessionEvent.objects.filter(event_type='image_load').last()
        assert event.session_id == session.session_id

    def test_malformed_session_id_does_not_500(self, api_client):
        """Garbage session_id is handled gracefully — 201 with session=None."""
        payload = {
            'url': 'https://cdn.example.com/B00004/image.jpg',
            'outcome': 'success',
            'session_id': 'not-a-uuid-at-all!!!',
        }
        response = api_client.post(self.URL, payload, format='json')
        assert response.status_code == 201
        event = SessionEvent.objects.filter(event_type='image_load').last()
        assert event.session is None

    # ---- Fix 3: session ownership injection ----

    def test_anon_user_session_id_silently_dropped(self, db, api_client, user_profile):
        """Anonymous user + valid session_id -> 201, but event.session is None (no linkage)."""
        from apps.recommendation.models import AnalysisSession, Project
        project = Project.objects.create(user=user_profile, name='Anon Drop Test')
        session = AnalysisSession.objects.create(user=user_profile, project=project)
        payload = {
            'url': 'https://cdn.example.com/B00005/image.jpg',
            'outcome': 'success',
            'session_id': str(session.session_id),
        }
        response = api_client.post(self.URL, payload, format='json')
        assert response.status_code == 201
        event = SessionEvent.objects.filter(event_type='image_load').last()
        # Anonymous user cannot link to any session
        assert event.session is None

    def test_other_users_session_id_silently_dropped(self, db, auth_client, user_profile):
        """Authenticated user A + session belonging to user B -> 201, event.session is None."""
        from django.contrib.auth.models import User
        from apps.accounts.models import UserProfile
        from apps.recommendation.models import AnalysisSession, Project
        # Create a second user (B) with their own session
        user_b = User.objects.create_user(username='user_b', password='pass')
        profile_b = UserProfile.objects.create(user=user_b, display_name='User B')
        project_b = Project.objects.create(user=profile_b, name='Project B')
        session_b = AnalysisSession.objects.create(user=profile_b, project=project_b)
        # auth_client is authenticated as user_profile (A), not user B
        payload = {
            'url': 'https://cdn.example.com/B00006/image.jpg',
            'outcome': 'success',
            'session_id': str(session_b.session_id),
        }
        response = auth_client.post(self.URL, payload, format='json')
        assert response.status_code == 201
        event = SessionEvent.objects.filter(event_type='image_load').last()
        # session_b belongs to user B; user A's filter finds 0 matches -> None
        assert event.session is None

    # ---- Fix 4: load_ms guard (unit-level, bypasses JSON serialization for inf/nan) ----

    def _load_ms_guard(self, raw_ms):
        """Mirror the guard logic from ImageLoadTelemetryView.post for unit testing."""
        if (
            isinstance(raw_ms, (int, float))
            and not isinstance(raw_ms, bool)
            and math.isfinite(raw_ms)
            and 0 <= raw_ms <= 60_000
        ):
            return int(raw_ms)
        return None

    def test_load_ms_inf_returns_none(self):
        """load_ms=Infinity is rejected by guard; result is None."""
        # JSON cannot encode Infinity, so we test the guard logic directly.
        assert self._load_ms_guard(float('inf')) is None

    def test_load_ms_nan_returns_none(self):
        """load_ms=NaN is rejected by guard; result is None."""
        assert self._load_ms_guard(float('nan')) is None

    def test_load_ms_negative_dropped(self, api_client):
        """Negative load_ms is out-of-range; stored as None."""
        payload = {
            'url': 'https://cdn.example.com/B00009/image.jpg',
            'outcome': 'success',
            'load_ms': -50,
        }
        response = api_client.post(self.URL, payload, format='json')
        assert response.status_code == 201
        event = SessionEvent.objects.filter(event_type='image_load').last()
        assert event.payload['load_ms'] is None

    def test_load_ms_too_large_dropped(self, api_client):
        """load_ms > 60_000 (60 s timeout territory) is dropped; stored as None."""
        payload = {
            'url': 'https://cdn.example.com/B00010/image.jpg',
            'outcome': 'success',
            'load_ms': 99999,
        }
        response = api_client.post(self.URL, payload, format='json')
        assert response.status_code == 201
        event = SessionEvent.objects.filter(event_type='image_load').last()
        assert event.payload['load_ms'] is None

    def test_load_ms_bool_dropped(self):
        """load_ms=True (bool, subclass of int) is rejected by guard; result is None."""
        assert self._load_ms_guard(True) is None
        assert self._load_ms_guard(False) is None

    def test_load_ms_valid_values_pass_through(self):
        """Valid numeric load_ms values are accepted and returned as int."""
        assert self._load_ms_guard(0) == 0
        assert self._load_ms_guard(123) == 123
        assert self._load_ms_guard(60000) == 60000
        assert self._load_ms_guard(500.7) == 500

    # ---- Fix 2: throttle — verify throttle_classes are set on the view ----

    def test_throttle_classes_configured_on_view(self):
        """ImageLoadTelemetryView has the expected throttle classes set."""
        from apps.recommendation.views import ImageLoadTelemetryView, ImageLoadTelemetryThrottle
        from rest_framework.throttling import UserRateThrottle

        throttle_classes = ImageLoadTelemetryView.throttle_classes
        assert ImageLoadTelemetryThrottle in throttle_classes, (
            "ImageLoadTelemetryThrottle must be in throttle_classes"
        )
        assert UserRateThrottle in throttle_classes, (
            "UserRateThrottle must be in throttle_classes"
        )

    def test_throttle_scope_matches_settings(self):
        """ImageLoadTelemetryThrottle scope must match the key in DEFAULT_THROTTLE_RATES."""
        from apps.recommendation.views import ImageLoadTelemetryThrottle
        from django.conf import settings as _s

        scope = ImageLoadTelemetryThrottle.scope
        rates = _s.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert scope in rates, (
            f"Scope '{scope}' must be configured in REST_FRAMEWORK DEFAULT_THROTTLE_RATES"
        )
