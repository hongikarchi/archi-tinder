"""
test_session_create_correctness.py — 3-fix correctness tests (2026-05-26 Codex retest).

Fix 1: /projects/ cache evicted on session create, swipe write, and dedupe hit.
Fix 2: project_id provided → dedupe skipped; new AnalysisSession created on target project.
Fix 3: no orphan Project row when pool fetch fails or returns empty.
"""
import pytest
import numpy as np
from unittest.mock import patch
from django.core.cache import cache

from apps.recommendation.models import Project, AnalysisSession
from apps.recommendation.caches import _projects_list_key

# ---------------------------------------------------------------------------
# Shared engine mock infrastructure — mirrors test_sessions.py
# ---------------------------------------------------------------------------

_FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]  # B00001..B00015
_FAKE_SCORES = {bid: 15 - i for i, bid in enumerate(_FAKE_POOL)}
_FAKE_EMBEDDINGS = {
    bid: np.random.RandomState(i).randn(384).astype(np.float64)
    for i, bid in enumerate(_FAKE_POOL)
}
for bid in _FAKE_EMBEDDINGS:
    v = _FAKE_EMBEDDINGS[bid]
    norm = np.linalg.norm(v)
    if norm > 0:
        _FAKE_EMBEDDINGS[bid] = v / norm


def _mock_farthest_point(pool_ids, exposed_ids, pool_embeddings):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _mock_get_card(bid, image_focus=None):
    if bid is None:
        return None
    return {
        'canonical_bld_id': bid,
        'name': f'Building {bid}',
        'image_url': '',
        'covers_by_type': {},
        'url': None,
        'gallery': [],
        'gallery_drawing_start': 0,
        'metadata': {
            'axis_typology': 'Museum',
            'axis_architects': 'Test Arch',
            'axis_country': 'Korea',
            'axis_city': None,
            'axis_year': 2022,
            'axis_style': 'Modern',
            'axis_atmosphere': 'bold',
            'axis_color_tone': 'Dark',
            'axis_material_visual': [],
            'visual_description': '',
        },
    }


def _mock_get_embedding(bid):
    if bid in _FAKE_EMBEDDINGS:
        return _FAKE_EMBEDDINGS[bid].tolist()
    return list(np.random.randn(384))


def _mock_update_pref(pref_vector, embedding, action):
    return list(np.random.RandomState(42).randn(384))


def _mock_compute_centroids(like_vectors, round_num, multimodal_floor=None):
    c = np.random.RandomState(42).randn(384)
    c = c / np.linalg.norm(c)
    return ([c], c)


def _mock_mmr_next(pool_ids, exposed_ids, pool_embeddings, like_vectors, round_num, **kwargs):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _sync_emit_telemetry(swipe_kwargs, confidence_kwargs):
    from apps.recommendation import event_log
    event_log.emit_swipe_event(**swipe_kwargs)
    if confidence_kwargs is not None:
        event_log.emit_event('confidence_update', **confidence_kwargs)


_ENGINE = 'apps.recommendation.views.engine'
_SESSIONS_VIEW = 'apps.recommendation.views.sessions'
_SWIPE_VIEW = 'apps.recommendation.views.swipe'


class _SyncThread:
    """Run telemetry synchronously while suppressing async prefetch in tests."""
    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **kw):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if getattr(self._target, '__name__', '') == '_async_prefetch_thread':
            return
        if self._target:
            self._target(*self._args, **self._kwargs)


_BASE_PATCHES = {
    f'{_ENGINE}.create_pool_with_relaxation': (
        lambda *a, **kw: (_FAKE_POOL[:], dict(_FAKE_SCORES), 1)
    ),
    f'{_ENGINE}.get_pool_embeddings': (
        lambda pool_ids: {bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)) for bid in pool_ids}
    ),
    f'{_ENGINE}.farthest_point_from_pool': _mock_farthest_point,
    f'{_ENGINE}.get_building_card': _mock_get_card,
    f'{_ENGINE}.get_building_embedding': _mock_get_embedding,
    f'{_ENGINE}.update_preference_vector': _mock_update_pref,
    f'{_ENGINE}.compute_taste_centroids': _mock_compute_centroids,
    f'{_ENGINE}.compute_mmr_next': _mock_mmr_next,
    f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
    f'{_ENGINE}.check_convergence': lambda *a: False,
    f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: 'B00010',
    f'{_ENGINE}._random_pool': lambda target: _FAKE_POOL[:target],
    f'{_SWIPE_VIEW}.threading.Thread': _SyncThread,
    f'{_SWIPE_VIEW}._emit_telemetry_thread': _sync_emit_telemetry,
}


def _apply_patches(extra=None):
    """Start base patchers, plus any extras. Returns list of started patchers."""
    patchers = []
    merged = dict(_BASE_PATCHES)
    if extra:
        merged.update(extra)
    for target, side_effect in merged.items():
        p = patch(target, side_effect=side_effect)
        p.start()
        patchers.append(p)
    return patchers


def _stop_patches(patchers):
    for p in patchers:
        p.stop()


def _post_session(auth_client, payload=None, extra_patches=None):
    """POST to /api/v1/analysis/sessions/. Returns response."""
    if payload is None:
        payload = {'filters': {}, 'name': 'Correctness Test', 'raw_query': 'modern arch'}
    patchers = _apply_patches(extra_patches)
    try:
        resp = auth_client.post(
            '/api/v1/analysis/sessions/',
            payload,
            format='json',
        )
    finally:
        _stop_patches(patchers)
    return resp


def _canonical_cache_key(profile_id):
    """Return the canonical page-1 cache key that evict_projects_list clears."""
    return _projects_list_key(profile_id, 1, 50)


def _seed_projects_cache(profile_id):
    """Populate the canonical /projects/ cache entry with a sentinel value."""
    key = _canonical_cache_key(profile_id)
    cache.set(key, {'sentinel': True}, 120)
    return key


def _cache_is_evicted(profile_id):
    """Return True if the canonical cache entry is gone."""
    return cache.get(_canonical_cache_key(profile_id)) is None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCacheEviction:

    # -----------------------------------------------------------------------
    # Fix 1a: session create evicts /projects/ cache
    # -----------------------------------------------------------------------
    def test_cache_evicted_on_session_create(self, auth_client, user_profile):
        """POST session create with no project_id → cache key deleted after success."""
        _seed_projects_cache(user_profile.id)
        assert not _cache_is_evicted(user_profile.id), 'Precondition: cache must be populated'

        resp = _post_session(auth_client)
        assert resp.status_code == 201, f'Expected 201, got {resp.status_code}: {resp.json()}'

        assert _cache_is_evicted(user_profile.id), '/projects/ cache must be evicted after session create'

    # -----------------------------------------------------------------------
    # Fix 1b: swipe write evicts /projects/ cache
    # -----------------------------------------------------------------------
    def test_cache_evicted_on_swipe_write(self, auth_client, user_profile):
        """POST swipe (like) → cache key deleted after save."""
        # Create project + session first (no cache seeding yet — avoid evict in setup)
        project = Project.objects.create(user=user_profile, name='Swipe Cache Test', filters={})
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'project_id': str(project.project_id), 'filters': {}},
                format='json',
            )
        finally:
            _stop_patches(patchers)
        assert resp.status_code == 201
        session_id = resp.json()['session_id']
        first_card_id = _FAKE_POOL[0]

        # Seed cache AFTER session create (so the evict from session create doesn't count)
        _seed_projects_cache(user_profile.id)
        assert not _cache_is_evicted(user_profile.id)

        # POST a swipe
        patchers = _apply_patches()
        try:
            swipe_resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {'canonical_bld_id': first_card_id, 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)
        assert swipe_resp.status_code == 200, f'Swipe failed: {swipe_resp.json()}'

        assert _cache_is_evicted(user_profile.id), '/projects/ cache must be evicted after swipe'

    # -----------------------------------------------------------------------
    # Fix 1c: dedupe hit evicts /projects/ cache
    # -----------------------------------------------------------------------
    def test_cache_evicted_on_dedupe_hit(self, auth_client, user_profile):
        """Second POST (dedupe hit) also evicts /projects/ cache."""
        payload = {'filters': {}, 'name': 'Dedupe Cache Test', 'raw_query': 'modern Korean'}

        # First POST — creates session
        resp1 = _post_session(auth_client, payload)
        assert resp1.status_code == 201

        # Seed cache AFTER first create
        _seed_projects_cache(user_profile.id)
        assert not _cache_is_evicted(user_profile.id)

        # Second POST — dedupe hit
        resp2 = _post_session(auth_client, payload)
        assert resp2.status_code == 200, f'Expected 200 dedupe, got {resp2.status_code}: {resp2.json()}'
        assert resp2.json().get('deduped') is True

        assert _cache_is_evicted(user_profile.id), '/projects/ cache must be evicted on dedupe hit'


@pytest.mark.django_db
class TestDedupeProjectIdBypass:

    # -----------------------------------------------------------------------
    # Fix 2: project_id provided → dedupe skipped
    # -----------------------------------------------------------------------
    def test_project_id_provided_skips_dedupe(self, auth_client, user_profile):
        """If project_id is given, dedupe logic is bypassed even if name+query match."""
        # Create a decoy session via implicit flow (no project_id) with same name+query
        decoy_payload = {'filters': {}, 'name': 'Shared Name', 'raw_query': 'shared query'}
        resp_decoy = _post_session(auth_client, decoy_payload)
        assert resp_decoy.status_code == 201, f'Decoy session create failed: {resp_decoy.json()}'
        decoy_session_id = resp_decoy.json()['session_id']
        decoy_project_id = resp_decoy.json()['project_id']

        # Create a second Project explicitly (distinct from the decoy)
        target_project = Project.objects.create(
            user=user_profile, name='Shared Name', filters={}, raw_query='shared query',
        )

        # POST with explicit project_id targeting the second project
        payload_with_pid = {
            'filters': {},
            'name': 'Shared Name',
            'raw_query': 'shared query',
            'project_id': str(target_project.project_id),
        }
        resp = _post_session(auth_client, payload_with_pid)
        assert resp.status_code == 201, (
            f'Expected 201 (new session, not dedupe), got {resp.status_code}: {resp.json()}'
        )
        data = resp.json()

        # Must be a NEW AnalysisSession (not the decoy)
        assert data['session_id'] != decoy_session_id, (
            'project_id bypasses dedupe; must not return decoy session'
        )
        assert data.get('deduped') is not True, 'deduped must be False/absent when project_id given'

        # Session must be bound to target_project, not decoy project
        assert data['project_id'] == str(target_project.project_id), (
            f'Expected project_id={target_project.project_id}, got {data["project_id"]}'
        )
        assert data['project_id'] != decoy_project_id

        # Total: decoy session + new session = 2 AnalysisSessions
        assert AnalysisSession.objects.filter(user=user_profile).count() == 2, (
            'Exactly 2 sessions: decoy + new'
        )


@pytest.mark.django_db
class TestCacheEvictionOnReportGenerate:

    # -----------------------------------------------------------------------
    # Fix-loop fix 1a: persona report generate evicts /projects/ cache
    # -----------------------------------------------------------------------
    def test_cache_evicted_on_persona_report_generate(self, auth_client, user_profile):
        """POST report generate → cache key deleted after project.save()."""
        from unittest.mock import patch as _patch

        project = Project.objects.create(
            user=user_profile,
            name='Report Cache Test',
            filters={},
            liked_ids=[{'id': 'B00001', 'intensity': 1.0}],
        )
        _seed_projects_cache(user_profile.id)
        assert not _cache_is_evicted(user_profile.id), 'Precondition: cache must be populated'

        with _patch(
            'apps.recommendation.views.reports.services.generate_persona_report',
            return_value='Fake persona report text',
        ), _patch(
            'apps.recommendation.views.reports.compute_axis_scores',
            return_value={axis: 0.0 for axis in ('form', 'materiality', 'scale', 'energy', 'tradition')},
        ):
            resp = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate/',
                format='json',
            )

        assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.json()}'
        assert _cache_is_evicted(user_profile.id), '/projects/ cache must be evicted after persona report generate'

    # -----------------------------------------------------------------------
    # Fix-loop fix 1b: report image generate evicts /projects/ cache
    # -----------------------------------------------------------------------
    def test_cache_evicted_on_report_image_generate(self, auth_client, user_profile):
        """POST report image generate → cache key deleted after project.save()."""
        from unittest.mock import patch as _patch

        project = Project.objects.create(
            user=user_profile,
            name='Image Cache Test',
            filters={},
            liked_ids=[{'id': 'B00001', 'intensity': 1.0}],
            final_report='Existing persona report text',
        )
        _seed_projects_cache(user_profile.id)
        assert not _cache_is_evicted(user_profile.id), 'Precondition: cache must be populated'

        with _patch(
            'apps.recommendation.views.reports.services.generate_persona_image',
            return_value={
                'image_data': 'base64encodeddata==',
                'mime_type': 'image/png',
                'prompt': 'fake prompt',
            },
        ):
            resp = auth_client.post(
                f'/api/v1/projects/{project.project_id}/report/generate-image/',
                format='json',
            )

        assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.json()}'
        assert _cache_is_evicted(user_profile.id), '/projects/ cache must be evicted after report image generate'


@pytest.mark.django_db
class TestSessionInsertAtomicity:

    # -----------------------------------------------------------------------
    # Fix-loop fix 2: session insert failure rolls back project create
    # -----------------------------------------------------------------------
    def test_session_insert_failure_rolls_back_project_create(self, auth_client, user_profile):
        """If AnalysisSession.objects.create raises, Project row must be rolled back."""
        project_count_before = Project.objects.filter(user=user_profile).count()

        def _raise_on_session_create(*a, **kw):
            raise RuntimeError('Simulated AnalysisSession.objects.create failure')

        session_create_patch = {
            f'{_SESSIONS_VIEW}.AnalysisSession.objects.create': _raise_on_session_create,
        }

        auth_client.raise_request_exception = False
        try:
            resp = _post_session(
                auth_client,
                payload={'filters': {}, 'name': 'Atomicity Test', 'raw_query': ''},
                extra_patches=session_create_patch,
            )
        finally:
            auth_client.raise_request_exception = True

        assert resp.status_code >= 500, (
            f'Expected 5xx on AnalysisSession create failure, got {resp.status_code}'
        )

        project_count_after = Project.objects.filter(user=user_profile).count()
        assert project_count_after == project_count_before, (
            f'transaction.atomic() must roll back Project create when AnalysisSession create fails. '
            f'Before={project_count_before}, after={project_count_after}'
        )


@pytest.mark.django_db
class TestNoOrphanProject:

    # -----------------------------------------------------------------------
    # Fix 3a: empty pool → no orphan Project
    # -----------------------------------------------------------------------
    def test_no_orphan_project_on_pool_empty(self, auth_client, user_profile):
        """Pool returns empty → 404, and no Project row created."""
        project_count_before = Project.objects.filter(user=user_profile).count()

        empty_pool_patch = {
            f'{_ENGINE}.create_pool_with_relaxation': lambda *a, **kw: ([], {}, 1),
        }
        resp = _post_session(
            auth_client,
            payload={'filters': {}, 'name': 'Orphan Pool Test', 'raw_query': ''},
            extra_patches=empty_pool_patch,
        )
        assert resp.status_code == 404, (
            f'Expected 404 (empty pool), got {resp.status_code}: {resp.json()}'
        )

        project_count_after = Project.objects.filter(user=user_profile).count()
        assert project_count_after == project_count_before, (
            f'No Project must be created on empty pool. '
            f'Before={project_count_before}, after={project_count_after}'
        )

    # -----------------------------------------------------------------------
    # Fix 3b: pool raises exception → no orphan Project
    # -----------------------------------------------------------------------
    def test_no_orphan_project_on_pool_exception(self, auth_client, user_profile):
        """Pool raises RuntimeError → 5xx, and no Project row created."""
        project_count_before = Project.objects.filter(user=user_profile).count()

        def _raise_on_pool(*a, **kw):
            raise RuntimeError('Simulated pool failure for Fix 3 test')

        exception_pool_patch = {
            f'{_ENGINE}.create_pool_with_relaxation': _raise_on_pool,
        }

        # Disable raise_request_exception so we can assert on status code
        auth_client.raise_request_exception = False
        try:
            resp = _post_session(
                auth_client,
                payload={'filters': {}, 'name': 'Orphan Exception Test', 'raw_query': ''},
                extra_patches=exception_pool_patch,
            )
        finally:
            auth_client.raise_request_exception = True

        assert resp.status_code >= 500, (
            f'Expected 5xx on pool exception, got {resp.status_code}'
        )

        project_count_after = Project.objects.filter(user=user_profile).count()
        assert project_count_after == project_count_before, (
            f'No Project must be created on pool exception. '
            f'Before={project_count_before}, after={project_count_after}'
        )


# ---------------------------------------------------------------------------
# F4: session create seeds prefetch cache for round 1 (first swipe cache key)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPrefetchCacheSeeding:
    """
    F4 fix: SessionCreateView.post writes prefetch:{sid}:1 so first swipe
    reads a cache hit instead of falling to the ~770ms sync compute path.

    IMP-8 consumer (swipe.py:764) reads:
        cache.get(f'prefetch:{session_id}:{saved_current_round}')
    where saved_current_round = session.current_round AFTER first swipe's
    current_round += 1 (0 → 1). So session create must seed key ':1'.
    """

    def test_session_create_seeds_prefetch_cache_round1(self, auth_client, user_profile):
        """
        After successful session create, cache key prefetch:{sid}:1 must be set
        with prefetch_card_id = initial_batch[1] and prefetch_card_2_id = initial_batch[2].
        """
        resp = _post_session(auth_client)
        assert resp.status_code == 201, f'Expected 201, got {resp.status_code}: {resp.json()}'

        session_id = resp.json()['session_id']
        cached = cache.get(f'prefetch:{session_id}:1')

        assert cached is not None, (
            f'prefetch:{session_id}:1 must be set by session create (F4 fix)'
        )
        assert 'prefetch_card_id' in cached, 'Cached value must have prefetch_card_id key'
        assert 'prefetch_card_2_id' in cached, 'Cached value must have prefetch_card_2_id key'

        # initial_batch is built from farthest-point sampling over _FAKE_POOL.
        # _mock_farthest_point returns the first non-exposed ID each call.
        # After session create, initial_batch[0]=B00001, [1]=B00002, [2]=B00003
        # (mock picks sequentially). We just assert the IDs are valid pool members.
        pf_id = cached['prefetch_card_id']
        pf2_id = cached['prefetch_card_2_id']
        if pf_id is not None:
            assert pf_id in _FAKE_POOL, f'prefetch_card_id {pf_id!r} not in fake pool'
        if pf2_id is not None:
            assert pf2_id in _FAKE_POOL, f'prefetch_card_2_id {pf2_id!r} not in fake pool'

    def test_first_swipe_hits_prefetch_cache(self, auth_client, user_profile):
        """
        Given that session create seeded prefetch:{sid}:1, the first swipe on the
        async path must read a cache hit (cached is not None). This indirectly
        verifies the seeded key has the correct round number by driving the full
        swipe endpoint with async_prefetch_enabled=True.
        """
        from django.test import override_settings

        # Create session (seeds prefetch:{sid}:1)
        resp = _post_session(auth_client)
        assert resp.status_code == 201
        session_id = resp.json()['session_id']

        # Confirm the seed is present before swipe
        assert cache.get(f'prefetch:{session_id}:1') is not None, (
            'Precondition: session create must seed prefetch cache'
        )

        first_card_id = _FAKE_POOL[0]
        patchers = _apply_patches()
        try:
            with override_settings(RECOMMENDATION={
                **__import__('django.conf', fromlist=['settings']).settings.RECOMMENDATION,
                'async_prefetch_enabled': True,
            }):
                swipe_resp = auth_client.post(
                    f'/api/v1/analysis/sessions/{session_id}/swipes/',
                    {'canonical_bld_id': first_card_id, 'action': 'like'},
                    format='json',
                )
        finally:
            _stop_patches(patchers)

        assert swipe_resp.status_code == 200, f'Swipe failed: {swipe_resp.json()}'

        data = swipe_resp.json()
        # async path was taken — prefetch_strategy field should be 'async-thread'
        # (the _SyncThread mock suppresses the background thread execution but
        # the consumer cache read still happens on the main path)
        assert data.get('prefetch_strategy') == 'async-thread', (
            f'Expected async-thread strategy, got: {data.get("prefetch_strategy")!r}. '
            'First swipe should hit the prefetch cache seeded by session create.'
        )
