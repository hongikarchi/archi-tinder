"""
Management command: seed_discovery

Seeds realistic local-dev test data for the People Discovery feed
(FRONT-PEOPLE-CARD-2). GET /api/v1/people/ (apps/social/views_people.py)
only returns candidates that pass BOTH gates:
  1. PersonalityProfile exists with discovery_opt_in=True.
  2. The owning UserProfile has >=1 Project with visibility='public' AND a
     non-empty report_image.

Local dev DBs routinely have 0 rows passing both gates, so the feed is
always empty. This command creates N fake users (auth User + UserProfile +
PersonalityProfile + one public Project carrying a tiny placeholder PNG)
so the feed has real, varied candidates to page through.

type_code derivation is NOT reinvented here — it reuses the exact function
the real assessment endpoint uses (apps/accounts/views/personality.py
_compute_type_code) so every seeded profile's type_code always matches its
axis vector, exactly like a real submission would produce.

Safety:
  - Refuses to run unless settings.DEBUG is True (keeps this off prod;
    Railway runs DEBUG=False).
  - Writes only to the 'default' DB alias (Django ORM). Never touches the
    'buildings' connection.
  - Idempotent: users are keyed by username/handle (get_or_create), so
    re-running does not duplicate rows.

Usage:
    python manage.py seed_discovery                  # seed 20 users (default)
    python manage.py seed_discovery --n 5             # seed 5 users
    python manage.py seed_discovery --n 0             # seed nothing
    python manage.py seed_discovery --clean           # delete all seed_* users
    python manage.py seed_discovery --publish-existing  # flip existing
                                                          # Projects with a
                                                          # report_image to
                                                          # visibility='public'
"""
import struct
import zlib

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import PersonalityProfile, UserProfile
from apps.accounts.views.personality import _compute_type_code
from apps.recommendation.models import Project

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEED_PREFIX = 'seed_'
DEFAULT_N = 20

# Plausible mixed Korean + English display names, cycled with an index
# suffix so `--n` beyond len(_NAMES) still produces unique display names.
_NAMES = [
    '김도윤', '이서연', '박지훈', '최수아', 'Daniel Kim',
    'Sophie Park', '정민준', '한소율', 'Ethan Choi', '윤하은',
    'Olivia Jung', '장현우', '오채원', 'Liam Yoon', '강지우',
    '조은서', 'Emma Kang', '임태양', 'Noah Cho', '신유진',
]

# 16 valid 4-letter type codes (matches views_people._VALID_TYPE_CODES).
_TYPE_CODES = [
    'CLON', 'CLOT', 'CLDN', 'CLDT',
    'CSON', 'CSOT', 'CSDN', 'CSDT',
    'RLON', 'RLOT', 'RLDN', 'RLDT',
    'RSON', 'RSOT', 'RSDN', 'RSDT',
]

# Per-letter sign used to build a vector whose _compute_type_code() output
# matches the intended type code (positive pole > 0.0, negative pole <= 0.0
# per the real derivation rule in accounts/views/personality.py).
_POLE_SIGN = {
    'C': 1, 'R': -1,
    'L': 1, 'S': -1,
    'O': 1, 'D': -1,
    'N': 1, 'T': -1,
}

# Magnitudes cycled per-user so the distance range is wide (near 0 for a
# "just past the tie line" profile up to the full ±1.0 extreme), which
# makes 'inspired' vs 'opposite' sorts on the feed produce visibly
# different orderings.
_MAGNITUDES = [0.15, 0.35, 0.55, 0.75, 0.95]

# axis_5 is a bonus axis (does not affect type_code) — vary it independently
# so vectors are not artificially clustered on that axis.
_AXIS5_VALUES = [-0.9, -0.5, -0.1, 0.1, 0.5, 0.9]


# ---------------------------------------------------------------------------
# Placeholder PNG (pure Python — no Pillow, no new dependency)
# ---------------------------------------------------------------------------

def _png_chunk(chunk_type, data):
    """Build one PNG chunk: length + type + data + CRC32."""
    chunk = chunk_type + data
    crc = zlib.crc32(chunk) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)


def _make_placeholder_png_base64(index, size=64):
    """Generate a tiny solid-color PNG (base64-encoded str), color derived
    from `index` so seeded users get visibly distinct placeholder images.

    Pure struct + zlib — no Pillow, no new dependency, per instruction.
    """
    import base64

    # Deterministic, visually-spread color per index (avoid all-same-hue).
    r = (index * 47) % 256
    g = (index * 97 + 60) % 256
    b = (index * 163 + 120) % 256

    raw_row = bytes([0]) + bytes([r, g, b] * size)  # filter byte 0 (None) + RGB per pixel
    raw = raw_row * size

    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)  # bit depth 8, color type 2 (RGB)
    idat = zlib.compress(raw, level=6)

    png = b'\x89PNG\r\n\x1a\n'
    png += _png_chunk(b'IHDR', ihdr)
    png += _png_chunk(b'IDAT', idat)
    png += _png_chunk(b'IEND', b'')

    return base64.b64encode(png).decode('ascii')


# ---------------------------------------------------------------------------
# Vector construction
# ---------------------------------------------------------------------------

def _vector_for(type_code, seed_index):
    """Build a 5-D axis vector whose _compute_type_code() output equals
    `type_code`, with a magnitude that varies per seed_index for a wide
    distance spread across the feed.
    """
    magnitude = _MAGNITUDES[seed_index % len(_MAGNITUDES)]
    axis_5 = _AXIS5_VALUES[seed_index % len(_AXIS5_VALUES)]
    values = [_POLE_SIGN[letter] * magnitude for letter in type_code]
    values.append(axis_5)
    return values  # [axis_1, axis_2, axis_3, axis_4, axis_5]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        'Seed local-dev test data for the People Discovery feed '
        '(FRONT-PEOPLE-CARD-2). Refuses to run unless settings.DEBUG is True.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--n', type=int, default=DEFAULT_N,
            help='Number of seed users to create (default %d). 0 is valid '
                 '(seed nothing) — useful with --publish-existing.' % DEFAULT_N,
        )
        parser.add_argument(
            '--clean', action='store_true', default=False,
            help='Delete all seed_* users (and their FK-cascaded profiles / '
                 'personality / projects), then exit.',
        )
        parser.add_argument(
            '--publish-existing', action='store_true', default=False,
            dest='publish_existing',
            help="Flip existing Projects that have a non-empty report_image "
                 "to visibility='public' (any owner). Independent of seeding.",
        )

    def handle(self, *args, **options):
        # -- Safety guard: local dev only -------------------------------------
        if not settings.DEBUG:
            self.stderr.write(self.style.ERROR(
                'seed_discovery refuses to run unless settings.DEBUG is True '
                '(Railway prod runs DEBUG=False). Aborting.'
            ))
            raise CommandError('seed_discovery: DEBUG is False — refusing to seed.')

        if options['clean']:
            self._clean()
            return

        n = options['n']
        if n < 0:
            raise CommandError('--n must be >= 0.')

        created_count = 0
        skipped_count = 0

        if n > 0:
            created_count, skipped_count = self._seed(n)

        flipped_count = 0
        if options['publish_existing']:
            flipped_count = self._publish_existing()

        self._print_summary(created_count, skipped_count, flipped_count)

    # -- Seeding ---------------------------------------------------------------

    def _seed(self, n):
        created_count = 0
        skipped_count = 0

        for i in range(n):
            username = f'{SEED_PREFIX}persona_{i:02d}'
            handle = username
            display_name = f'{_NAMES[i % len(_NAMES)]} {i + 1}' if i >= len(_NAMES) else _NAMES[i % len(_NAMES)]
            type_code = _TYPE_CODES[i % len(_TYPE_CODES)]
            vector = _vector_for(type_code, i)
            # Reuse the REAL derivation so seeded type_code always matches
            # its vector, exactly as a live assessment submission would.
            derived_type_code = _compute_type_code(*vector[:4])

            with transaction.atomic():
                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': f'{username}@seed.architinder.local',
                        'first_name': display_name,
                    },
                )
                if not user_created:
                    skipped_count += 1
                    continue
                user.set_unusable_password()
                user.save(update_fields=['password'])

                profile = UserProfile.objects.create(
                    user=user,
                    display_name=display_name,
                    handle=handle,
                    is_guest=True,
                )

                PersonalityProfile.objects.create(
                    user=profile,
                    axis_1=vector[0],
                    axis_2=vector[1],
                    axis_3=vector[2],
                    axis_4=vector[3],
                    axis_5=vector[4],
                    type_code=derived_type_code,
                    discovery_opt_in=True,
                )

                png_b64 = _make_placeholder_png_base64(i)
                Project.objects.create(
                    user=profile,
                    name=f'{display_name}의 취향 보드',
                    visibility='public',
                    report_image=png_b64,
                    report_image_mime='image/png',
                )

                created_count += 1

        return created_count, skipped_count

    # -- Clean -------------------------------------------------------------

    def _clean(self):
        seed_users = User.objects.filter(username__startswith=SEED_PREFIX)
        user_ids = list(seed_users.values_list('id', flat=True))
        profile_ids = list(
            UserProfile.objects.filter(user_id__in=user_ids).values_list('id', flat=True)
        )

        # Project.user -> UserProfile has on_delete=CASCADE (see
        # apps/recommendation/models.py), so deleting the UserProfile cascades
        # to Project automatically. Delete explicitly anyway to report an
        # accurate count and to be robust if that FK's on_delete ever changes.
        project_count = Project.objects.filter(user_id__in=profile_ids).count()
        Project.objects.filter(user_id__in=profile_ids).delete()

        personality_count = PersonalityProfile.objects.filter(user_id__in=profile_ids).count()
        # PersonalityProfile.user -> UserProfile is also on_delete=CASCADE;
        # deleting User below cascades through UserProfile -> PersonalityProfile
        # anyway, but we already counted it before the cascade fires.

        profile_count = len(profile_ids)
        user_count = len(user_ids)

        # Deleting the auth User cascades to UserProfile (OneToOne CASCADE),
        # which cascades to PersonalityProfile and any remaining FKs.
        seed_users.delete()

        self.stdout.write(self.style.SUCCESS(
            'seed_discovery --clean: deleted %d users, %d profiles, '
            '%d personality profiles, %d projects' % (
                user_count, profile_count, personality_count, project_count,
            )
        ))

    # -- Publish existing ----------------------------------------------------

    def _publish_existing(self):
        qs = (
            Project.objects
            .exclude(visibility='public')
            .exclude(report_image__isnull=True)
            .exclude(report_image='')
        )
        flipped = qs.update(visibility='public')
        return flipped

    # -- Summary ---------------------------------------------------------------

    def _print_summary(self, created_count, skipped_count, flipped_count):
        self.stdout.write(
            'seed_discovery: created %d users / skipped %d existing / '
            'flipped %d projects to public' % (created_count, skipped_count, flipped_count)
        )

        candidate_count = self._feed_candidate_count()
        self.stdout.write(
            self.style.SUCCESS(
                'Feed-candidate count (opt_in + public report-image owner): %d'
                % candidate_count
            )
        )

    def _feed_candidate_count(self):
        """Compute the exact same two-gate candidate count views_people.py
        uses, so the printed summary matches what GET /api/v1/people/ will
        actually return (modulo the [:500] cap + top-15-shuffle, which are
        display-time concerns, not pool-membership concerns).
        """
        report_image_owner_ids = set(
            Project.objects
            .filter(visibility='public')
            .exclude(report_image__isnull=True)
            .exclude(report_image='')
            .values_list('user_id', flat=True)
            .distinct()
        )
        return (
            PersonalityProfile.objects
            .filter(discovery_opt_in=True)
            .filter(user_id__in=report_image_owner_ids)
            .count()
        )
