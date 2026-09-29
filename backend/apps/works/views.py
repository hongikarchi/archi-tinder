"""apps.works.views — presigned PUT + finalize endpoints for Work uploads.

FULL-WORKS-1:
  POST /api/v1/works/presign/   — generate presigned PUT URLs for R2 direct upload.
  POST /api/v1/works/           — finalize work after client confirms upload.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.exceptions import PermissionDenied

from .services import _process_work
from .storage import WorksR2DisabledError, _make_s3_client, generate_presigned_put, verify_key_exists

logger = logging.getLogger('apps.works')

# Upper bound on images per upload request (presign) / per work (finalize).
MAX_WORK_IMAGES = 10

# Server-side size cap enforced at finalize (a presigned PUT cannot express
# a size condition the way a POST policy's content-length-range could).
MAX_WORK_IMAGE_BYTES = 10 * 1024 * 1024

# GET /api/v1/works/ pagination (BACK-WORKS-1). Default equals the cap so the
# existing frontend (getMyWorks() sends no params, no load-more UI) keeps
# seeing up to 50 works with zero frontend change.
_WORKS_PAGE_SIZE_DEFAULT = 50
_WORKS_PAGE_SIZE_MAX = 50


class PresignView(APIView):
    """POST /api/v1/works/presign/ — generate presigned PUT URLs."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not settings.WORKS_R2_ENABLED:
            return Response(
                {'detail': 'Works upload not configured on this server.'},
                status=503,
            )

        files = request.data.get('files', [])
        if not isinstance(files, list):
            return Response({'detail': 'files must be a list.'}, status=400)
        if len(files) > MAX_WORK_IMAGES:
            return Response(
                {'detail': f'Too many files: max {MAX_WORK_IMAGES} images per work.'},
                status=400,
            )

        for f in files:
            file_size = f.get('file_size', 0)
            if file_size > MAX_WORK_IMAGE_BYTES:
                return Response({'detail': 'File too large'}, status=400)
            content_type = f.get('content_type', '')
            if not content_type.startswith('image/'):
                return Response({'detail': 'Only image files are accepted'}, status=400)

        profile = request.user.profile
        presign_results = []

        for index, f in enumerate(files):
            content_type = f.get('content_type', 'image/webp')
            slot = 'cover' if index == 0 else f'gallery_{index}'
            key = f'works/{profile.id}/{uuid4().hex[:8]}_{slot}.webp'

            try:
                result = generate_presigned_put(key, content_type)
            except WorksR2DisabledError:
                # Should not reach here (guard above), but belt-and-suspenders.
                return Response(
                    {'detail': 'Works upload not configured on this server.'},
                    status=503,
                )

            presign_results.append({
                'key': key,
                'url': result['url'],
            })

        return Response({'presign_results': presign_results})


class FinalizeView(APIView):
    """GET /api/v1/works/  — list authenticated user's own works.
    POST /api/v1/works/ — create a Work row and start background processing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return a user's uploaded works, newest first.

        Query params (BACK-WORKS-1): page (1-indexed, default 1),
        page_size (default + cap 50 — the default equals the cap so the
        current fetch-all frontend, which sends no params, keeps seeing up
        to 50 works with zero frontend change).

        user_id (optional, design-parity public-profile tabs): when omitted,
        returns the authenticated caller's own works (all, regardless of
        is_publishable — the owner sees their own processing/rejected works
        too). When provided, returns that user's PUBLISHABLE-ONLY works —
        any authenticated user may view another user's published works
        (taste-sharing is the product concept; still requires auth, no
        anonymous access). Unknown user_id -> 404.

        Response 200:
          {works: [{upload_id, title, program, built_status, cover_url,
                    is_publishable, gate_reason, created_at}...], total, page, page_size}

        'total' is the total row count before pagination (not len(works)).
        r2_keys is intentionally omitted from each item — the frontend
        Created tab only consumes the fields above; cover_url is derived
        server-side from r2_keys[0].
        """
        from .models import Work
        from apps.accounts.models import UserProfile

        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = min(
                _WORKS_PAGE_SIZE_MAX,
                max(1, int(request.query_params.get('page_size', _WORKS_PAGE_SIZE_DEFAULT))),
            )
        except (ValueError, TypeError):
            page_size = _WORKS_PAGE_SIZE_DEFAULT

        target_user_id_raw = request.query_params.get('user_id')
        is_owner_view = True
        if target_user_id_raw is not None:
            try:
                target_user_id = int(target_user_id_raw)
            except (ValueError, TypeError):
                return Response({'detail': 'user_id must be an integer.'}, status=400)
            try:
                profile = UserProfile.objects.get(user__id=target_user_id)
            except UserProfile.DoesNotExist:
                return Response({'detail': 'Not found.'}, status=404)
            is_owner_view = (profile.user_id == request.user.id)
        else:
            profile = request.user.profile

        works_qs = Work.objects.filter(owner=profile).order_by('-created_at')
        if not is_owner_view:
            works_qs = works_qs.filter(is_publishable=True)
        total = works_qs.count()
        offset = (page - 1) * page_size
        page_works = works_qs[offset: offset + page_size]

        public_base = getattr(settings, 'WORKS_PUBLIC_BASE_URL', '').rstrip('/')

        results = []
        for w in page_works:
            cover_url = None
            if w.r2_keys and public_base:
                cover_url = f'{public_base}/{w.r2_keys[0]}'
            results.append({
                'upload_id': w.upload_id,
                'title': w.title,
                'program': w.program,
                'built_status': w.built_status,
                'cover_url': cover_url,
                'is_publishable': w.is_publishable,
                'gate_reason': w.gate_reason,
                'created_at': w.created_at.isoformat(),
            })

        return Response({'works': results, 'total': total, 'page': page, 'page_size': page_size})

    def post(self, request):
        from .models import Work

        data = request.data

        title = data.get('title', '')
        program = data.get('program', '')
        built_status = data.get('built_status', 'built')
        location_city = data.get('location_city', '')
        location_country = data.get('location_country', '')
        project_year_raw = data.get('project_year')
        r2_keys = data.get('r2_keys', [])
        is_copyright_confirmed = data.get('is_copyright_confirmed', False)

        # 1a. Copyright confirmation required.
        if is_copyright_confirmed is not True:
            return Response({'detail': 'Copyright confirmation required.'}, status=400)

        # 1b. Title and program are required and must be valid.
        from .models import PROGRAM_CHOICES
        if not title.strip():
            return Response({'detail': 'Title is required.'}, status=400)
        valid_programs = {key for key, _ in PROGRAM_CHOICES}
        if program not in valid_programs:
            return Response(
                {'detail': f'Invalid program value: {program!r}. '
                           f'Allowed values: {sorted(valid_programs)}.'},
                status=400,
            )

        # 1b2. built_status, when provided, must be one of the two choices.
        from .models import BUILT_STATUS_CHOICES
        valid_built_statuses = {key for key, _ in BUILT_STATUS_CHOICES}
        if built_status not in valid_built_statuses:
            return Response(
                {'detail': f'Invalid built_status value: {built_status!r}. '
                           f'Allowed values: {sorted(valid_built_statuses)}.'},
                status=400,
            )

        # 1c. project_year, when provided, must be an integer (raw INSERT would
        # otherwise raise ValueError/TypeError -> unhandled 500).
        project_year = None
        if project_year_raw is not None:
            try:
                project_year = int(project_year_raw)
            except (TypeError, ValueError):
                return Response(
                    {'detail': f'project_year must be an integer, got {project_year_raw!r}.'},
                    status=400,
                )

        # 2. Ownership check — each key must belong to the authenticated user.
        if not isinstance(r2_keys, list):
            return Response({'detail': 'r2_keys must be a list.'}, status=400)
        if not r2_keys:
            return Response({'detail': 'At least one image is required.'}, status=400)
        if len(r2_keys) > MAX_WORK_IMAGES:
            return Response(
                {'detail': f'Too many images: max {MAX_WORK_IMAGES} per work.'},
                status=400,
            )
        if not all(isinstance(key, str) for key in r2_keys):
            return Response({'detail': 'r2_keys must be a list of strings.'}, status=400)
        profile = request.user.profile
        expected_prefix = f'works/{profile.id}/'
        for key in r2_keys:
            if not key.startswith(expected_prefix):
                return Response(
                    {'detail': 'Key does not belong to the authenticated user.'},
                    status=403,
                )

        # 3. Storage existence + size check (only when R2 is enabled).
        # Build one S3 client and reuse it for all keys to avoid per-key
        # client construction overhead (FULL-WORKS-1 low finding).
        # A presigned PUT cannot express a size cap the way the old POST
        # policy's content-length-range condition could, so the 10 MB cap
        # is enforced here, server-side, using the head_object ContentLength.
        #
        # BACK-WORKS-2: the per-key head_object round trips are parallelized
        # (each is a blocking network call; N images = N serial RTTs
        # otherwise). botocore clients are documented thread-safe, so the
        # single shared s3_client is reused across worker threads. Results
        # are gathered fully before any failure is reported, then walked in
        # the ORIGINAL r2_keys order so the reported failing key is
        # deterministic regardless of which thread finishes first.
        if settings.WORKS_R2_ENABLED:
            s3_client = _make_s3_client()

            def _check_key(key):
                try:
                    exists, size = verify_key_exists(key, s3_client=s3_client)
                except Exception as exc:
                    logger.warning('verify_key_exists failed for key=%s: %s', key, exc)
                    return 'error'
                if not exists:
                    return 'missing'
                if size is not None and size > MAX_WORK_IMAGE_BYTES:
                    return 'oversized'
                return 'ok'

            max_workers = min(len(r2_keys), MAX_WORK_IMAGES)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # executor.map preserves input order in its results, matching
                # r2_keys 1:1 regardless of completion order.
                outcomes = list(executor.map(_check_key, r2_keys))

            for key, outcome in zip(r2_keys, outcomes):
                if outcome == 'error':
                    return Response(
                        {'detail': f'Storage check failed for key: {key}'},
                        status=500,
                    )
                if outcome == 'missing':
                    return Response(
                        {'detail': f'Upload not found in storage: {key}'},
                        status=400,
                    )
                if outcome == 'oversized':
                    return Response(
                        {'detail': f'Image exceeds 10MB: {key}'},
                        status=400,
                    )

        # 4. Create Work (is_publishable=False until background processing completes).
        upload_id = Work.generate_upload_id()
        work = Work.objects.create(
            owner=profile,
            upload_id=upload_id,
            title=title,
            program=program,
            built_status=built_status,
            location_city=location_city,
            location_country=location_country,
            project_year=project_year,
            r2_keys=r2_keys,
            is_copyright_confirmed=True,
            is_publishable=False,
        )

        # 5. Background validation thread (mirrors swipe.py daemon thread pattern).
        threading.Thread(
            target=_process_work,
            args=(work.id,),
            daemon=True,
        ).start()

        # 6. Respond immediately.
        return Response(
            {'upload_id': work.upload_id, 'status': 'processing'},
            status=201,
        )


class WorkDetailView(APIView):
    """GET /api/v1/works/<upload_id>/ — retrieve a single work's full detail.

    FULL-WORKS-3: returns cover_url (from cover_r2_key if set, else r2_keys[0])
    plus gallery_urls (all r2_keys). Owner-only: 403 for another user's work,
    404 for a non-existent upload_id.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, upload_id):
        from .models import Work

        try:
            work = Work.objects.get(upload_id=upload_id)
        except Work.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        if work.owner.user != request.user:
            raise PermissionDenied

        public_base = getattr(settings, 'WORKS_PUBLIC_BASE_URL', '').rstrip('/')

        # cover_url: prefer explicit cover_r2_key; fall back to r2_keys[0].
        cover_url = None
        if public_base:
            cover_key = work.cover_r2_key or (work.r2_keys[0] if work.r2_keys else None)
            if cover_key:
                cover_url = f'{public_base}/{cover_key}'

        # gallery_urls: all r2_keys with the public base prefix.
        gallery_urls = []
        if public_base and work.r2_keys:
            gallery_urls = [f'{public_base}/{key}' for key in work.r2_keys]

        # Status derivation: published > rejected (gate_reason set) > processing.
        if work.is_publishable:
            status_str = 'published'
        elif work.gate_reason:
            status_str = 'rejected'
        else:
            status_str = 'processing'

        return Response({
            'upload_id': work.upload_id,
            'title': work.title,
            'program': work.program,
            'built_status': work.built_status,
            'location_city': work.location_city,
            'location_country': work.location_country,
            'project_year': work.project_year,
            'cover_url': cover_url,
            'gallery_urls': gallery_urls,
            'status': status_str,
            'created_at': work.created_at.isoformat(),
        })
