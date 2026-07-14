"""apps.works.views — presigned POST + finalize endpoints for Work uploads.

FULL-WORKS-1:
  POST /api/v1/works/presign/   — generate presigned POST URLs for R2 direct upload.
  POST /api/v1/works/           — finalize work after client confirms upload.
"""
import logging
import threading
from uuid import uuid4

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import _process_work
from .storage import WorksR2DisabledError, _make_s3_client, generate_presigned_post, verify_key_exists

logger = logging.getLogger('apps.works')


class PresignView(APIView):
    """POST /api/v1/works/presign/ — generate presigned POST URLs."""

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

        _MAX_BYTES = 10 * 1024 * 1024

        for f in files:
            file_size = f.get('file_size', 0)
            if file_size > _MAX_BYTES:
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
                result = generate_presigned_post(key, content_type)
            except WorksR2DisabledError:
                # Should not reach here (guard above), but belt-and-suspenders.
                return Response(
                    {'detail': 'Works upload not configured on this server.'},
                    status=503,
                )

            presign_results.append({
                'key': key,
                'url': result['url'],
                'fields': result['fields'],
            })

        return Response({'presign_results': presign_results})


class FinalizeView(APIView):
    """POST /api/v1/works/ — create a Work row and start background processing."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import Work

        data = request.data

        title = data.get('title', '')
        program = data.get('program', '')
        location_city = data.get('location_city', '')
        location_country = data.get('location_country', '')
        project_year = data.get('project_year')
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

        # 2. Ownership check — each key must belong to the authenticated user.
        if not isinstance(r2_keys, list):
            return Response({'detail': 'r2_keys must be a list.'}, status=400)
        if not r2_keys:
            return Response({'detail': 'At least one image is required.'}, status=400)
        profile = request.user.profile
        expected_prefix = f'works/{profile.id}/'
        for key in r2_keys:
            if not key.startswith(expected_prefix):
                return Response(
                    {'detail': 'Key does not belong to the authenticated user.'},
                    status=403,
                )

        # 3. Storage existence check (only when R2 is enabled).
        # Build one S3 client and reuse it for all keys to avoid per-key
        # client construction overhead (FULL-WORKS-1 low finding).
        if settings.WORKS_R2_ENABLED:
            s3_client = _make_s3_client()
            for key in r2_keys:
                try:
                    exists = verify_key_exists(key, s3_client=s3_client)
                except Exception as exc:
                    logger.warning('verify_key_exists failed for key=%s: %s', key, exc)
                    return Response(
                        {'detail': f'Storage check failed for key: {key}'},
                        status=500,
                    )
                if not exists:
                    return Response(
                        {'detail': f'Upload not found in storage: {key}'},
                        status=400,
                    )

        # 4. Create Work (is_publishable=False until background processing completes).
        upload_id = Work.generate_upload_id()
        work = Work.objects.create(
            owner=profile,
            upload_id=upload_id,
            title=title,
            program=program,
            location_city=location_city,
            location_country=location_country,
            project_year=project_year,
            r2_keys=r2_keys if isinstance(r2_keys, list) else [],
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
