"""
test_phase13_office.py -- Phase 13 PROF1 Office Profile backend tests.

Tests: Office model, OfficeProjectLink model, public OfficeDetailView,
       authenticated OfficeClaimView, and admin OfficeAdminQueueView /
       OfficeAdminVerifyView.

Fix-loop 1 additions:
  - test_claim_does_not_mutate_office_fields (Fix 1 — no pre-verification mutation)
  - test_office_project_link_confidence_bounds_validation (Fix 3 — validators)
  - test_rejected_office_can_be_reclaimed (Fix 5 — rejected→reclaim path)
"""
import uuid
import pytest
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile
from apps.profiles.models import Office, OfficeProjectLink


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def office(db):
    """A basic unclaimed office for reuse across tests."""
    return Office.objects.create(
        name='OMA',
        description='Office for Metropolitan Architecture',
        location='Rotterdam, Netherlands',
        founded_year=1975,
        website='https://oma.com',
        contact_email='info@oma.com',
    )


@pytest.fixture
def auth_client(db):
    """APIClient with JWT Bearer token for a standard test user."""
    user = User.objects.create_user(
        username='testuser_prof1', email='prof1@test.com', password='testpass123',
    )
    UserProfile.objects.create(user=user, display_name='Prof1 Test User')
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def admin_client(db):
    """APIClient with JWT for an is_staff + is_superuser user."""
    admin_user = User.objects.create_superuser(
        username='adminuser_prof1', email='admin_prof1@test.com', password='admin123',
    )
    UserProfile.objects.create(user=admin_user, display_name='Admin User')
    client = APIClient()
    refresh = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# TestOfficeModel
# ---------------------------------------------------------------------------

class TestOfficeModel:

    @pytest.mark.django_db
    def test_office_create_with_default_claim_status_unclaimed(self):
        office = Office.objects.create(name='Zaha Hadid Architects')
        assert office.claim_status == 'unclaimed'
        assert office.verified is False
        assert office.follower_count == 0
        assert office.following_count == 0

    @pytest.mark.django_db
    def test_office_str_repr_includes_verification_state(self):
        office = Office.objects.create(name='SANAA', claim_status='unclaimed')
        assert 'unclaimed' in str(office)
        assert 'SANAA' in str(office)

        office.verified = True
        office.save()
        assert 'verified' in str(office)

    @pytest.mark.django_db
    def test_office_canonical_id_indexed_lookup(self):
        Office.objects.create(name='Bjarke Ingels Group', canonical_id=42)
        Office.objects.create(name='Foster + Partners', canonical_id=99)
        result = Office.objects.filter(canonical_id=42).first()
        assert result is not None
        assert result.name == 'Bjarke Ingels Group'


# ---------------------------------------------------------------------------
# TestOfficeProjectLink
# ---------------------------------------------------------------------------

class TestOfficeProjectLink:

    @pytest.mark.django_db
    def test_link_unique_together_office_building_id(self, office):
        OfficeProjectLink.objects.create(
            office=office,
            building_id='B00042',
            confidence=1.0,
            source='manual',
        )
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            OfficeProjectLink.objects.create(
                office=office,
                building_id='B00042',  # duplicate
                confidence=1.0,
                source='manual',
            )

    @pytest.mark.django_db
    def test_link_create_with_canonical_fk_source(self, office):
        link = OfficeProjectLink.objects.create(
            office=office,
            building_id='B00001',
            confidence=1.0,
            source='canonical_fk',
        )
        assert link.source == 'canonical_fk'
        assert link.confidence == 1.0
        assert 'B00001' in str(link)

    @pytest.mark.django_db
    def test_link_create_with_manual_source_confidence_1(self, office):
        link = OfficeProjectLink.objects.create(
            office=office,
            building_id='B00002',
            confidence=1.0,
            source='manual',
        )
        assert link.source == 'manual'
        assert link.confidence == 1.0

    @pytest.mark.django_db
    def test_link_create_with_string_match_confidence_below_1(self, office):
        link = OfficeProjectLink.objects.create(
            office=office,
            building_id='B00003',
            confidence=0.87,
            source='string_match',
        )
        assert link.source == 'string_match'
        assert link.confidence < 1.0

    @pytest.mark.django_db
    def test_office_project_link_confidence_bounds_validation(self, office):
        """Fix-loop 1 Fix 3: confidence field validators enforce [0.0, 1.0] range."""
        # Below lower bound
        link_neg = OfficeProjectLink(
            office=office,
            building_id='B00099',
            confidence=-0.5,
            source='string_match',
        )
        with pytest.raises(ValidationError):
            link_neg.full_clean()

        # Above upper bound
        link_high = OfficeProjectLink(
            office=office,
            building_id='B00098',
            confidence=2.0,
            source='string_match',
        )
        with pytest.raises(ValidationError):
            link_high.full_clean()

        # Boundary values are valid
        link_zero = OfficeProjectLink(
            office=office,
            building_id='B00097',
            confidence=0.0,
            source='string_match',
        )
        link_zero.full_clean()  # should not raise

        link_one = OfficeProjectLink(
            office=office,
            building_id='B00096',
            confidence=1.0,
            source='manual',
        )
        link_one.full_clean()  # should not raise


# ---------------------------------------------------------------------------
# TestOfficeDetailView
# ---------------------------------------------------------------------------

class TestOfficeDetailView:

    @pytest.mark.django_db
    def test_get_office_returns_mock_office_shape(self, api_client, office):
        url = f'/api/v1/offices/{office.office_id}/'
        response = api_client.get(url)
        assert response.status_code == 200
        data = response.json()
        # All fields matching MOCK_OFFICE shape must be present
        expected_keys = {
            'office_id', 'name', 'verified', 'website_url', 'contact_email',
            'description', 'logo_url', 'location', 'founded_year',
            'follower_count', 'following_count', 'projects',
        }
        assert expected_keys.issubset(set(data.keys())), (
            f'Missing keys: {expected_keys - set(data.keys())}'
        )
        assert isinstance(data['projects'], list)
        # Verify website_url maps correctly from model's 'website' field
        assert data['website_url'] == 'https://oma.com'

    @pytest.mark.django_db
    def test_get_office_404_on_missing(self, api_client):
        fake_uuid = str(uuid.uuid4())
        url = f'/api/v1/offices/{fake_uuid}/'
        response = api_client.get(url)
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_get_office_excludes_admin_fields(self, api_client, office):
        url = f'/api/v1/offices/{office.office_id}/'
        response = api_client.get(url)
        data = response.json()
        # Admin-only fields must NOT appear in public response
        for admin_field in ('claim_status', 'aliases', 'canonical_id'):
            assert admin_field not in data, f'Admin field "{admin_field}" leaked into public response'

    @pytest.mark.django_db
    @patch('apps.profiles.views.connection')
    def test_get_office_hydrates_projects_from_links(self, mock_conn, api_client, office):
        # Create a project link
        OfficeProjectLink.objects.create(
            office=office,
            building_id='B00042',
            confidence=1.0,
            source='manual',
        )
        # Mock raw SQL cursor returning architecture_vectors row
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            ('B00042', 'Seattle Central Library', 2004, 'Public', 'Seattle', ['0_cover.jpg']),
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        url = f'/api/v1/offices/{office.office_id}/'
        response = api_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert len(data['projects']) == 1
        proj = data['projects'][0]
        assert proj['building_id'] == 'B00042'
        assert proj['name_en'] == 'Seattle Central Library'
        assert proj['year'] == 2004
        assert proj['program'] == 'Public'
        assert proj['city'] == 'Seattle'
        assert proj['image_url'] is not None
        assert 'B00042' in proj['image_url']
        assert '0_cover.jpg' in proj['image_url']


# ---------------------------------------------------------------------------
# TestOfficeClaimView
# ---------------------------------------------------------------------------

class TestOfficeClaimView:

    @pytest.mark.django_db
    def test_claim_unauthenticated_returns_401(self, api_client, office):
        url = f'/api/v1/offices/{office.office_id}/claim/'
        response = api_client.post(url, {}, format='json')
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_claim_unclaimed_office_marks_pending(self, auth_client, office):
        cache.clear()  # reset throttle counters
        url = f'/api/v1/offices/{office.office_id}/claim/'
        response = auth_client.post(
            url,
            {'proof_text': 'I work here.'},
            format='json',
        )
        assert response.status_code == 200
        office.refresh_from_db()
        assert office.claim_status == 'pending'
        assert response.json()['claim_status'] == 'pending'

    @pytest.mark.django_db
    def test_claim_does_not_mutate_office_fields(self, auth_client, office):
        """Fix-loop 1: claim payload contact_email/website silently ignored (not in schema).
        Office.contact_email and .website remain unchanged after claim submission.
        """
        cache.clear()  # reset throttle counters
        original_email = office.contact_email  # 'info@oma.com' from fixture
        original_website = office.website       # 'https://oma.com' from fixture
        url = f'/api/v1/offices/{office.office_id}/claim/'
        response = auth_client.post(
            url,
            # contact_email + website are NOT in OfficeClaimSerializer schema —
            # silently ignored. Submitting them tests the security-vector regression:
            # even if an attacker passes legacy payload fields, Office is unchanged.
            {
                'proof_text': 'I am the founding partner.',
                'contact_email': 'attacker@evil.com',
                'website': 'https://evil.com',
            },
            format='json',
        )
        assert response.status_code == 200
        office.refresh_from_db()
        assert office.claim_status == 'pending'
        assert office.contact_email == original_email, (
            'Claim must NOT mutate contact_email before admin verification'
        )
        assert office.website == original_website, (
            'Claim must NOT mutate website before admin verification'
        )

    @pytest.mark.django_db
    def test_claim_already_pending_returns_409(self, auth_client, office):
        cache.clear()
        office.claim_status = 'pending'
        office.save()
        url = f'/api/v1/offices/{office.office_id}/claim/'
        response = auth_client.post(url, {}, format='json')
        assert response.status_code == 409

    @pytest.mark.django_db
    def test_claim_already_verified_returns_409(self, auth_client, office):
        cache.clear()
        office.claim_status = 'verified'
        office.verified = True
        office.save()
        url = f'/api/v1/offices/{office.office_id}/claim/'
        response = auth_client.post(url, {}, format='json')
        assert response.status_code == 409

    @pytest.mark.django_db
    def test_rejected_office_can_be_reclaimed(self, auth_client, office):
        """Fix-loop 1 Fix 5: Office.claim_status='rejected' allows re-claim attempt."""
        cache.clear()  # reset throttle counters to avoid interference from other tests
        office.claim_status = 'rejected'
        office.save()
        url = f'/api/v1/offices/{office.office_id}/claim/'
        response = auth_client.post(url, {}, format='json')
        assert response.status_code == 200
        office.refresh_from_db()
        assert office.claim_status == 'pending'
        assert response.json()['claim_status'] == 'pending'


# ---------------------------------------------------------------------------
# TestOfficeAdminQueueView
# ---------------------------------------------------------------------------

class TestOfficeAdminQueueView:

    @pytest.mark.django_db
    def test_admin_queue_lists_pending_only(self, admin_client):
        Office.objects.create(name='Pending Office', claim_status='pending')
        Office.objects.create(name='Unclaimed Office', claim_status='unclaimed')
        Office.objects.create(name='Verified Office', claim_status='verified', verified=True)

        response = admin_client.get('/api/v1/admin/office_claims/')
        assert response.status_code == 200
        data = response.json()
        assert all(item['claim_status'] == 'pending' for item in data)
        names = [item['name'] for item in data]
        assert 'Pending Office' in names
        assert 'Unclaimed Office' not in names
        assert 'Verified Office' not in names

    @pytest.mark.django_db
    def test_admin_queue_unauthorized_for_non_admin(self, auth_client):
        response = auth_client.get('/api/v1/admin/office_claims/')
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# TestOfficeAdminVerifyView
# ---------------------------------------------------------------------------

class TestOfficeAdminVerifyView:

    @pytest.mark.django_db
    def test_admin_verify_flips_verified_true_and_status_verified(self, admin_client):
        office = Office.objects.create(name='Claim Pending', claim_status='pending')
        url = f'/api/v1/admin/office_claims/{office.office_id}/'
        response = admin_client.patch(url, {'claim_status': 'verified'}, format='json')
        assert response.status_code == 200
        office.refresh_from_db()
        assert office.claim_status == 'verified'
        assert office.verified is True
        data = response.json()
        assert data['verified'] is True
        assert data['claim_status'] == 'verified'

    @pytest.mark.django_db
    def test_admin_reject_keeps_verified_false(self, admin_client):
        office = Office.objects.create(name='To Reject', claim_status='pending')
        url = f'/api/v1/admin/office_claims/{office.office_id}/'
        response = admin_client.patch(url, {'claim_status': 'rejected'}, format='json')
        assert response.status_code == 200
        office.refresh_from_db()
        assert office.claim_status == 'rejected'
        assert office.verified is False

    @pytest.mark.django_db
    def test_admin_invalid_status_returns_400(self, admin_client):
        office = Office.objects.create(name='Bad Status Office', claim_status='pending')
        url = f'/api/v1/admin/office_claims/{office.office_id}/'
        response = admin_client.patch(url, {'claim_status': 'approved'}, format='json')
        assert response.status_code == 400
