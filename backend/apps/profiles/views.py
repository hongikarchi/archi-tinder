import json

from django.db import connections
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Office, OfficeProjectLink
from .serializers import OfficeSerializer, OfficeClaimSerializer, OfficeAdminSerializer
from .throttles import OfficeClaimThrottle


def _get_profile(request):
    try:
        return request.user.userprofile
    except Exception:
        return None


class OfficeDetailView(APIView):
    """GET /api/v1/offices/{office_id}/ -- public Office detail + projects."""
    permission_classes = [permissions.AllowAny]  # Office profiles are public-readable

    def get(self, request, office_id):
        office = get_object_or_404(Office, office_id=office_id)

        # Hydrate projects[] via OfficeProjectLink + raw SQL on canonical_v2_buildings.
        # OfficeProjectLink.building_id stores canonical_bld_id ('bld_000344' format).
        canonical_bld_ids = list(
            OfficeProjectLink.objects
            .filter(office=office)
            .order_by('-confidence', '-created_at')
            .values_list('building_id', flat=True)
        )

        projects = []
        if canonical_bld_ids:
            with connections['buildings'].cursor() as cur:
                cur.execute(
                    """
                    SELECT canonical_bld_id,
                           name,
                           project_year,
                           program,
                           location_city,
                           display_cover_url,
                           cover_image_url_default,
                           covers_by_type,
                           all_images
                    FROM canonical_v2_buildings
                    WHERE canonical_bld_id = ANY(%s)
                      AND is_publishable = true
                    """,
                    [canonical_bld_ids],
                )
                rows = cur.fetchall()
                # Preserve ordering from canonical_bld_ids (confidence-sorted)
                row_map = {row[0]: row for row in rows}
                for cid in canonical_bld_ids:
                    if cid not in row_map:
                        continue
                    (
                        canonical_bld_id, name, project_year, program,
                        location_city, display_cover_url, cover_image_url_default,
                        covers_by_type_raw, all_images_raw,
                    ) = row_map[cid]

                    # Image resolution: source-CDN URLs stored in the row (no R2 composition).
                    # Fallback chain mirrors engine._row_to_card:
                    #   display_cover_url -> cover_image_url_default
                    #   -> covers_by_type.exterior -> all_images[0].url -> ''
                    covers_by_type = covers_by_type_raw or {}
                    if isinstance(covers_by_type, str):
                        try:
                            covers_by_type = json.loads(covers_by_type)
                        except (ValueError, TypeError):
                            covers_by_type = {}
                    all_images = all_images_raw or []
                    if isinstance(all_images, str):
                        try:
                            all_images = json.loads(all_images)
                        except (ValueError, TypeError):
                            all_images = []

                    image_url = (
                        display_cover_url
                        or cover_image_url_default
                        or (covers_by_type.get('exterior') if isinstance(covers_by_type, dict) else None)
                        or ''
                    )
                    if not image_url and all_images:
                        first = all_images[0] if isinstance(all_images[0], dict) else {}
                        image_url = first.get('url') or ''

                    projects.append({
                        'canonical_bld_id': canonical_bld_id,
                        'building_id': canonical_bld_id,  # backward-compat alias
                        'name_en': name,                  # FE reads name_en; source is canonical `name`
                        'image_url': image_url or None,
                        'year': project_year,
                        'program': program,
                        'city': location_city,
                    })

        serializer = OfficeSerializer(office)
        data = serializer.data
        data['projects'] = projects
        data['is_following'] = False
        return Response(data)


class OfficeClaimView(APIView):
    """POST /api/v1/offices/{office_id}/claim/ -- submit claim for verification.

    Fix-loop 1 hardening: claim does NOT mutate Office contact fields before admin
    verification. contact_email / website in payload are silently ignored (removed from
    serializer schema). Admin contacts claimant via request.user context and updates
    contact fields manually post-verification via admin endpoints.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [OfficeClaimThrottle]

    def post(self, request, office_id):
        office = get_object_or_404(Office, office_id=office_id)
        if office.claim_status not in ('unclaimed', 'rejected'):
            return Response(
                {'detail': 'Office already claimed or pending review.'},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = OfficeClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # v0 conservative: just mark pending. Admin reviews via admin endpoint.
        # No pre-verification mutation of Office contact fields (fix-loop 1).
        # Detailed proof-text storage deferred to claim-history-table (PROF1.5).
        office.claim_status = 'pending'
        office.save(update_fields=['claim_status', 'updated_at'])
        return Response(
            {'office_id': str(office.office_id), 'claim_status': office.claim_status},
            status=status.HTTP_200_OK,
        )


class OfficeAdminQueueView(APIView):
    """GET /api/v1/admin/office_claims/ -- admin queue for pending claims."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        offices = Office.objects.filter(claim_status='pending').order_by('updated_at')
        return Response(OfficeAdminSerializer(offices, many=True).data)


class OfficeAdminVerifyView(APIView):
    """PATCH /api/v1/admin/office_claims/{office_id}/ -- admin verifies/rejects."""
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, office_id):
        office = get_object_or_404(Office, office_id=office_id)
        new_status = request.data.get('claim_status')
        if new_status not in ('verified', 'rejected'):
            return Response(
                {'detail': "claim_status must be 'verified' or 'rejected'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        office.claim_status = new_status
        office.verified = (new_status == 'verified')
        office.save(update_fields=['claim_status', 'verified', 'updated_at'])
        return Response({
            'office_id': str(office.office_id),
            'claim_status': office.claim_status,
            'verified': office.verified,
        })
