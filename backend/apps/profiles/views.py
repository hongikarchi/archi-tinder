from django.conf import settings
from django.db import connection
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Office, OfficeProjectLink
from .serializers import OfficeSerializer, OfficeClaimSerializer, OfficeAdminSerializer
from .throttles import OfficeClaimThrottle


class OfficeDetailView(APIView):
    """GET /api/v1/offices/{office_id}/ -- public Office detail + projects."""
    permission_classes = [permissions.AllowAny]  # Office profiles are public-readable

    def get(self, request, office_id):
        office = get_object_or_404(Office, office_id=office_id)

        # Hydrate projects[] via OfficeProjectLink + raw SQL on architecture_vectors
        building_ids = list(
            OfficeProjectLink.objects
            .filter(office=office)
            .order_by('-confidence', '-created_at')
            .values_list('building_id', flat=True)
        )

        projects = []
        if building_ids:
            base = settings.IMAGE_BASE_URL.rstrip('/')
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT building_id, name_en, year, program, city, image_photos
                    FROM architecture_vectors
                    WHERE building_id = ANY(%s)
                    """,
                    [building_ids],
                )
                rows = cur.fetchall()
                # Preserve ordering from building_ids (confidence-sorted)
                row_map = {row[0]: row for row in rows}
                for bid in building_ids:
                    if bid not in row_map:
                        continue
                    bid, name_en, year, program, city, image_photos = row_map[bid]
                    cover = image_photos[0] if image_photos else None
                    image_url = f'{base}/{bid}/{cover}' if cover else None
                    projects.append({
                        'building_id': bid,
                        'name_en': name_en,
                        'image_url': image_url,
                        'year': year,
                        'program': program,
                        'city': city,
                    })

        serializer = OfficeSerializer(office)
        data = serializer.data
        data['projects'] = projects
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
