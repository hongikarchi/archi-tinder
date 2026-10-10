"""
Management command: seed_contests

DEV ONLY. Seeds 7 real-world-shaped contests so the /competitions screen has
data before any production import path exists
(docs/decisions/2026-10-09-contest-real-data.md §4-5).

Safety:
  - Refuses to run unless settings.DEBUG is True (Railway runs DEBUG=False).
  - Writes only to the 'default' DB alias. Never touches 'buildings'.
  - Idempotent: update_or_create keyed on (listing_source='seed', title).
  - --clean deletes ONLY listing_source='seed' rows.

Usage:
    python manage.py seed_contests
    python manage.py seed_contests --clean
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.contests.models import Contest

SEED_SOURCE = 'seed'
KST = ZoneInfo('Asia/Seoul')


def kst(year, month, day, hour, minute=0):
    """Aware datetime in Asia/Seoul (stored as UTC by Django)."""
    return datetime(year, month, day, hour, minute, tzinfo=KST)


# ---------------------------------------------------------------------------
# SEED DATA -- ALL VALUES NEED RE-VERIFICATION BEFORE ANY PRODUCTION USE.
#
# On 2026-10-09 the official sites could mostly NOT be read directly
# (ggkia.or.kr: certificate error / IP block; kosid.or.kr: 403), so the values
# below come from listing sites and news articles -- except 정림
# (junglimaward.com), whose dates were read on the official site.
# Poster URLs and 공공누리 (KOGL) marks are unverified for all 7, so no seed
# row carries a poster; poster_url stays None (frontend shows the fallback card).
# ---------------------------------------------------------------------------
SEED_CONTESTS = [
    {
        # (a)
        'title': '대한건축사협회 대학(원)생 모듈러건축 공모전',
        'organizer': '대한건축사협회',
        'organizer_type': Contest.ORGANIZER_ASSOCIATION,
        'status': Contest.STATUS_PUBLISHED,
        'submission_deadline': kst(2026, 12, 2, 15),
        # 이전 조사값, 재확인 필요 (earlier research value, needs re-check) -- only "신청 9/21 시작" was
        # actually confirmed.
        'apply_deadline': kst(2026, 10, 19, 15),
        'eligibility': '건축(공)학 전공 대학(원)생',
        'summary': '모듈러 건축을 주제로 한 대학(원)생 대상 건축 설계 공모전.',
        # Official announcement URL unverified.
        'source_url': 'https://www.kira.or.kr/',
    },
    {
        # (b)
        'title': '제14회 한옥디자인 국제공모',
        'organizer': '한옥건축학회',
        'organizer_type': Contest.ORGANIZER_ASSOCIATION,
        'status': Contest.STATUS_PUBLISHED,
        'submission_deadline': kst(2026, 12, 28, 18),
        'theme': '목구조의 확장: 전통과 현대 재료의 구조적 융합',
        'summary': '전통 목구조와 현대 재료의 구조적 융합을 다루는 한옥 디자인 국제공모.',
        'listing_url': 'https://lectus.kr/14th-hanok-design-int-competition/',
        # Official site unverified -- listing URL used as the source for now.
        'source_url': 'https://lectus.kr/14th-hanok-design-int-competition/',
    },
    {
        # (c)
        'title': '제38회 대한민국 실내건축대전',
        'organizer': '한국실내건축가협회(KOSID)',
        'organizer_type': Contest.ORGANIZER_ASSOCIATION,
        'status': Contest.STATUS_PUBLISHED,
        # 신청 및 1차 작품 접수 마감.
        'submission_deadline': kst(2026, 10, 14, 17),
        'theme': '실내건축디자인 창작품',
        'summary': '신청 및 1차 작품 접수 10/14까지. 2차 작품 접수 11/11, PT심사·시상식 11/14.',
        'eligibility': '대학생·대학원생',
        'team_size': '3인 이내',
        'source_url': 'https://kosid.or.kr/78',
        'listing_url': 'https://linkareer.com/activity/330489',
    },
    {
        # (d)
        'title': '제15회 도로경관디자인 대전',
        'organizer': '한국도로공사',
        'organizer_type': Contest.ORGANIZER_PUBLIC_AGENCY,
        'status': Contest.STATUS_PUBLISHED,
        # 이전 조사값, 재확인 필요 (18:00 is an earlier research value, needs re-check).
        'submission_deadline': kst(2026, 10, 29, 18),
        'summary': '지정 주제와 자유 주제로 도로 경관 디자인 아이디어를 공모.',
        'eligibility': '누구나',
        'team_size': '개인 또는 2인 이내 팀',
        'source_url': 'https://www.ex-contest.co.kr/design26',
    },
    {
        # (e)
        'title': '제62회 경기건축대전',
        'organizer': '한국건축가협회 경기지회',  # per listing sites; verify on ggkia.or.kr
        'organizer_type': Contest.ORGANIZER_ASSOCIATION,
        'status': Contest.STATUS_PUBLISHED,
        # 1차 = online work submission 10/26~10/28.
        'submission_deadline': kst(2026, 10, 28, 18),
        'theme': '변화와 기회의 공간',
        'summary': '1차 온라인 작품 제출 10/26~10/28. 입선 발표 11/2, 2차(패널·모형 접수) 11/21.',
        'eligibility': '대학생·대학원생 (주니어/시니어 부문)',
        'team_size': '3인 이내',
        'source_url': 'http://www.ggkia.or.kr/',
        'listing_url': (
            'https://www.contestkorea.com/sub/view.php'
            '?int_gbn=1&Txt_bcode=&str_no=202607280021'
        ),
    },
    {
        # (f)
        'title': '정림학생건축상 2027',
        'organizer': '정림건축문화재단',
        'organizer_type': Contest.ORGANIZER_PRIVATE_GROUP,
        'status': Contest.STATUS_PUBLISHED,
        # Dates confirmed on the official site; TIME OF DAY NOT CONFIRMED --
        # 23:59 is a placeholder.
        'submission_deadline': kst(2027, 1, 11, 23, 59),
        'apply_deadline': kst(2027, 1, 4, 23, 59),
        'summary': '과제 제출 2027/1/7~1/11, 참가신청 2026/10/26~2027/1/4.',
        'source_url': 'https://www.junglimaward.com/',
    },
    {
        # (g)
        'title': '에어-비트 시티 건축디자인 공모전',
        'organizer': '에어-비트 시티 미래전략위원회',
        'organizer_type': Contest.ORGANIZER_UNKNOWN,
        # Organizer is an unverified ad-hoc body -> stays hidden from users.
        'status': Contest.STATUS_PENDING,
        # 11/20 was a wevity D-n conversion and may be off by one; 11/19 is
        # the sourced value. Time of day unconfirmed.
        'submission_deadline': kst(2026, 11, 19, 23, 59),
        'summary': '에어-비트 시티를 주제로 한 건축 디자인 공모전.',
        'listing_url': 'https://lectus.kr/2026-air-beat-city-arch-competition/',
        'source_url': 'https://lectus.kr/2026-air-beat-city-arch-competition/',
    },
]


class Command(BaseCommand):
    help = (
        'Seed 7 dev contests (listing_source="seed"). '
        'Refuses to run unless settings.DEBUG is True.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean', action='store_true', default=False,
            help="Delete only listing_source='seed' contests, then exit.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stderr.write(self.style.ERROR(
                'seed_contests refuses to run unless settings.DEBUG is True '
                '(Railway prod runs DEBUG=False). Aborting.'
            ))
            raise CommandError('seed_contests: DEBUG is False -- refusing to seed.')

        if options['clean']:
            deleted, _ = Contest.objects.filter(listing_source=SEED_SOURCE).delete()
            self.stdout.write(self.style.SUCCESS(
                'seed_contests --clean: deleted %d contests' % deleted
            ))
            return

        created_count = 0
        updated_count = 0
        for row in SEED_CONTESTS:
            fields = dict(row)
            title = fields.pop('title')
            _, created = Contest.objects.update_or_create(
                listing_source=SEED_SOURCE, title=title, defaults=fields,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            'seed_contests: created %d / updated %d' % (created_count, updated_count)
        ))
