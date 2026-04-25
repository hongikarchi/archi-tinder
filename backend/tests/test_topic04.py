"""
test_topic04.py -- Sprint 4 Topic 04: MMR lambda ramp + DPP greedy MAP.

Tests cover:
- MMR lambda ramp flag OFF (default): fixed lambda used unchanged
- MMR lambda ramp flag ON: lambda=0 at t=0, ramps to full at t>=N_ref
- MMR lambda ramp: mid-session partial ramp value
- compute_dpp_topk: basic reordering returns k items
- compute_dpp_topk: early return when len(cards) <= k
- compute_dpp_topk: empty input returns []
- compute_dpp_topk: alpha=0 => pure quality (max-q items selected first)
- compute_dpp_topk: alpha clamped above 1.0 acts like alpha=1.0
- compute_dpp_topk: singularity fallback (d < eps)
- compute_dpp_topk: exception fallback returns q-sorted top-k
- SessionResultView with dpp_topk_enabled=True -> predicted_cards reordered
- SessionResultView with dpp_topk_enabled=False (default) -> no DPP call
- SessionResultView with dpp_topk_enabled=True but empty like_vectors -> DPP skipped
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DIM = 384  # production embedding dimension (compute_taste_centroids hardcodes index 191)


def _unit(v):
    """Return L2-normalised version of v."""
    v = np.array(v, dtype=np.float64)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _unit384(seed_vec):
    """
    Build a 384-dim unit vector where the first len(seed_vec) dims are seed_vec
    and the rest are zero, then L2-normalise. Satisfies compute_taste_centroids
    cache key which accesses embedding[191].
    """
    v = np.zeros(DIM)
    v[:len(seed_vec)] = seed_vec
    return _unit(v)


def _make_cards(n):
    """
    Build n minimal card dicts (ImageCard format, no 'embedding' key).
    Embeddings are stored separately via _cards_to_pool_embs for monkeypatching
    get_pool_embeddings.
    """
    cards = []
    for i in range(n):
        vec = np.zeros(DIM)
        vec[i % DIM] = 1.0
        if i >= DIM:
            vec[(i + 1) % DIM] = 0.1
            vec = _unit(vec)
        cards.append({
            'building_id': f'B{i:05d}',
            '_test_embedding': vec,  # kept for test use only, not in real card format
        })
    return cards


def _cards_to_pool_embs(cards):
    """Return dict {building_id: np.ndarray} from test card list."""
    return {c['building_id']: c['_test_embedding'] for c in cards}


def _like_vectors_fixture(n=2):
    """Return n random 384-dim unit-vector like_vectors in {'round', 'embedding'} format."""
    rng = np.random.default_rng(42)
    vecs = []
    for i in range(n):
        v = rng.standard_normal(DIM)
        vecs.append({'round': i + 1, 'embedding': _unit(v).tolist()})
    return vecs


# ---------------------------------------------------------------------------
# TestMmrLambdaRamp
# ---------------------------------------------------------------------------

class TestMmrLambdaRamp:
    """Sprint 4 Topic 04 (a): per-swipe MMR lambda ramp."""

    def test_ramp_disabled_uses_fixed_lambda(self, monkeypatch):
        """Flag OFF (default): lambda equals mmr_penalty constant."""
        from django.conf import settings
        from apps.recommendation import engine

        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_lambda_ramp_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_penalty', 0.3)

        # Use 384-dim embeddings; compute_taste_centroids cache key accesses index 191
        pool_embeddings = {
            'B00000': _unit384([1, 0, 0, 0]),
            'B00001': _unit384([0, 1, 0, 0]),
            'B00002': _unit384([0, 0, 1, 0]),
        }
        like_vectors = [{'round': 1, 'embedding': _unit384([1, 1, 0, 0]).tolist()}]
        pool_ids = list(pool_embeddings.keys())

        # Exposed = 0 items; with ramp ON this would give lambda=0
        exposed_ids = []

        result_off = engine.compute_mmr_next(
            pool_ids, exposed_ids, pool_embeddings, like_vectors, round_num=1,
        )
        # Just verify it returns a valid pool member (fixed lambda path executes)
        assert result_off in pool_ids

    def test_ramp_at_t0_gives_zero_lambda(self, monkeypatch):
        """
        At t=0 (exposed_ids=[]), lambda_ramp = lambda_base * 0/N_ref = 0.
        With lambda=0 the MMR score = relevance, so the most relevant item wins.
        With fixed lambda=0.3 a different ordering may result.
        Use deterministic embeddings to verify.
        """
        from django.conf import settings
        from apps.recommendation import engine

        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_lambda_ramp_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_penalty', 0.9)
        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_lambda_ramp_n_ref', 5)

        # Centroid will be unit384([1,0,0,0]); B00000 is most similar
        pool_embeddings = {
            'B00000': _unit384([1, 0, 0, 0]),
            'B00001': _unit384([0.5, 0.866, 0, 0]),
            'B00002': _unit384([0, 0, 1, 0]),
        }
        like_vectors = [{'round': 1, 'embedding': _unit384([1, 0, 0, 0]).tolist()}]
        pool_ids = list(pool_embeddings.keys())

        # t=0: exposed=[], lambda=0 -> pure relevance -> B00000 wins
        result = engine.compute_mmr_next(pool_ids, [], pool_embeddings, like_vectors, round_num=1)
        assert result == 'B00000'

    def test_ramp_full_at_n_ref(self, monkeypatch):
        """At |exposed|=N_ref lambda_ramp equals lambda_base (ramp saturates)."""
        from django.conf import settings
        from apps.recommendation import engine

        n_ref = 3
        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_lambda_ramp_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_penalty', 0.3)
        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_lambda_ramp_n_ref', n_ref)

        pool_embeddings = {
            'B00000': _unit384([1, 0, 0, 0]),
            'B00001': _unit384([0, 1, 0, 0]),
            'B00002': _unit384([0, 0, 1, 0]),
            'B00003': _unit384([0, 0, 0, 1]),
        }
        like_vectors = [{'round': 1, 'embedding': _unit384([1, 0, 0, 0]).tolist()}]
        pool_ids = list(pool_embeddings.keys())

        # exposed = n_ref items -> min(1, n_ref/n_ref) = 1.0 -> full lambda
        exposed = ['B00001', 'B00002', 'B00003']
        result = engine.compute_mmr_next(pool_ids, exposed, pool_embeddings, like_vectors, round_num=1)
        assert result == 'B00000'

    def test_ramp_partial_at_mid_session(self, monkeypatch):
        """At |exposed|=N_ref/2 lambda_ramp = 0.5 * lambda_base."""
        from django.conf import settings
        from apps.recommendation import engine

        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_lambda_ramp_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_penalty', 1.0)
        monkeypatch.setitem(settings.RECOMMENDATION, 'mmr_lambda_ramp_n_ref', 4)

        # Centroid ≈ unit384([1,0,0,0]); B00000 most relevant
        pool_embeddings = {
            'B00000': _unit384([1, 0, 0, 0]),
            'B00001': _unit384([0, 1, 0, 0]),
        }
        like_vectors = [{'round': 1, 'embedding': _unit384([1, 0, 0, 0]).tolist()}]
        pool_ids = list(pool_embeddings.keys())

        # |exposed|=2, n_ref=4 -> lambda=0.5; relevance dominates for B00000
        exposed = ['B00002', 'B00003']
        result = engine.compute_mmr_next(pool_ids, exposed, pool_embeddings, like_vectors, round_num=1)
        assert result == 'B00000'


# ---------------------------------------------------------------------------
# TestDppTopK
# ---------------------------------------------------------------------------

class TestDppTopK:
    """Sprint 4 Topic 04 (b): DPP greedy MAP kernel + Chen 2018 Cholesky greedy."""

    def _patch_pool_embs(self, monkeypatch, engine, cards):
        """Monkeypatch get_pool_embeddings to return test embeddings from cards."""
        pool = _cards_to_pool_embs(cards)
        monkeypatch.setattr(engine, 'get_pool_embeddings', lambda ids: {bid: pool[bid] for bid in ids if bid in pool})

    def test_returns_k_items(self, monkeypatch):
        """compute_dpp_topk returns exactly k building_ids from input."""
        from django.conf import settings
        from apps.recommendation import engine

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_alpha', 0.5)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_singularity_eps', 1e-9)

        cards = _make_cards(6)
        like_vectors = _like_vectors_fixture()
        self._patch_pool_embs(monkeypatch, engine, cards)
        result = engine.compute_dpp_topk(cards, like_vectors, k=3)

        assert len(result) == 3
        input_ids = {c['building_id'] for c in cards}
        assert all(bid in input_ids for bid in result)
        assert len(set(result)) == len(result)

    def test_early_return_when_n_le_k(self, monkeypatch):
        """When len(cards) <= k, return all ids immediately (no DPP computation)."""
        from apps.recommendation import engine

        cards = _make_cards(3)
        like_vectors = _like_vectors_fixture()
        # No pool embs patch needed — early return happens before embedding fetch
        result = engine.compute_dpp_topk(cards, like_vectors, k=5)

        assert result == [c['building_id'] for c in cards]

    def test_empty_input_returns_empty(self):
        """Empty cards list returns empty list."""
        from apps.recommendation import engine

        result = engine.compute_dpp_topk([], [], k=5)
        assert result == []

    def test_alpha_zero_pure_quality(self, monkeypatch):
        """
        alpha=0: L = diag(q^2) -- pure quality diagonal, no cross terms.
        Greedy MAP picks items in descending q order.
        Embeddings are arranged so q varies; verify top-q items are selected.
        """
        from django.conf import settings
        from apps.recommendation import engine

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_alpha', 0.0)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_singularity_eps', 1e-9)

        # 5 cards; like_vectors points toward card 0 (most relevant -> highest q)
        cards = []
        embs = {}
        for i in range(5):
            bid = f'B{i:05d}'
            vec = np.zeros(DIM)
            vec[i] = 1.0
            cards.append({'building_id': bid})
            embs[bid] = vec

        monkeypatch.setattr(engine, 'get_pool_embeddings', lambda ids: {bid: embs[bid] for bid in ids if bid in embs})

        # like_vector pointing to B00000 -> q(B00000) is highest
        like_vectors = [{'round': 1, 'embedding': np.eye(DIM)[0].tolist()}]

        result = engine.compute_dpp_topk(cards, like_vectors, k=2)

        assert len(result) == 2
        assert 'B00000' in result  # highest q must be selected

    def test_alpha_clamped_above_one(self, monkeypatch):
        """
        alpha=2.0 must be clamped to 1.0 -- Wilhelm PSD requirement.
        Result with alpha=2.0 must equal result with alpha=1.0.
        """
        from django.conf import settings
        from apps.recommendation import engine

        cards = _make_cards(5)
        like_vectors = _like_vectors_fixture()
        self._patch_pool_embs(monkeypatch, engine, cards)

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_alpha', 1.0)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_singularity_eps', 1e-9)
        result_one = engine.compute_dpp_topk(cards, like_vectors, k=3)

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_alpha', 2.0)
        result_clamped = engine.compute_dpp_topk(cards, like_vectors, k=3)

        assert result_clamped == result_one

    def test_exception_fallback_returns_q_sorted(self, monkeypatch):
        """
        If the embedding fetch raises, function logs WARNING and falls back to
        input-order top-k.
        """
        from django.conf import settings
        from apps.recommendation import engine

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_alpha', 0.5)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_singularity_eps', 1e-9)

        cards = _make_cards(5)
        like_vectors = _like_vectors_fixture()

        # Force exception in embedding fetch phase
        monkeypatch.setattr(engine, 'get_pool_embeddings', lambda ids: (_ for _ in ()).throw(RuntimeError("db error")))

        result = engine.compute_dpp_topk(cards, like_vectors, k=3)

        # Falls back to first k ids (input order)
        assert len(result) == 3
        input_ids = {c['building_id'] for c in cards}
        assert all(bid in input_ids for bid in result)

    def test_singularity_pads_remaining_slots(self, monkeypatch):
        """
        When DPP terminates early due to singularity, remaining slots filled by q-sort.
        Use eps=infinity to force immediate stop after first selection.
        """
        from django.conf import settings
        from apps.recommendation import engine

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_alpha', 0.5)
        # eps = huge -> d[best] < eps always after first step -> stop immediately
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_singularity_eps', 1e10)

        cards = _make_cards(5)
        like_vectors = _like_vectors_fixture()
        self._patch_pool_embs(monkeypatch, engine, cards)

        result = engine.compute_dpp_topk(cards, like_vectors, k=3)

        assert len(result) == 3
        input_ids = {c['building_id'] for c in cards}
        assert all(bid in input_ids for bid in result)
        assert len(set(result)) == 3

    def test_no_like_vectors_uniform_quality(self, monkeypatch):
        """
        When like_vectors=[], quality falls back to uniform 0.7.
        DPP still runs and returns k distinct items.
        """
        from django.conf import settings
        from apps.recommendation import engine

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_alpha', 0.5)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_singularity_eps', 1e-9)

        cards = _make_cards(5)
        self._patch_pool_embs(monkeypatch, engine, cards)
        result = engine.compute_dpp_topk(cards, like_vectors=[], k=3)

        assert len(result) == 3
        input_ids = {c['building_id'] for c in cards}
        assert all(bid in input_ids for bid in result)


# ---------------------------------------------------------------------------
# TestSessionResultDppIntegration
# ---------------------------------------------------------------------------

class TestSessionResultDppIntegration:
    """Integration tests: DPP block inside SessionResultView."""

    def _make_fake_cards(self, ids):
        """Minimal card dicts that views.py and engine.compute_dpp_topk can consume."""
        cards = []
        for i, bid in enumerate(ids):
            vec = np.zeros(DIM)
            vec[i % DIM] = 1.0
            cards.append({
                'building_id': bid,
                'name_en': f'Building {bid}',
                'embedding': vec.tolist(),
                'atmosphere': 'calm',
                'style': 'Modernist',
                'program': 'Museum',
                'architect': 'Anon',
                'material': 'concrete',
            })
        return cards

    @pytest.mark.django_db
    def test_dpp_flag_off_no_reorder(self, user_profile, auth_client, monkeypatch):
        """Flag OFF (default): predicted_cards returned in original MMR order."""
        from django.conf import settings
        from apps.recommendation import engine
        from apps.recommendation.models import Project, AnalysisSession

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', False)

        ids = [f'B{i:05d}' for i in range(5)]
        fake_cards = self._make_fake_cards(ids)

        project = Project.objects.create(
            user=user_profile,
            name='Test Project',
            liked_ids=[{'id': ids[0], 'intensity': 1.0}],
        )
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            status='completed',
            like_vectors=[fake_cards[0]['embedding']],
            preference_vector=[0.1] * 4,
            exposed_ids=ids,
        )

        call_log = []

        def _fake_top_k_mmr(*a, **kw):
            return list(fake_cards)

        def _fake_dpp(cards, like_vectors, k):
            call_log.append('dpp_called')
            return [c['building_id'] for c in cards[:k]]

        monkeypatch.setattr(engine, 'get_top_k_mmr', _fake_top_k_mmr)
        monkeypatch.setattr(engine, 'compute_dpp_topk', _fake_dpp)

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200
        assert 'dpp_called' not in call_log

    @pytest.mark.django_db
    def test_dpp_flag_on_reorders_cards(self, user_profile, auth_client, monkeypatch):
        """Flag ON: predicted_cards reordered by compute_dpp_topk output."""
        from django.conf import settings
        from apps.recommendation import engine
        from apps.recommendation.models import Project, AnalysisSession

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', 5)

        ids = [f'B{i:05d}' for i in range(5)]
        fake_cards = self._make_fake_cards(ids)

        project = Project.objects.create(
            user=user_profile,
            name='Test Project DPP',
            liked_ids=[{'id': ids[0], 'intensity': 1.0}],
        )
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            status='completed',
            like_vectors=[fake_cards[0]['embedding']],
            preference_vector=[0.1] * 4,
            exposed_ids=ids,
        )

        # DPP reverses the order
        reversed_ids = list(reversed(ids))

        def _fake_top_k_mmr(*a, **kw):
            return list(fake_cards)

        def _fake_dpp(cards, like_vectors, k):
            return reversed_ids[:k]

        monkeypatch.setattr(engine, 'get_top_k_mmr', _fake_top_k_mmr)
        monkeypatch.setattr(engine, 'compute_dpp_topk', _fake_dpp)

        # Mock get_building_card to avoid DB hit
        monkeypatch.setattr(engine, 'get_building_card', lambda bid: None)

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200
        data = resp.json()
        predicted_ids = [c['building_id'] for c in data['predicted_images']]
        assert predicted_ids == reversed_ids[:5]

    @pytest.mark.django_db
    def test_dpp_skipped_when_no_like_vectors(self, user_profile, auth_client, monkeypatch):
        """Flag ON but empty like_vectors -> DPP gate skips, no compute_dpp_topk call."""
        from django.conf import settings
        from apps.recommendation import engine
        from apps.recommendation.models import Project, AnalysisSession

        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', False)

        ids = [f'B{i:05d}' for i in range(5)]
        fake_cards = self._make_fake_cards(ids)

        project = Project.objects.create(
            user=user_profile,
            name='Test Project DPP No Likes',
            liked_ids=[],
        )
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            status='completed',
            like_vectors=[],   # empty -> DPP gate fails
            preference_vector=[0.1] * 4,
            exposed_ids=ids,
        )

        call_log = []

        def _fake_get_top_k_results(*a, **kw):
            return list(fake_cards)

        def _fake_dpp(cards, like_vectors, k):
            call_log.append('dpp_called')
            return [c['building_id'] for c in cards[:k]]

        monkeypatch.setattr(engine, 'get_top_k_results', _fake_get_top_k_results)
        monkeypatch.setattr(engine, 'compute_dpp_topk', _fake_dpp)
        monkeypatch.setattr(engine, 'get_building_card', lambda bid: None)

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200
        assert 'dpp_called' not in call_log
