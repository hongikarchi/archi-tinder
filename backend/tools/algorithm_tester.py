"""
Algorithm hyperparameter tester for the recommendation engine.
Runs in-memory simulations against real embeddings from the DB.

Usage:
    cd backend
    DJANGO_SETTINGS_MODULE=config.settings python3 tools/algorithm_tester.py \
        [--personas N] [--combos N] [--phase2-personas N] [--seed N]
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
    check_convergence,
    compute_taste_centroids,
    compute_convergence,
    update_preference_vector,
)

# ── Parameter search space (discrete values) ────────────────────────────────

PARAM_SPACE = {
    'decay_rate':              [0.01, 0.03, 0.05, 0.1],
    'mmr_penalty':             [0.1, 0.2, 0.3, 0.4],
    'convergence_threshold':   [0.05, 0.08, 0.1, 0.15],
    'like_weight':             [0.2, 0.5, 1.0],
    'dislike_weight':          [-0.3, -1.0, -2.0],
    'bounded_pool_target':     [100, 150, 200],
    'min_likes_for_clustering': [2, 3, 5],
    'k_clusters':              [1, 2, 3],
    'convergence_window':      [2, 3, 5],
    'initial_explore_rounds':  [5, 10, 15],
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


# ── In-memory top-10 MMR ────────────────────────────────────────────────────

def top_k_mmr_inmemory(like_vectors, exposed_ids, pool_ids, embeddings,
                       mmr_penalty, round_num, k=10):
    """
    In-memory MMR selection for final results. No DB calls.
    Uses compute_taste_centroids for centroids.
    """
    if not like_vectors:
        return []

    centroids, global_centroid = compute_taste_centroids(like_vectors, round_num)

    # Score all pool candidates (not just unexposed -- final results consider full pool)
    candidates = [bid for bid in pool_ids if bid in embeddings]
    if not candidates:
        return []

    # Compute relevance for all candidates
    scored = []
    for bid in candidates:
        emb = embeddings[bid]
        relevance = max(float(np.dot(emb, c)) for c in centroids)
        scored.append((bid, relevance, emb))
    scored.sort(key=lambda x: -x[1])

    # Take top 3*k for re-ranking
    pool = scored[:k * 3]

    selected = []
    remaining = list(pool)

    # First item: best relevance
    if remaining:
        selected.append(remaining.pop(0))

    # Greedy MMR
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

def simulate_session(persona, all_ids, embeddings, rng, max_swipes=30):
    """
    Simulate a full swipe session in-memory using real engine functions.
    Returns (top10_ids, swipe_count).
    """
    pool_ids = list(all_ids)
    rng.shuffle(pool_ids)
    pool_ids = pool_ids[:RC['bounded_pool_target']]
    pool_emb = {bid: embeddings[bid] for bid in pool_ids if bid in embeddings}

    exposed_ids = []
    like_vectors = []
    preference_vector = []
    previous_pref_vector = []
    convergence_history = []
    phase = 'exploring'
    current_round = 0

    # Pre-compute initial batch using farthest-point sampling
    tmp_exposed = []
    initial_batch = []
    for _ in range(RC['initial_explore_rounds']):
        bid = farthest_point_from_pool(pool_ids, tmp_exposed, pool_emb)
        if bid:
            initial_batch.append(bid)
            tmp_exposed.append(bid)

    swipe_count = 0
    for swipe_count in range(max_swipes):
        # Card selection by phase
        if phase == 'exploring':
            if current_round < len(initial_batch):
                next_bid = initial_batch[current_round]
            else:
                next_bid = farthest_point_from_pool(pool_ids, exposed_ids, pool_emb)
        elif phase == 'analyzing':
            next_bid = compute_mmr_next(
                pool_ids, exposed_ids, pool_emb, like_vectors, current_round
            )
        elif phase == 'converged':
            break
        else:
            break

        if next_bid is None:
            break

        if next_bid in exposed_ids:
            break

        exposed_ids.append(next_bid)
        emb = embeddings.get(next_bid)
        if emb is None:
            current_round += 1
            continue

        # Persona decides like/dislike
        action = persona_decides(emb, persona, rng)

        # Update state
        if action == 'like':
            like_vectors.append({'embedding': emb.tolist(), 'round': current_round})
            preference_vector = update_preference_vector(
                preference_vector, emb.tolist(), action
            )
        else:
            preference_vector = update_preference_vector(
                preference_vector, emb.tolist(), action
            )

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

        # Pool exhaustion check
        remaining = [bid for bid in pool_ids if bid not in set(exposed_ids)]
        if not remaining:
            break

    if not like_vectors:
        return [], swipe_count + 1

    # Compute top-10 results using in-memory MMR
    top10 = top_k_mmr_inmemory(
        like_vectors, exposed_ids, pool_ids, embeddings,
        RC['mmr_penalty'], current_round, k=10
    )
    return top10, swipe_count + 1


# ── Parameter combo sampling ────────────────────────────────────────────────

def random_combo(rng):
    """Sample a random parameter combo from the discrete search space."""
    combo = {}
    for param, values in PARAM_SPACE.items():
        combo[param] = rng.choice(values)
    return combo


# ── Scoring ─────────────────────────────────────────────────────────────────

def evaluate_combo(combo, personas, all_ids, embeddings, combo_idx, n_combos, phase_label):
    """
    Run simulation for all personas with a given combo.
    Returns (score, avg_precision, avg_swipes, std_precision, std_swipes).
    """
    import apps.recommendation.engine as eng_mod
    orig_rc = dict(eng_mod.RC)
    eng_mod.RC.update(combo)

    try:
        precisions = []
        swipe_counts = []
        n = len(personas)
        for p_idx, (persona, ground_truth, p_rng) in enumerate(personas):
            top10, num_swipes = simulate_session(persona, all_ids, embeddings, p_rng)
            hits = len(set(top10) & ground_truth)
            precision = hits / 10.0
            precisions.append(precision)
            swipe_counts.append(num_swipes)

            if (p_idx + 1) % max(n // 10, 1) == 0 or p_idx == n - 1:
                print(
                    f'\r  {phase_label}: combo {combo_idx+1}/{n_combos} | '
                    f'persona {p_idx+1}/{n}',
                    end='', flush=True,
                )
    finally:
        eng_mod.RC.clear()
        eng_mod.RC.update(orig_rc)

    avg_precision = float(np.mean(precisions))
    avg_swipes = float(np.mean(swipe_counts))
    std_precision = float(np.std(precisions))
    std_swipes = float(np.std(swipe_counts))
    score = avg_precision * (20.0 / max(avg_swipes, 1))

    return score, avg_precision, avg_swipes, std_precision, std_swipes


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Algorithm hyperparameter tester')
    parser.add_argument('--personas', type=int, default=200,
                        help='Number of personas per combo in phase 1')
    parser.add_argument('--combos', type=int, default=200,
                        help='Number of random parameter combos to test')
    parser.add_argument('--phase2-personas', type=int, default=1000,
                        help='Number of personas for phase 2 validation')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility')
    args = parser.parse_args()

    rng = random.Random(args.seed)
    np.random.seed(args.seed)

    # Load embeddings
    embeddings = load_embeddings()
    all_ids = list(embeddings.keys())

    # ── Build phase 1 personas ───────────────────────────────────────────
    print(f"Building {args.personas} phase-1 personas...", flush=True)
    personas_p1 = []
    for i in range(args.personas):
        archetype = sample_archetype(rng)
        persona = generate_persona(archetype, all_ids, embeddings, rng)
        ground_truth = compute_ground_truth(persona['taste_vectors'], all_ids, embeddings, k=50)
        persona_rng = random.Random(args.seed + i + 1)
        personas_p1.append((persona, ground_truth, persona_rng))

    # ── Phase 1: screening ───────────────────────────────────────────────
    print(f"\nPhase 1: evaluating {args.combos} combos x {args.personas} personas...", flush=True)
    phase1_results = []

    for combo_idx in range(args.combos):
        combo = random_combo(rng)
        score, avg_prec, avg_swipes, std_prec, std_swipes = evaluate_combo(
            combo, personas_p1, all_ids, embeddings, combo_idx, args.combos, 'Phase 1'
        )
        phase1_results.append({
            'combo': combo,
            'score': round(score, 6),
            'precision': round(avg_prec, 4),
            'avg_swipes': round(avg_swipes, 1),
            'std_precision': round(std_prec, 4),
            'std_swipes': round(std_swipes, 1),
        })
        print(
            f'\r  Phase 1: combo {combo_idx+1}/{args.combos} | '
            f'score={score:.4f}  prec={avg_prec:.3f}  swipes={avg_swipes:.1f}   ',
            end='', flush=True,
        )

    print()

    # Sort by score descending
    phase1_results.sort(key=lambda x: -x['score'])
    top10_combos = phase1_results[:10]

    # Print phase 1 top 10
    print("\n=== PHASE 1 RESULTS (top 10 combos) ===")
    hdr = f"{'Rank':>4}  {'Score':>10}  {'Prec@10':>10}  {'AvgSwipes':>10}  {'StdPrec':>10}  {'StdSwipes':>10}"
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(top10_combos):
        print(
            f"{i+1:>4}  {r['score']:>10.6f}  {r['precision']:>10.4f}  "
            f"{r['avg_swipes']:>10.1f}  {r['std_precision']:>10.4f}  {r['std_swipes']:>10.1f}"
        )

    # ── Build phase 2 personas ───────────────────────────────────────────
    print(f"\nPhase 2: re-evaluating top 10 with {args.phase2_personas} personas...", flush=True)
    print(f"Building {args.phase2_personas} phase-2 personas...", flush=True)
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
        score, avg_prec, avg_swipes, std_prec, std_swipes = evaluate_combo(
            combo, personas_p2, all_ids, embeddings, rank, 10, 'Phase 2'
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
            f'\r  Phase 2: [{rank+1:>2}/10] '
            f'score_p2={score:.4f}  prec={avg_prec:.3f}  swipes={avg_swipes:.1f}   ',
            end='', flush=True,
        )

    print()

    # Sort phase 2 by score
    phase2_results.sort(key=lambda x: -x['score_p2'])

    # ── Print results ────────────────────────────────────────────────────
    print("\n=== PHASE 2 RESULTS (top 10 combos ranked by phase-2 score) ===")
    hdr = f"{'Rank':>4}  {'ScoreP2':>10}  {'ScoreP1':>10}  {'Prec@10':>10}  {'AvgSwipes':>10}  {'StdPrec':>10}"
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(phase2_results):
        print(
            f"{i+1:>4}  {r['score_p2']:>10.6f}  {r['score_p1']:>10.6f}  "
            f"{r['precision']:>10.4f}  {r['avg_swipes']:>10.1f}  {r['std_precision']:>10.4f}"
        )

    # Print recommended settings
    print("\n=== RECOMMENDED SETTINGS ===")
    best = phase2_results[0]['combo']
    orig_rc = dict(RC)
    for param in sorted(best.keys()):
        if param in PARAM_SPACE:
            orig_val = orig_rc.get(param, '---')
            print(f"  {param:<32} {best[param]}  (current: {orig_val})")

    # ── Write results to JSON ────────────────────────────────────────────
    out_path = os.path.join(os.path.dirname(__file__), 'optimization_results.json')
    output = {
        'args': vars(args),
        'timestamp': datetime.now().isoformat(),
        'phase1_top10': top10_combos,
        'phase2_results': phase2_results,
    }
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == '__main__':
    main()
