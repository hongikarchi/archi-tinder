"""
Algorithm hyperparameter tester for the recommendation engine.
Runs in-memory simulations against real embeddings from the DB.

Usage:
    cd backend
    DJANGO_SETTINGS_MODULE=config.settings python3 tools/algorithm_tester.py \
        [--personas N] [--trials N] [--phase2-personas N] [--seed N]

Two-phase approach:
  Phase 1: Bayesian optimization (Optuna TPE) over 12 hyperparameters
  Phase 2: Validate top-10 combos with 5x more personas for statistical confidence
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

import argparse
import json
import math
import random
from datetime import datetime

import numpy as np
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning, module='sklearn')
from django.db import connection

from apps.recommendation.engine import (
    RC,
    farthest_point_from_pool,
    compute_mmr_next,
    compute_taste_centroids,
    check_convergence,
    compute_convergence,
    update_preference_vector,
    get_dislike_fallback,
)

# ── Parameter search space ───────────────────────────────────────────────────
# Continuous params: (min, max) for suggest_float
# Integer params: (min, max) for suggest_int

CONTINUOUS_PARAMS = {
    'decay_rate':            (0.01, 0.1),
    'mmr_penalty':           (0.1, 0.4),
    'convergence_threshold': (0.05, 0.15),
    'like_weight':           (0.1, 1.0),
    'dislike_weight':        (-2.0, -0.1),
}

INTEGER_PARAMS = {
    'bounded_pool_target':       (50, 300),
    'min_likes_for_clustering':  (2, 5),
    'convergence_window':        (2, 5),
    'k_clusters':                (1, 3),
    'max_consecutive_dislikes':  (5, 20),
    'initial_explore_rounds':    (5, 20),
    'top_k_results':             (10, 30),
}

# Current production values — used as first trial (baseline)
PRODUCTION_PARAMS = {
    'decay_rate':               0.05,
    'mmr_penalty':              0.3,
    'convergence_threshold':    0.08,
    'like_weight':              0.5,
    'dislike_weight':           -1.0,
    'bounded_pool_target':      150,
    'min_likes_for_clustering': 3,
    'convergence_window':       3,
    'k_clusters':               2,
    'max_consecutive_dislikes': 10,
    'initial_explore_rounds':   10,
    'top_k_results':            20,
}

# ── Persona archetypes ──────────────────────────────────────────────────────

PERSONA_MIX = [
    ('focused',     0.30),
    ('multi_modal', 0.30),
    ('broad',       0.20),
    ('strict',      0.10),
    ('noisy',       0.10),
]

ARCHETYPE_CONFIG = {
    'focused':     {'n_taste_vectors': 1, 'threshold': 0.6,  'noise_flip': 0.0},
    'multi_modal': {'n_taste_vectors': 0, 'threshold': 0.55, 'noise_flip': 0.0},  # 2-3, set dynamically
    'broad':       {'n_taste_vectors': 1, 'threshold': 0.4,  'noise_flip': 0.0},
    'strict':      {'n_taste_vectors': 1, 'threshold': 0.7,  'noise_flip': 0.0},
    'noisy':       {'n_taste_vectors': 1, 'threshold': 0.6,  'noise_flip': 0.2},
}


# ── Data loading ────────────────────────────────────────────────────────────

def load_embeddings():
    """Load all building embeddings from DB, normalize to unit length."""
    print("Loading embeddings from DB...", flush=True)
    with connection.cursor() as cur:
        cur.execute("SELECT building_id, embedding::text FROM architecture_vectors")
        rows = cur.fetchall()
    embeddings = {}
    for building_id, emb_str in rows:
        vec = np.array([float(x) for x in emb_str.strip('[]').split(',')])
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        embeddings[building_id] = vec
    print(f"Loaded {len(embeddings)} embeddings.", flush=True)
    return embeddings


# ── Persona generation ──────────────────────────────────────────────────────

def _make_single_taste_vector(all_ids, embeddings, rng):
    """Create one taste vector by averaging 1-3 random building embeddings."""
    n_samples = rng.randint(1, 3)
    sampled = rng.sample(all_ids, n_samples)
    vecs = [embeddings[bid] for bid in sampled]
    v = np.mean(vecs, axis=0)
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    return v


def generate_persona(archetype, all_ids, embeddings, rng):
    """
    Generate a persona with taste vectors and config.
    Returns dict with keys: archetype, taste_vectors (list of np.array),
    threshold, noise_flip.
    """
    config = ARCHETYPE_CONFIG[archetype]
    threshold = config['threshold']
    noise_flip = config['noise_flip']

    if archetype == 'multi_modal':
        # 2-3 separate taste vectors, each from 1-2 buildings
        n_vectors = rng.randint(2, 3)
        taste_vectors = []
        for _ in range(n_vectors):
            n_samples = rng.randint(1, 2)
            sampled = rng.sample(all_ids, n_samples)
            vecs = [embeddings[bid] for bid in sampled]
            v = np.mean(vecs, axis=0)
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            taste_vectors.append(v)
    else:
        taste_vectors = [_make_single_taste_vector(all_ids, embeddings, rng)]

    return {
        'archetype': archetype,
        'taste_vectors': taste_vectors,
        'threshold': threshold,
        'noise_flip': noise_flip,
    }


def sample_archetype(rng):
    """Sample a persona archetype based on the mix proportions."""
    archetypes, weights = zip(*PERSONA_MIX)
    return rng.choices(archetypes, weights=weights, k=1)[0]


def compute_ground_truth(taste_vectors, all_ids, embeddings, k=50):
    """
    Compute ground truth top-k buildings by cosine similarity.
    For multi-modal, use max similarity to any taste vector.
    """
    sims = []
    for bid in all_ids:
        emb = embeddings[bid]
        sim = max(float(np.dot(emb, tv)) for tv in taste_vectors)
        sims.append((bid, sim))
    sims.sort(key=lambda x: -x[1])
    return set(bid for bid, _ in sims[:k])


def persona_decides(emb, persona, rng):
    """Decide like/dislike based on persona taste vectors and threshold."""
    sim = max(float(np.dot(emb, tv)) for tv in persona['taste_vectors'])

    if persona['noise_flip'] > 0 and rng.random() < persona['noise_flip']:
        # Random flip
        return 'like' if sim <= persona['threshold'] else 'dislike'

    return 'like' if sim > persona['threshold'] else 'dislike'


# ── In-memory top-K MMR ─────────────────────────────────────────────────────

def top_k_mmr_inmemory(like_vectors, exposed_ids, pool_ids, embeddings,
                       mmr_penalty, round_num, k=10):
    """
    In-memory MMR selection for final results. No DB calls.
    Uses compute_taste_centroids for recency-weighted multi-modal centroids.
    """
    if not like_vectors:
        return []

    centroids, _ = compute_taste_centroids(like_vectors, round_num)

    exposed_set = set(exposed_ids)
    candidates = [bid for bid in pool_ids if bid in embeddings and bid not in exposed_set]
    if not candidates:
        return []

    # Score all candidates by max relevance to any centroid
    scored = []
    for bid in candidates:
        emb = embeddings[bid]
        relevance = max(float(np.dot(emb, c)) for c in centroids)
        scored.append((bid, relevance, emb))
    scored.sort(key=lambda x: -x[1])

    pool = scored[:k * 3]
    selected = []
    remaining = list(pool)

    if remaining:
        selected.append(remaining.pop(0))

    while len(selected) < k and remaining:
        best_idx = 0
        best_score = -float('inf')
        for i, (bid, _, emb) in enumerate(remaining):
            relevance = max(float(np.dot(emb, c)) for c in centroids)
            redundancy = max(
                (float(np.dot(emb, s[2])) for s in selected),
                default=0,
            )
            score = relevance - mmr_penalty * redundancy
            if score > best_score:
                best_score = score
                best_idx = i
        selected.append(remaining.pop(best_idx))

    return [bid for bid, _, _ in selected]


# ── Session simulation ──────────────────────────────────────────────────────

def simulate_session(persona, all_ids, embeddings, rng, max_swipes=50):
    """
    Simulate a full swipe session in-memory using real engine functions.
    Mirrors views.py SessionCreateView + SwipeView logic faithfully.
    Returns (top_k_ids, swipe_count).
    """
    # Pool creation: random sample of bounded_pool_target buildings
    pool_ids = list(all_ids)
    rng.shuffle(pool_ids)
    pool_ids = pool_ids[:RC['bounded_pool_target']]
    pool_emb = {bid: embeddings[bid] for bid in pool_ids if bid in embeddings}

    # Pre-compute initial batch via farthest-point sampling
    tmp_exposed = []
    initial_batch = []
    for _ in range(RC['initial_explore_rounds']):
        bid = farthest_point_from_pool(pool_ids, tmp_exposed, pool_emb)
        if bid:
            initial_batch.append(bid)
            tmp_exposed.append(bid)

    # Session state
    exposed_ids = []
    like_vectors = []
    dislike_vectors = []
    preference_vector = []
    previous_pref_vector = []
    convergence_history = []
    phase = 'exploring'
    current_round = 0
    consecutive_dislikes = 0

    swipe_count = 0
    for swipe_count in range(max_swipes):
        # Card selection by phase
        if phase == 'exploring':
            if current_round < len(initial_batch):
                next_bid = initial_batch[current_round]
            elif consecutive_dislikes >= RC['max_consecutive_dislikes']:
                # Dislike fallback: pick farthest from dislike centroid
                next_bid = get_dislike_fallback(pool_ids, exposed_ids, pool_emb, dislike_vectors)
            else:
                next_bid = farthest_point_from_pool(pool_ids, exposed_ids, pool_emb)
        elif phase == 'analyzing':
            next_bid = compute_mmr_next(
                pool_ids, exposed_ids, pool_emb, like_vectors, current_round
            )
        else:
            break

        if next_bid is None or next_bid in exposed_ids:
            break

        exposed_ids.append(next_bid)
        emb = embeddings.get(next_bid)
        if emb is None:
            current_round += 1
            continue

        # Persona decides like/dislike
        action = persona_decides(emb, persona, rng)

        # Update state
        preference_vector = update_preference_vector(preference_vector, emb.tolist(), action)

        if action == 'like':
            like_vectors.append({'embedding': emb.tolist(), 'round': current_round})
            consecutive_dislikes = 0
        else:
            dislike_vectors.append(emb.tolist())
            consecutive_dislikes += 1

        current_round += 1

        # Phase transition: exploring -> analyzing
        if phase == 'exploring' and len(like_vectors) >= RC['min_likes_for_clustering']:
            phase = 'analyzing'

        # Convergence tracking (analyzing phase, likes only)
        if phase == 'analyzing' and action == 'like' and like_vectors:
            _, global_centroid = compute_taste_centroids(like_vectors, current_round)
            centroid_list = global_centroid.tolist()
            if previous_pref_vector:
                delta_v = compute_convergence(centroid_list, previous_pref_vector)
                if delta_v is not None:
                    convergence_history.append(delta_v)
            previous_pref_vector = centroid_list

            if check_convergence(
                convergence_history,
                RC['convergence_threshold'],
                RC['convergence_window'],
            ):
                phase = 'converged'
                break

        # Pool exhaustion check
        remaining = [bid for bid in pool_ids if bid not in set(exposed_ids)]
        if not remaining:
            break

    if not like_vectors:
        return [], swipe_count + 1

    k = RC['top_k_results']
    top_k = top_k_mmr_inmemory(
        like_vectors, exposed_ids, pool_ids, embeddings,
        RC['mmr_penalty'], current_round, k=k,
    )
    return top_k, swipe_count + 1


# ── Scoring ──────────────────────────────────────────────────────────────────

def evaluate_combo(combo, personas, all_ids, embeddings, label=''):
    """
    Run simulation for all personas with a given parameter combo.
    Returns (composite_score, avg_precision, avg_swipes, std_precision, std_swipes).
    """
    import apps.recommendation.engine as eng_mod
    orig_rc = dict(eng_mod.RC)
    eng_mod.RC.update(combo)

    try:
        precisions = []
        swipe_counts = []
        k = combo.get('top_k_results', RC['top_k_results'])
        n = len(personas)

        for p_idx, (persona, ground_truth, p_rng) in enumerate(personas):
            top_k, num_swipes = simulate_session(persona, all_ids, embeddings, p_rng)
            hits = len(set(top_k) & ground_truth)
            precision = hits / k if k > 0 else 0.0
            precisions.append(precision)
            swipe_counts.append(num_swipes)

            if (p_idx + 1) % max(n // 5, 1) == 0 or p_idx == n - 1:
                print(
                    f'\r  {label} | persona {p_idx+1}/{n}',
                    end='', flush=True,
                )
    finally:
        eng_mod.RC.clear()
        eng_mod.RC.update(orig_rc)

    avg_precision = float(np.mean(precisions))
    avg_swipes = float(np.mean(swipe_counts))
    std_precision = float(np.std(precisions))
    std_swipes = float(np.std(swipe_counts))
    # Composite: precision * (target_swipes / avg_swipes). PRD target: 15 swipes.
    score = avg_precision * (15.0 / max(avg_swipes, 1))

    return score, avg_precision, avg_swipes, std_precision, std_swipes


# ── Search strategies ────────────────────────────────────────────────────────

def run_optuna(personas, all_ids, embeddings, n_trials, seed):
    """
    Bayesian optimization via Optuna TPE sampler.
    Returns list of result dicts sorted by score descending.
    """
    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        print("Optuna not installed. Run: pip install optuna")
        print("Falling back to random search.")
        return run_random_search(personas, all_ids, embeddings, n_trials, seed)

    results = []

    def objective(trial):
        params = {}
        for name, (lo, hi) in CONTINUOUS_PARAMS.items():
            params[name] = trial.suggest_float(name, lo, hi)
        for name, (lo, hi) in INTEGER_PARAMS.items():
            params[name] = trial.suggest_int(name, lo, hi)

        label = f'Trial {trial.number+1}/{n_trials}'
        score, avg_prec, avg_swipes, std_prec, std_swipes = evaluate_combo(
            params, personas, all_ids, embeddings, label
        )
        trial.set_user_attr('precision', avg_prec)
        trial.set_user_attr('avg_swipes', avg_swipes)
        trial.set_user_attr('std_precision', std_prec)

        results.append({
            'combo': dict(params),
            'score': round(score, 6),
            'precision': round(avg_prec, 4),
            'avg_swipes': round(avg_swipes, 1),
            'std_precision': round(std_prec, 4),
            'std_swipes': round(std_swipes, 1),
        })
        print(
            f'\r  Trial {trial.number+1}/{n_trials} | '
            f'score={score:.4f}  prec={avg_prec:.3f}  swipes={avg_swipes:.1f}   ',
            end='', flush=True,
        )
        return score

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction='maximize', sampler=sampler)
    # Always evaluate production defaults first as the baseline
    study.enqueue_trial(PRODUCTION_PARAMS)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    results.sort(key=lambda x: -x['score'])
    return results


def run_random_search(personas, all_ids, embeddings, n_combos, seed):
    """Fallback: random sampling from discrete param space."""
    rng = random.Random(seed)

    def random_combo():
        combo = {}
        for name, (lo, hi) in CONTINUOUS_PARAMS.items():
            combo[name] = round(rng.uniform(lo, hi), 4)
        for name, (lo, hi) in INTEGER_PARAMS.items():
            combo[name] = rng.randint(lo, hi)
        return combo

    results = []
    # Always evaluate production defaults first
    combos = [PRODUCTION_PARAMS] + [random_combo() for _ in range(n_combos - 1)]

    for combo_idx, combo in enumerate(combos):
        label = f'Combo {combo_idx+1}/{n_combos}'
        score, avg_prec, avg_swipes, std_prec, std_swipes = evaluate_combo(
            combo, personas, all_ids, embeddings, label
        )
        results.append({
            'combo': dict(combo),
            'score': round(score, 6),
            'precision': round(avg_prec, 4),
            'avg_swipes': round(avg_swipes, 1),
            'std_precision': round(std_prec, 4),
            'std_swipes': round(std_swipes, 1),
        })
        print(
            f'\r  Combo {combo_idx+1}/{n_combos} | '
            f'score={score:.4f}  prec={avg_prec:.3f}  swipes={avg_swipes:.1f}   ',
            end='', flush=True,
        )

    results.sort(key=lambda x: -x['score'])
    return results


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='ArchiTinder algorithm hyperparameter optimizer')
    parser.add_argument('--personas', type=int, default=100,
                        help='Personas per trial in phase 1 (default: 100)')
    parser.add_argument('--trials', type=int, default=200,
                        help='Optuna trials in phase 1 (default: 200)')
    parser.add_argument('--phase2-personas', type=int, default=500,
                        help='Personas for phase 2 validation (default: 500)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')
    args = parser.parse_args()

    rng = random.Random(args.seed)
    np.random.seed(args.seed)

    # Load embeddings (one DB round-trip, then all simulation is in-memory)
    embeddings = load_embeddings()
    all_ids = list(embeddings.keys())

    # ── Build phase-1 personas ───────────────────────────────────────────
    print(f"Building {args.personas} phase-1 personas...", flush=True)
    personas_p1 = []
    for i in range(args.personas):
        archetype = sample_archetype(rng)
        persona = generate_persona(archetype, all_ids, embeddings, rng)
        ground_truth = compute_ground_truth(persona['taste_vectors'], all_ids, embeddings, k=50)
        persona_rng = random.Random(args.seed + i + 1)
        personas_p1.append((persona, ground_truth, persona_rng))

    archetype_counts = {}
    for p, _, _ in personas_p1:
        archetype_counts[p['archetype']] = archetype_counts.get(p['archetype'], 0) + 1
    print(f"Archetype mix: {archetype_counts}", flush=True)

    # ── Phase 1: Bayesian optimization ──────────────────────────────────
    n_params = len(CONTINUOUS_PARAMS) + len(INTEGER_PARAMS)
    print(f"\nPhase 1: Optuna ({args.trials} trials x {args.personas} personas, {n_params} params)...",
          flush=True)

    phase1_results = run_optuna(personas_p1, all_ids, embeddings, args.trials, args.seed)

    top10_combos = phase1_results[:10]

    print("\n\n=== PHASE 1 RESULTS (top 10) ===")
    hdr = f"{'Rank':>4}  {'Score':>10}  {'Prec@K':>10}  {'AvgSwipes':>10}  {'StdPrec':>10}"
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(top10_combos):
        marker = " ← BASELINE" if r['combo'] == PRODUCTION_PARAMS else ""
        print(
            f"{i+1:>4}  {r['score']:>10.6f}  {r['precision']:>10.4f}  "
            f"{r['avg_swipes']:>10.1f}  {r['std_precision']:>10.4f}{marker}"
        )

    # ── Build phase-2 personas ───────────────────────────────────────────
    print(f"\nPhase 2: re-evaluating top 10 with {args.phase2_personas} personas...", flush=True)
    personas_p2 = []
    for i in range(args.phase2_personas):
        archetype = sample_archetype(rng)
        persona = generate_persona(archetype, all_ids, embeddings, rng)
        ground_truth = compute_ground_truth(persona['taste_vectors'], all_ids, embeddings, k=50)
        persona_rng = random.Random(args.seed + args.personas + i + 1)
        personas_p2.append((persona, ground_truth, persona_rng))

    # ── Phase 2: validation ──────────────────────────────────────────────
    phase2_results = []
    for rank, entry in enumerate(top10_combos):
        combo = entry['combo']
        label = f'Phase 2 [{rank+1:>2}/10]'
        score, avg_prec, avg_swipes, std_prec, std_swipes = evaluate_combo(
            combo, personas_p2, all_ids, embeddings, label
        )
        phase2_results.append({
            'rank_p1': rank + 1,
            'combo': combo,
            'score_p1': entry['score'],
            'score_p2': round(score, 6),
            'precision': round(avg_prec, 4),
            'avg_swipes': round(avg_swipes, 1),
            'std_precision': round(std_prec, 4),
            'std_swipes': round(std_swipes, 1),
        })
        print(
            f'\r  Phase 2 [{rank+1:>2}/10] | '
            f'score_p2={score:.4f}  prec={avg_prec:.3f}  swipes={avg_swipes:.1f}   ',
            end='', flush=True,
        )

    print()
    phase2_results.sort(key=lambda x: -x['score_p2'])

    # ── Print final results ──────────────────────────────────────────────
    print("\n=== PHASE 2 RESULTS (top 10 ranked by phase-2 score) ===")
    hdr2 = f"{'Rank':>4}  {'ScoreP2':>10}  {'ScoreP1':>10}  {'Prec@K':>10}  {'AvgSwipes':>10}  {'StdPrec':>10}"
    print(hdr2)
    print("-" * len(hdr2))
    for i, r in enumerate(phase2_results):
        print(
            f"{i+1:>4}  {r['score_p2']:>10.6f}  {r['score_p1']:>10.6f}  "
            f"{r['precision']:>10.4f}  {r['avg_swipes']:>10.1f}  {r['std_precision']:>10.4f}"
        )

    # ── Recommended settings ─────────────────────────────────────────────
    print("\n=== RECOMMENDED SETTINGS ===")
    best = phase2_results[0]['combo']
    for param in sorted(best.keys()):
        orig_val = PRODUCTION_PARAMS.get(param, '---')
        changed = ' ← CHANGED' if best[param] != orig_val else ''
        print(f"  {param:<32} {best[param]}  (current: {orig_val}){changed}")

    # ── Baseline comparison ──────────────────────────────────────────────
    baseline = next((r for r in phase2_results if r['combo'] == PRODUCTION_PARAMS), None)
    if baseline:
        best_score = phase2_results[0]['score_p2']
        improvement = ((best_score / max(baseline['score_p2'], 1e-9)) - 1) * 100
        print(f"\nBaseline score: {baseline['score_p2']:.6f} "
              f"(prec={baseline['precision']:.4f}, swipes={baseline['avg_swipes']:.1f})")
        print(f"Best score:     {best_score:.6f} "
              f"(prec={phase2_results[0]['precision']:.4f}, "
              f"swipes={phase2_results[0]['avg_swipes']:.1f})")
        print(f"Improvement:    {improvement:+.1f}%")

    # ── Write JSON results ───────────────────────────────────────────────
    out_path = os.path.join(os.path.dirname(__file__), 'optimization_results.json')
    output = {
        'args': vars(args),
        'timestamp': datetime.now().isoformat(),
        'production_params': PRODUCTION_PARAMS,
        'phase1_top10': top10_combos,
        'phase2_results': phase2_results,
    }
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == '__main__':
    main()
