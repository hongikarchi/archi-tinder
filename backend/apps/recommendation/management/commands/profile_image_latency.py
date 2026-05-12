"""
Management command: profile_image_latency

측정 대상
  1. get_building_card()       – 단건 조회 (스와이프당 next+prefetch+prefetch2 = 3회 호출)
  2. get_buildings_by_ids(N)   – 배치 조회 (결과 페이지 / 프로필 보드)
  3. get_diverse_random()      – 초기 화면 다양성 샘플링
  4. simulate_swipe_round()    – get_building_card × 3 순차 (실 스와이프 1회 비용)

각 함수는 DB 쿼리 / URL 조합(_row_to_card) / 기타(embedding 파싱·greedy 샘플링) 로
sub-phase 분리하여 측정한다.

Usage:
    python manage.py profile_image_latency
    python manage.py profile_image_latency --iterations 50
    python manage.py profile_image_latency --batch-sizes 1,5,20,50
"""
import statistics
import time
from typing import List, Dict, Any

from django.core.management.base import BaseCommand
from django.db import connection

import apps.recommendation.engine as engine


# ── Timing helpers ────────────────────────────────────────────────────────────

class Timer:
    """Context manager: accumulates elapsed seconds into a shared list."""
    def __init__(self, bucket: list):
        self._bucket = bucket

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_):
        self._bucket.append(time.perf_counter() - self._t0)


def stats(samples: list) -> dict:
    if not samples:
        return {}
    s = sorted(samples)
    n = len(s)
    def pct(p):
        idx = max(0, min(n - 1, int(p / 100 * n)))
        return s[idx]
    return {
        'n':   n,
        'min': s[0]   * 1000,
        'p50': pct(50) * 1000,
        'p95': pct(95) * 1000,
        'p99': pct(99) * 1000,
        'max': s[-1]  * 1000,
    }


def fmt_row(label: str, s: dict) -> str:
    if not s:
        return f"  {label:<42}  (no data)"
    return (
        f"  {label:<42}  "
        f"min={s['min']:>7.1f}ms  "
        f"p50={s['p50']:>7.1f}ms  "
        f"p95={s['p95']:>7.1f}ms  "
        f"p99={s['p99']:>7.1f}ms  "
        f"max={s['max']:>7.1f}ms  (n={s['n']})"
    )


# ── Sub-phase instrumented versions ──────────────────────────────────────────

def _fetch_raw_row(building_id: str) -> Dict[str, Any]:
    """DB 쿼리만 실행해서 raw dict를 반환 (URL 조합 없음)."""
    required = [
        'building_id', 'name_en', 'project_name', 'architect', 'location_country',
        'city', 'year', 'area_sqm', 'program', 'style', 'atmosphere', 'color_tone',
        'material', 'material_visual', 'url', 'tags', 'image_photos', 'image_drawings',
        'visual_description', 'description',
    ]
    optional = ['cover_image_url_divisare', 'divisare_gallery_urls']
    cols = engine._build_select_columns(required, optional)
    with connection.cursor() as cur:
        cur.execute(
            f'SELECT {cols} FROM architecture_vectors WHERE building_id = %s',
            [building_id],
        )
        rows = engine._dictfetchall(cur)
    return rows[0] if rows else {}


def _fetch_raw_rows_batch(building_ids: List[str]) -> List[Dict[str, Any]]:
    """배치 DB 쿼리만 실행해서 raw dict 리스트 반환."""
    if not building_ids:
        return []
    required = [
        'building_id', 'name_en', 'project_name', 'architect', 'location_country',
        'city', 'year', 'area_sqm', 'program', 'style', 'atmosphere', 'color_tone',
        'material', 'material_visual', 'url', 'tags', 'image_photos', 'image_drawings',
        'visual_description', 'description',
    ]
    optional = ['cover_image_url_divisare', 'divisare_gallery_urls']
    cols = engine._build_select_columns(required, optional)
    ph = ','.join(['%s'] * len(building_ids))
    with connection.cursor() as cur:
        cur.execute(
            f'SELECT {cols} FROM architecture_vectors WHERE building_id IN ({ph})',
            list(building_ids),
        )
        return engine._dictfetchall(cur)


def _pick_sample_ids(n: int) -> List[str]:
    """architecture_vectors에서 랜덤으로 n개의 building_id를 고른다."""
    with connection.cursor() as cur:
        cur.execute(
            'SELECT building_id FROM architecture_vectors ORDER BY RANDOM() LIMIT %s',
            [n],
        )
        return [r[0] for r in cur.fetchall()]


# ── Benchmark runners ─────────────────────────────────────────────────────────

def bench_get_building_card(sample_ids: List[str], iterations: int) -> dict:
    """get_building_card() 전체 / DB / URL조합 분리 측정."""
    t_total, t_db, t_url = [], [], []

    for i in range(iterations):
        bid = sample_ids[i % len(sample_ids)]

        # DB only
        with Timer(t_db):
            row = _fetch_raw_row(bid)

        # URL composition only (using already-fetched row)
        if row:
            with Timer(t_url):
                engine._row_to_card(row)

        # Full function (includes DB + URL)
        with Timer(t_total):
            engine.get_building_card(bid)

    return {'total': stats(t_total), 'db': stats(t_db), 'url_compose': stats(t_url)}


def bench_get_buildings_by_ids(sample_ids: List[str], batch_size: int, iterations: int) -> dict:
    """get_buildings_by_ids(N) 전체 / DB / URL조합 분리 측정."""
    t_total, t_db, t_url = [], [], []

    for i in range(iterations):
        start = (i * batch_size) % max(1, len(sample_ids) - batch_size)
        bids = sample_ids[start:start + batch_size]
        if len(bids) < batch_size:
            bids = (bids * ((batch_size // len(bids)) + 1))[:batch_size]

        # DB only
        with Timer(t_db):
            rows = _fetch_raw_rows_batch(bids)

        # URL composition only
        with Timer(t_url):
            for r in rows:
                engine._row_to_card(r)

        # Full function
        with Timer(t_total):
            engine.get_buildings_by_ids(bids)

    return {'total': stats(t_total), 'db': stats(t_db), 'url_compose': stats(t_url)}


def bench_get_diverse_random(iterations: int) -> dict:
    """get_diverse_random() 전체 / DB+embedding파싱 / greedy샘플링 / URL조합 분리 측정."""
    t_total, t_db_embed, t_greedy, t_url = [], [], [], []
    N = 10
    POOL = min(N * 5, 100)

    for _ in range(iterations):
        # --- phase 1: DB query + embedding::text 파싱 ---
        with Timer(t_db_embed):
            required = [
                'building_id', 'name_en', 'project_name', 'architect', 'location_country',
                'city', 'year', 'area_sqm', 'program', 'style', 'atmosphere', 'color_tone',
                'material', 'material_visual', 'url', 'tags', 'image_photos', 'image_drawings',
                'visual_description', 'description',
            ]
            optional = ['cover_image_url_divisare', 'divisare_gallery_urls']
            cols = engine._build_select_columns(required, optional)
            with connection.cursor() as cur:
                cur.execute(
                    f'SELECT {cols}, embedding::text FROM architecture_vectors ORDER BY RANDOM() LIMIT %s',
                    [POOL],
                )
                rows = engine._dictfetchall(cur)
            for row in rows:
                raw = row['embedding']
                row['_vec'] = [float(x) for x in raw.strip('[]').split(',')]

        # --- phase 2: greedy farthest-point sampling ---
        with Timer(t_greedy):
            selected = [rows[0]]
            remaining = rows[1:]
            while len(selected) < N and remaining:
                best_idx, best_dist = 0, -1
                for i, r in enumerate(remaining):
                    min_sim = min(
                        sum(a * b for a, b in zip(r['_vec'], s['_vec']))
                        for s in selected
                    )
                    dist = 1 - min_sim
                    if dist > best_dist:
                        best_idx, best_dist = i, dist
                selected.append(remaining.pop(best_idx))

        # --- phase 3: URL 조합 ---
        with Timer(t_url):
            for r in selected:
                engine._row_to_card(r)

        # --- 전체 (위 3 phase 합산 기준 비교용) ---
        with Timer(t_total):
            engine.get_diverse_random(N)

    return {
        'total':        stats(t_total),
        'db+embed_parse': stats(t_db_embed),
        'greedy_sampling': stats(t_greedy),
        'url_compose':  stats(t_url),
    }


def bench_simulate_swipe(sample_ids: List[str], iterations: int) -> dict:
    """실제 스와이프 1회 비용: get_building_card × 3 순차 호출."""
    t_total, t_card1, t_card2, t_card3 = [], [], [], []

    for i in range(iterations):
        ids = [
            sample_ids[(i * 3) % len(sample_ids)],
            sample_ids[(i * 3 + 1) % len(sample_ids)],
            sample_ids[(i * 3 + 2) % len(sample_ids)],
        ]

        t0 = time.perf_counter()
        with Timer(t_card1):
            engine.get_building_card(ids[0])   # next_image
        with Timer(t_card2):
            engine.get_building_card(ids[1])   # prefetch
        with Timer(t_card3):
            engine.get_building_card(ids[2])   # prefetch_2
        t_total.append(time.perf_counter() - t0)

    return {
        'total_3_cards': stats(t_total),
        'card1_next':    stats(t_card1),
        'card2_prefetch': stats(t_card2),
        'card3_prefetch2': stats(t_card3),
    }


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Image 전달 레이턴시 프로파일링 — DB쿼리 vs URL조합 병목 측정'

    def add_arguments(self, parser):
        parser.add_argument(
            '--iterations', type=int, default=30,
            help='각 벤치마크 반복 횟수 (기본 30)',
        )
        parser.add_argument(
            '--batch-sizes', type=str, default='1,5,10,50',
            help='배치 조회 테스트 N값 콤마구분 (기본 1,5,10,50)',
        )
        parser.add_argument(
            '--skip-diverse-random', action='store_true',
            help='get_diverse_random 벤치마크 건너뜀 (느린 greedy 샘플링 때문에 시간이 걸림)',
        )

    def handle(self, *args, **options):
        itr = options['iterations']
        batch_sizes = [int(x) for x in options['batch_sizes'].split(',') if x.strip()]
        skip_diverse = options['skip_diverse_random']

        self.stdout.write('\n' + '═' * 110)
        self.stdout.write('  IMAGE LATENCY PROFILER — archi-tinder backend')
        self.stdout.write('═' * 110)
        self.stdout.write(f'  iterations={itr}  batch_sizes={batch_sizes}')
        self.stdout.write('═' * 110 + '\n')

        # DB 연결 확인 + sample IDs 수집
        self.stdout.write('▶ DB에서 sample building IDs 수집 중...')
        max_needed = max(batch_sizes) * itr + itr * 3 + 10
        sample_ids = _pick_sample_ids(min(max_needed, 500))
        if not sample_ids:
            self.stderr.write('ERROR: architecture_vectors에서 building_id를 가져올 수 없습니다.')
            return
        self.stdout.write(f'  {len(sample_ids)}개 ID 수집 완료\n')

        results = {}

        # ── 1. get_building_card ──────────────────────────────────────────────
        self.stdout.write('▶ [1/4] get_building_card() 측정 중...')
        r = bench_get_building_card(sample_ids, itr)
        results['card'] = r
        self.stdout.write('  ┌─ 결과 ─────────────────────────────────────────────────────────────────────')
        self.stdout.write(fmt_row('get_building_card  [TOTAL]', r['total']))
        self.stdout.write(fmt_row('  ├─ DB query only             ', r['db']))
        self.stdout.write(fmt_row('  └─ _row_to_card (URL compose)', r['url_compose']))
        if r['total']['p50'] and r['db']['p50']:
            pct_db = r['db']['p50'] / r['total']['p50'] * 100
            pct_url = r['url_compose']['p50'] / r['total']['p50'] * 100 if r['url_compose'].get('p50') else 0
            self.stdout.write(f'  📊 p50 분담: DB={pct_db:.0f}%  URL조합={pct_url:.0f}%  기타={100-pct_db-pct_url:.0f}%')
        self.stdout.write('')

        # ── 2. simulate_swipe (3×get_building_card) ──────────────────────────
        self.stdout.write('▶ [2/4] 스와이프 1회 시뮬레이션 (next+prefetch+prefetch2) 측정 중...')
        r = bench_simulate_swipe(sample_ids, itr)
        results['swipe'] = r
        self.stdout.write('  ┌─ 결과 ─────────────────────────────────────────────────────────────────────')
        self.stdout.write(fmt_row('swipe_round  [TOTAL 3 cards]', r['total_3_cards']))
        self.stdout.write(fmt_row('  ├─ card1 next_image         ', r['card1_next']))
        self.stdout.write(fmt_row('  ├─ card2 prefetch           ', r['card2_prefetch']))
        self.stdout.write(fmt_row('  └─ card3 prefetch_2         ', r['card3_prefetch2']))
        self.stdout.write('')

        # ── 3. get_buildings_by_ids (batch) ──────────────────────────────────
        self.stdout.write('▶ [3/4] get_buildings_by_ids(N) 배치 조회 측정 중...')
        results['batch'] = {}
        self.stdout.write('  ┌─ 결과 ─────────────────────────────────────────────────────────────────────')
        for bs in batch_sizes:
            r = bench_get_buildings_by_ids(sample_ids, bs, itr)
            results['batch'][bs] = r
            self.stdout.write(fmt_row(f'get_buildings_by_ids(N={bs:>3})  [TOTAL]', r['total']))
            self.stdout.write(fmt_row(f'  ├─ DB query (N={bs:>3})          ', r['db']))
            self.stdout.write(fmt_row(f'  └─ URL compose ×{bs:<3}           ', r['url_compose']))
        self.stdout.write('')

        # ── 4. get_diverse_random ─────────────────────────────────────────────
        if not skip_diverse:
            self.stdout.write('▶ [4/4] get_diverse_random() 측정 중 (greedy sampling 포함 — 시간이 걸릴 수 있음)...')
            r = bench_get_diverse_random(itr)
            results['diverse'] = r
            self.stdout.write('  ┌─ 결과 ─────────────────────────────────────────────────────────────────────')
            self.stdout.write(fmt_row('get_diverse_random  [TOTAL]  ', r['total']))
            self.stdout.write(fmt_row('  ├─ DB query + embed parse    ', r['db+embed_parse']))
            self.stdout.write(fmt_row('  ├─ greedy farthest sampling  ', r['greedy_sampling']))
            self.stdout.write(fmt_row('  └─ URL compose ×10           ', r['url_compose']))
            if r['total']['p50'] and r['db+embed_parse']['p50']:
                pct_db = r['db+embed_parse']['p50'] / r['total']['p50'] * 100
                pct_gr = r['greedy_sampling']['p50'] / r['total']['p50'] * 100
                pct_url = r['url_compose']['p50'] / r['total']['p50'] * 100
                self.stdout.write(
                    f'  📊 p50 분담: DB+파싱={pct_db:.0f}%  greedy={pct_gr:.0f}%  URL조합={pct_url:.0f}%'
                )
            self.stdout.write('')
        else:
            self.stdout.write('▶ [4/4] get_diverse_random 건너뜀 (--skip-diverse-random)\n')

        # ── 종합 진단 ────────────────────────────────────────────────────────
        self.stdout.write('═' * 110)
        self.stdout.write('  DIAGNOSIS')
        self.stdout.write('═' * 110)

        card_total_p50 = results['card']['total']['p50']
        card_db_p50 = results['card']['db']['p50']
        card_url_p50 = results['card']['url_compose'].get('p50', 0)
        swipe_total_p50 = results['swipe']['total_3_cards']['p50']

        self.stdout.write(f'\n  스와이프 응답 비용 (p50 기준):')
        self.stdout.write(f'    • 3× get_building_card 합산: {swipe_total_p50:.1f}ms')
        self.stdout.write(f'    • 단건 카드 평균:            {card_total_p50:.1f}ms')
        self.stdout.write(f'      └─ DB 쿼리:               {card_db_p50:.1f}ms ({card_db_p50/card_total_p50*100:.0f}% of total)' if card_total_p50 else '')
        self.stdout.write(f'      └─ URL 조합:              {card_url_p50:.1f}ms ({card_url_p50/card_total_p50*100:.0f}% of total)' if card_total_p50 else '')

        # 병목 판정
        bottlenecks = []
        if card_db_p50 / max(card_total_p50, 0.001) > 0.7:
            bottlenecks.append('DB 쿼리 (>70% of card latency) — 인덱스 확인 또는 커넥션 풀 튜닝 권장')
        if card_total_p50 > 50:
            bottlenecks.append(f'단건 카드 조회 p50={card_total_p50:.0f}ms > 50ms — Neon cold start 또는 네트워크 RTT 의심')
        if swipe_total_p50 > 200:
            bottlenecks.append(f'스와이프 3-card 합산 p50={swipe_total_p50:.0f}ms > 200ms — 병렬화 검토 필요')
        if results.get('diverse'):
            d = results['diverse']
            if d['greedy_sampling']['p50'] / max(d['total']['p50'], 0.001) > 0.3:
                bottlenecks.append(
                    f"greedy farthest-point p50={d['greedy_sampling']['p50']:.0f}ms "
                    f"({d['greedy_sampling']['p50']/d['total']['p50']*100:.0f}% of diverse_random) — numpy 벡터화 또는 pool 축소 검토"
                )

        if bottlenecks:
            self.stdout.write('\n  ⚠️  병목 감지:')
            for b in bottlenecks:
                self.stdout.write(f'    [!] {b}')
        else:
            self.stdout.write('\n  ✅ 모든 지표 정상 범위')

        self.stdout.write('\n' + '═' * 110 + '\n')
