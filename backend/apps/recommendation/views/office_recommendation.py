"""office_recommendation.py — Architect recommendation views.

Two endpoints:
  GET /api/v1/projects/<uuid:pk>/recommended_architects/
      Returns up to 3 architects whose buildings appear most often on the
      requesting user's board, together with up to 5 of their other works
      that are NOT already on the board.

  GET /api/v1/architects/<architect_id>/
      Public-ish architect profile: name + all their publishable buildings
      (up to 50 returned; true total in building_count).

DB notes:
  - canonical_v2_buildings is Make-DB-owned; accessed via connections['buildings']
    (read-only raw SQL, never ORM/migrate).
  - canonical_bld_id has a primary-key B-tree index (canonical_v2_buildings_pkey),
    so the ANY(%s) filter on that column hits the index.
  - architect_canonical_ids is a TEXT[] column. PostgreSQL uses a sequential scan
    for = ANY(architect_canonical_ids) unless a GIN index exists. We cannot CREATE
    INDEX here (DDL not permitted from the make_web_app role). The column has ~2,614
    publishable rows, so a seq-scan is acceptable in the short term.
  - Always gate queries with is_publishable = true (HARD RULE).
"""
import logging

from django.db import connections
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.social.models import ArchitectFollow

from ..models import Project
from ._shared import _get_profile, _liked_id_only

logger = logging.getLogger('apps.recommendation')


def _extract_ids_from_project(project):
    """Return a flat list of unique canonical_bld_id strings from liked + saved.

    saved_ids shape: list[{id: str, saved_at: ISO}]
    liked_ids shape: list[{id: str, intensity: float}] or legacy list[str]
    """
    liked = _liked_id_only(project.liked_ids)
    saved = [
        e.get('id')
        for e in (project.saved_ids or [])
        if isinstance(e, dict) and e.get('id')
    ]
    seen = set()
    result = []
    for bid in liked + saved:
        if isinstance(bid, str) and bid not in seen:
            result.append(bid)
            seen.add(bid)
    return result


def _serialize_building_card(row, include_extra=False):
    """Convert a tuple row from the buildings DB into a response dict.

    Base card fields (both endpoints):
        canonical_bld_id, image_url, name_en, location_country, project_year

    Extra fields (ArchitectDetailView only, include_extra=True):
        location_city, program
    """
    if include_extra:
        (
            canonical_bld_id, name, cover_image_url_default,
            architect_names, architect_canonical_ids,
            location_country, location_city, project_year, program,
        ) = row
    else:
        (
            canonical_bld_id, name, cover_image_url_default,
            architect_names, architect_canonical_ids,
            location_country, project_year,
        ) = row

    card = {
        'canonical_bld_id': canonical_bld_id,
        'image_url': cover_image_url_default or '',
        'name_en': name or '',
        'location_country': location_country or '',
        'project_year': project_year,
    }
    if include_extra:
        card['location_city'] = location_city or ''
        card['program'] = program or ''
    return card, architect_names, architect_canonical_ids


def _resolve_architect_name(architect_id, architect_names, architect_canonical_ids):
    """Find the name for architect_id from a parallel arrays pair.

    architect_canonical_ids and architect_names are TEXT[] columns returned
    as Python lists by psycopg2.  Returns '' on any mismatch.
    """
    if not architect_canonical_ids or not architect_names:
        return ''
    try:
        idx = list(architect_canonical_ids).index(architect_id)
        names = list(architect_names)
        return names[idx] if idx < len(names) else ''
    except ValueError:
        return ''


class RecommendedArchitectsView(APIView):
    """GET /api/v1/projects/<uuid:pk>/recommended_architects/

    Returns up to 3 architects sorted by board-building frequency, each
    annotated with up to 5 of their other publishable works not already on
    the board.

    Ownership: the requesting user must own the project.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        # Ownership check: filter(user=profile) ensures non-owner sees 404.
        project = get_object_or_404(Project.objects.filter(user=profile), project_id=pk)

        board_ids = _extract_ids_from_project(project)
        if not board_ids:
            return Response([], status=status.HTTP_200_OK)

        with connections['buildings'].cursor() as cur:
            # Step 1: rank architects by how many of their buildings appear on the board.
            cur.execute(
                """
                SELECT
                    unnested_id AS architect_id,
                    COUNT(*) AS cnt
                FROM canonical_v2_buildings,
                     UNNEST(architect_canonical_ids) AS unnested_id
                WHERE canonical_bld_id = ANY(%s)
                  AND is_publishable = true
                GROUP BY unnested_id
                ORDER BY cnt DESC
                LIMIT 3
                """,
                [board_ids],
            )
            top_architects = cur.fetchall()  # list of (architect_id, cnt)

        if not top_architects:
            return Response([], status=status.HTTP_200_OK)

        result = []
        with connections['buildings'].cursor() as cur:
            for architect_id, board_count in top_architects:
                # Step 2: fetch up to 5 OTHER buildings by this architect.
                cur.execute(
                    """
                    SELECT canonical_bld_id, name, cover_image_url_default,
                           architect_names, architect_canonical_ids,
                           location_country, project_year
                    FROM canonical_v2_buildings
                    WHERE %s = ANY(architect_canonical_ids)
                      AND canonical_bld_id != ALL(%s)
                      AND is_publishable = true
                    ORDER BY confidence_tier DESC, project_year DESC NULLS LAST
                    LIMIT 5
                    """,
                    [architect_id, board_ids],
                )
                rows = cur.fetchall()

                if not rows:
                    # Skip architect if they have no additional buildings to show.
                    continue

                # Extract architect name from the first row returned.
                first_row_names = rows[0][3]        # architect_names array
                first_row_ids = rows[0][4]           # architect_canonical_ids array
                arch_name = _resolve_architect_name(architect_id, first_row_names, first_row_ids)

                buildings = []
                for row in rows:
                    card, _, _ = _serialize_building_card(row, include_extra=False)
                    buildings.append(card)

                result.append({
                    'architect_id': architect_id,
                    'name': arch_name,
                    'board_building_count': board_count,
                    'buildings': buildings,
                })

        return Response(result, status=status.HTTP_200_OK)


class ArchitectDetailView(APIView):
    """GET /api/v1/architects/<architect_id>/

    Public-ish architect profile.  No project ownership check — just requires
    auth.  Returns name, total building count, and up to 50 buildings ordered
    by confidence_tier DESC, project_year DESC.

    404 when the architect_id has no publishable buildings in the DB.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, architect_id):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        with connections['buildings'].cursor() as cur:
            # Step 1: total count (separate query — LIMIT 50 on the main query
            # means len(rows) is not the true total).
            cur.execute(
                """
                SELECT COUNT(*)
                FROM canonical_v2_buildings
                WHERE %s = ANY(architect_canonical_ids)
                  AND is_publishable = true
                """,
                [architect_id],
            )
            total_count = cur.fetchone()[0]

        if total_count == 0:
            return Response({'detail': 'Architect not found'}, status=status.HTTP_404_NOT_FOUND)

        with connections['buildings'].cursor() as cur:
            cur.execute(
                """
                SELECT canonical_bld_id, name, cover_image_url_default,
                       architect_names, architect_canonical_ids,
                       location_country, location_city, project_year, program
                FROM canonical_v2_buildings
                WHERE %s = ANY(architect_canonical_ids)
                  AND is_publishable = true
                ORDER BY confidence_tier DESC, project_year DESC NULLS LAST
                LIMIT 50
                """,
                [architect_id],
            )
            rows = cur.fetchall()

        if not rows:
            return Response({'detail': 'Architect not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Extract architect name from the first row.
        first_row_names = rows[0][3]
        first_row_ids = rows[0][4]
        arch_name = _resolve_architect_name(architect_id, first_row_names, first_row_ids)

        # Fetch profile metadata from canonical_v2_architects (buildings DB).
        with connections['buildings'].cursor() as cur:
            cur.execute(
                """
                SELECT canonical_name, logo_url, description, website, email,
                       primary_country
                FROM canonical_v2_architects
                WHERE canonical_arch_id = %s
                """,
                [architect_id],
            )
            arch_row = cur.fetchone()

        if arch_row:
            canonical_name, logo_url, description, website, email, primary_country = arch_row
        else:
            canonical_name = logo_url = description = website = email = primary_country = ''

        buildings = []
        for row in rows:
            card, _, _ = _serialize_building_card(row, include_extra=True)
            buildings.append(card)

        is_following = ArchitectFollow.objects.filter(
            follower=profile, architect_id=architect_id
        ).exists()
        follower_count = ArchitectFollow.objects.filter(architect_id=architect_id).count()

        return Response({
            'architect_id': architect_id,
            'name': arch_name or canonical_name or '',
            'logo_url': logo_url or '',
            'description': description or '',
            'website': website or '',
            'email': email or '',
            'primary_country': primary_country or '',
            'building_count': total_count,
            'follower_count': follower_count,
            'is_following': is_following,
            'buildings': buildings,
        }, status=status.HTTP_200_OK)


class ArchitectFollowView(APIView):
    """POST + DELETE /api/v1/architects/<architect_id>/follow/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, architect_id):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        _, created = ArchitectFollow.objects.get_or_create(
            follower=profile,
            architect_id=architect_id,
        )
        follower_count = ArchitectFollow.objects.filter(architect_id=architect_id).count()
        return Response(
            {'following': True, 'follower_count': follower_count},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, architect_id):
        profile = _get_profile(request)
        if not profile:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        deleted_count, _ = ArchitectFollow.objects.filter(
            follower=profile, architect_id=architect_id,
        ).delete()
        if deleted_count == 0:
            return Response({'detail': 'Not following.'}, status=status.HTTP_404_NOT_FOUND)
        follower_count = ArchitectFollow.objects.filter(architect_id=architect_id).count()
        return Response({'following': False, 'follower_count': follower_count}, status=status.HTTP_200_OK)
