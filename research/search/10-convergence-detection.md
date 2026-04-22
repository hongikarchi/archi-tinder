# Convergence Detection Robustness: Delta-V Moving Average vs Kalman / CUSUM / Change-Point

## Status
Ready for Implementation

## Question
archi-tinder detects "taste convergence" via a Delta-V moving-average on K-Means centroid drift with ε=0.08 across a window of 3. Is this the most robust approach, or should it be replaced with a Kalman filter, a change-point method (CUSUM, PELT, BOCD), or a Bayesian credible-interval approach, given a session horizon of 15-25 swipes (≈3-15 likes) and jittery centroids?

## TL;DR
- **The current detector is under-engineered, but the frontier methods (PELT, BOCD, full Bayesian) are sample-starved at N≤15.** Change-point literature assumes N ≥ 30-100; our analyzing-phase window is 3-15 *likes*. Recommending BOCD here would be theatre.
- **Two structural bugs matter more than the algorithm choice.** (i) `views.py:539-557` only appends Delta-V on `action == 'like'` — the "window of 3" is 3 likes, not 3 rounds, silently stretching to 5-10 rounds of wall time. (ii) `convergence_history` is not reset on the exploring→analyzing phase transition (`views.py:568-570`), so the first analyzing-phase Delta-V compares a K-Means centroid against the prior preference vector — a cross-metric distance with no physical meaning.
- **Recommendation**: ship a two-part upgrade, both flag-gated: (A) **patience-style early-stopping** — require `K=3` consecutive sub-threshold Delta-V observations with a `min_delta` floor (Prechelt 1998), replacing the moving-average mean (which masks a single dip below ε); (B) **1-D Kalman filter on Delta-V** — cheap, gives posterior variance for free, so convergence fires only when *mean + 1.96·σ < ε*, eliminating spurious single-sample trips. Both <40-line patches, zero new deps (numpy only).
- **Defer / reject**: CUSUM (our moving average already is a degenerate CUSUM; asymmetric-shift framing adds little at N=15), PELT / Bayesian Online Change Detection (require ≥30-100 samples), full posterior "probability user still exploring" (warranted only once we log enough sessions for a hyperprior).
- The structural bug fix (phase-transition reset + dislike-aware counter) is a non-negotiable precondition for any detector — pure noise floor matters more than filter math.

## Context (Current State)

Detector implementation, two files, two gating points:

- `backend/apps/recommendation/engine.py:576-599` — `compute_convergence()` is `float(np.linalg.norm(current - previous))` (unnormalized L2, despite the `research/algorithm.md:58-63` spec which shows a *relative* form `|Δc| / |c_prev|`). `check_convergence()` takes `np.mean(history[-window:]) < threshold`.
- `backend/apps/recommendation/views.py:539-557` — **the Delta-V append is gated by `action == 'like'` inside `phase == 'analyzing'`**. Dislikes in analyzing produce no history entry at all. In exploring, every swipe (like or dislike) contributes a pref-vector Delta-V.
- `views.py:568-570` — at like-count ≥ `min_likes_for_clustering` (3), phase flips exploring → analyzing. **`convergence_history` is not cleared.** The first analyzing swipe therefore computes `||K-Means_centroid - pref_vector||` — apples-to-oranges.
- `backend/config/settings.py:136-137` — `convergence_threshold=0.08`, `convergence_window=3`.
- `views.py:439` — the only reset of `convergence_history` is on user-initiated left-swipe of the Action Card.
- Empirical: 89.5% completion rate, but most completions are Action-Card-accept — not pure detector firings. We have no measurement of the detector's false-positive / false-negative rate in isolation.

Noise sources feeding the signal:
1. **K-Means `n_init=3`, `random_state=42`** (`engine.py:481`): deterministic initialization — jitter comes from the inputs, not the algorithm. Every new like perturbs every prior weight via `w_i = exp(-γ·(round - round_i))` (γ=0.05), so the centroid moves even when the "taste" is stable. This is expected signal and unavoidable noise mixed.
2. **k=2 on 3-5 points** (see `research/search/06-clustering-alternatives.md`): high centroid variance at low N; the single-point "cluster" centroid *is* the embedding. Any k-jitter round-to-round becomes raw noise in Delta-V.
3. **Dislikes invisible**: centroids are cached on dislike rounds (`engine.py:464`), so centroid-based Delta-V would be zero — but the append gate means zeros never enter the history anyway.

## Findings

### 1. Change-point detection literature is built for N≫15

A 2017 survey across 200+ change-point methods ([Aminikhanghahi & Cook 2017](https://link.springer.com/article/10.1007/s10115-016-0987-z)) notes that Bayesian and kernel methods require substantial observation windows for the posterior to concentrate. PELT ([Killick, Fearnhead & Eckley 2012, *JASA*](https://www.tandfonline.com/doi/abs/10.1080/01621459.2012.737745)) is O(n) in the best case but its penalty term (BIC-style) implicitly assumes enough data to invert an information matrix — degrades to "detect nothing" or "detect every point" at N<30 depending on the penalty scalar. Bayesian Online Change Detection ([Adams & MacKay 2007, arXiv:0710.3742](https://arxiv.org/abs/0710.3742)) models a run-length posterior; at N=3-15 the posterior is dominated by the hazard-rate hyperprior — you are measuring your prior, not the data. These methods are strong at N=100-10000 industrial monitoring time series. They are the wrong tool at our horizon.

### 2. CUSUM is what we're already doing, badly

Page's CUSUM ([Page 1954, *Biometrika*](https://www.jstor.org/stable/2333009)) maintains a running sum of (signal - reference) and triggers when it crosses a threshold. A 3-sample moving average of Delta-V *is* a windowed degenerate CUSUM with reference mean = 0 and threshold = ε×window. The two legitimate CUSUM improvements over the current code — (a) asymmetric one-sided shift detection, (b) the h/k parameter tuning against a target false-alarm rate — both require an estimate of the pre-change mean and the target shift size. At 15-25 swipes per session we cannot estimate either from the session itself; we would need offline calibration across many sessions. Plausible as a future upgrade, premature today.

### 3. Kalman 1-D on Delta-V is the natural fit at this scale

A Kalman filter's prior-carried estimate is exactly the feature we need for small-N robustness ([Welch & Bishop 2006, "An Introduction to the Kalman Filter"](https://www.cs.unc.edu/~welch/media/pdf/kalman_intro.pdf)). Model Delta-V as a 1-D state with process noise `Q` and measurement noise `R`:

```
x_k|k-1 = x_k-1|k-1                    # constant-mean model
P_k|k-1 = P_k-1|k-1 + Q
K_k = P_k|k-1 / (P_k|k-1 + R)
x_k|k = x_k|k-1 + K_k · (delta_v_k - x_k|k-1)
P_k|k = (1 - K_k) · P_k|k-1
converged := (x_k|k + 1.96·sqrt(P_k|k)) < threshold
```

Choose `Q ≈ 0.001` (slow drift), `R ≈ 0.005` (K-Means jitter std, estimable from session-log simulation). This gives (i) a smoothed Delta-V estimate that tolerates single-sample spikes or dips, (ii) a confidence interval for free, so convergence fires only when the *upper bound* is sub-threshold. At N=3 the posterior is dominated by the `Q/R` ratio (prior). At N=10 it has converged to the data. ~15 lines of numpy, no sklearn needed. Graceful at small N because the filter is exactly *designed* for the Q/R-prior-dominates-at-small-N regime.

### 4. Early-stopping patience is the cheap match for our UX

Prechelt's classic early-stopping survey ([Prechelt 1998, "Early Stopping — But When?" in *Neural Networks: Tricks of the Trade*](https://link.springer.com/chapter/10.1007/3-540-49430-8_3)) defines three rule families for gradient-training monitors that translate directly to our setting: **GL** (generalization loss threshold), **PQ** (progress quotient), and **UP** (consecutive rounds of up-trend). The UP rule — "stop if the metric fails to improve for K consecutive steps" — is routinely shipped in Keras (`EarlyStopping(patience=K, min_delta=δ)`), PyTorch Lightning, and PyTorch Ignite. Translated: "converge only if Delta-V has been below ε for `patience=3` consecutive likes, with `min_delta=0.01` between checks." Predictable, debuggable, zero-hyperparameter surprise. It is weaker than Kalman at noise-rejection (no uncertainty band) but stronger on interpretability — the product surface already has a "patience" metaphor at the UI layer (left-swipe the Action Card to keep going).

### 5. The first-order bugs: phase-transition reset and dislike counting

The advisor-verified issues in our current code are not filter-quality issues; they are **signal-integrity issues**:

- **Cross-metric mixing at phase transition.** `previous_pref_vector` holds the pref_vector during exploring and the K-Means global_centroid during analyzing. Those two live in the same vector space but are *different physical quantities*: one is a sum-L2-normalized running average (slow-moving, high inertia), the other is a recency-weighted weighted-mean-L2-normalized centroid (fast-moving at low N). Delta-V across that boundary is nonsense. Fix: `convergence_history = []; previous_pref_vector = []` on the exploring→analyzing transition.
- **Hidden window stretch.** Because Delta-V is only appended on likes in analyzing phase, `window=3` means 3 likes — at a 30% like rate that's ≈10 swipes of wall time. Users experience a long silent stretch before the Action Card fires. Either document this, or make the window round-indexed with a "Delta-V=0 on centroid-unchanged" entry on dislikes (which the check_convergence would then treat as converged). The latter is dangerous without care.
- **Unit inconsistency vs the spec.** `research/algorithm.md:58-63` specifies `delta_V = ||c_now - c_prev|| / ||c_prev||` (*relative* drift). Code uses absolute L2. On L2-normalized centroids both denominators are 1, so the values are numerically equal; but the spec-code drift is a maintenance hazard.

## Options

### Option A — Keep moving average, fix the two bugs
Reset `convergence_history` on phase transition; document dislike-gating explicitly; leave ε=0.08 and window=3 as-is.
- Pros: Minimal risk; restores the signal integrity the detector implicitly assumed.
- Cons: Does nothing about single-sample dip sensitivity or noise at low N.
- Complexity: **Trivial** (~10 lines).
- Expected impact: Small on metrics, positive on maintainability.

### Option B — Patience + min_delta (Prechelt UP rule)
Replace `np.mean(last_k) < ε` with "K consecutive Delta-V observations each < ε, with |Δ_k - Δ_k-1| < min_delta". Recommended `K=3, min_delta=0.01, ε=0.08`.
- Pros: Single-dip-resistant; well-understood in ML tooling; mirrors the UI "patience" metaphor.
- Cons: No uncertainty estimate; still fires on 3 lucky likes in a row at N=3-5.
- Complexity: **Low** (~20 lines in `engine.py:590-599`).
- Expected impact: Medium — fewer false positives at mid-session.

### Option C — 1-D Kalman filter on Delta-V with credible-interval gating (recommended)
Maintain posterior mean `x` and variance `P` over Delta-V; converge when `x + 1.96·sqrt(P) < ε`.
- Pros: Graceful at N=3 (prior-dominated); graceful at N=15 (data-dominated); uncertainty band rejects spikes; telemetrable (log `P` per session to characterize noise floor).
- Cons: Requires `Q, R` tuning — must come from an offline simulation of observed Delta-V across logged sessions (or bootstrap from algorithm_tester personas).
- Complexity: **Low-Medium** (~30 lines + one Optuna-style calibration pass).
- Expected impact: Largest quality win; gives us a foundation for data-driven threshold tuning.

### Option D — Bayesian Online Change Detection (deferred)
Full BOCD on the Delta-V time series with a geometric hazard prior.
- Pros: Principled; gives full posterior over change point.
- Cons: Sample-starved at our N; hyperprior dominates; implementation is ~100 lines.
- Complexity: **High**.
- Expected impact: Indistinguishable from Option C at N<15 by construction.

## Recommendation

**Ship Option A first as a bug fix (no flag — the cross-metric mixing is indefensible), then ship Option C behind `KALMAN_CONVERGENCE_ENABLED` with Option B as a strictly-simpler fallback keyed by the same flag's absence.**

Concretely:

1. **A (unconditional)**: in `views.py:568-570`, on exploring→analyzing transition, clear `convergence_history = []` and `previous_pref_vector = []`. Document the dislike-gating behaviour in `engine.py:590-599` docstring.
2. **B (behind `EARLY_STOP_PATIENCE_ENABLED=True` as intermediate)**: new `check_convergence_patience(history, threshold, patience, min_delta)` in `engine.py`. Safe as a default for the next release if C calibration lags.
3. **C (behind `KALMAN_CONVERGENCE_ENABLED`)**: maintain `session.kalman_state = {'x': float, 'P': float}` (new JSON field on `AnalysisSession`); update per-like in analyzing phase; gate convergence on `x + 1.96·sqrt(P) < threshold`. Calibrate `Q, R` by running `algorithm_tester.py` across 100 personas and fitting to the empirical Delta-V distribution.
4. **Algo-tester validation gate**: do NOT roll out C until it shows (a) ≥ baseline completion rate, (b) ≤ baseline median swipes-to-convergence on converging sessions, and (c) no degradation in persona-reported top-K precision.

Defer Option D. Revisit when we have 1K+ logged sessions and can characterize the Delta-V prior empirically (at that point BOCD with an informed hyperprior becomes viable).

## Open Questions

- **What is the empirical Delta-V distribution across sessions?** Without this we can only calibrate `Q, R` (Option C) and `min_delta` (Option B) from synthetic personas. A tiny telemetry change — log per-swipe `delta_v` into a table — unblocks data-driven choice of every threshold here.
- **Should dislikes contribute a Delta-V=0 sample?** Currently gated out. Adding zeros would (i) make the window round-indexed not like-indexed, (ii) bias the moving average down — converging faster, good or bad depending on UX goals. Needs A/B.
- **Phase-1 exploring convergence check is vestigial.** Exploring phase uses pref_vector Delta-V, but the phase exits on `like_count ≥ min_likes_for_clustering`, not on convergence. Is the exploring-phase `convergence_history` even consumed anywhere before the transition reset recommended above? If not, Option A can simplify further by computing `convergence_history` only in analyzing phase.
- **Pool-exhaustion path** (`views.py:579-582`) forces convergence regardless of detector state. Should we attribute those to "forced convergence" vs "detected convergence" in telemetry to separate detector-quality from coverage-quality?
- **Relative vs absolute Delta-V.** Spec says relative, code does absolute. On L2-normalized centroids these agree, but *if* we switch to un-normalized centroids anywhere (e.g. soft-assignment changes from topic 06), they diverge. Align or explicitly acknowledge.

## Proposed Tasks for Main Terminal

All backend; no frontend changes.

1. **BACK-CONV-1** — `views.py:568-570`: on exploring→analyzing transition, set `session.convergence_history = []; session.previous_pref_vector = []`. Include in `save(update_fields=...)`. Add a unit test asserting the first analyzing-phase Delta-V is computed centroid-to-centroid (not centroid-to-pref_vector).
2. **BACK-CONV-2** — `engine.py:590-599`: expand `check_convergence()` docstring with dislike-gating behaviour ("`window` measures likes in analyzing phase, not rounds"). Add `assert window <= len(history)` comment.
3. **BACK-CONV-3** — `engine.py`: add `check_convergence_patience(history, threshold, patience=3, min_delta=0.01)` implementing Prechelt UP rule. Behind `settings.RECOMMENDATION.get('EARLY_STOP_PATIENCE_ENABLED', False)`.
4. **BACK-CONV-4** — `apps/recommendation/models.py:AnalysisSession`: add `kalman_state = models.JSONField(default=dict)` and a migration. Stores `{'x': float, 'P': float}`.
5. **BACK-CONV-5** — `engine.py`: add `update_kalman(state, delta_v, Q, R)` returning new `{'x', 'P'}`, and `check_convergence_kalman(state, threshold, z=1.96)`. Behind `KALMAN_CONVERGENCE_ENABLED=False`.
6. **BACK-CONV-6** — `views.py:572-576`: flag-multiplexed convergence check. Fallback order: Kalman → Patience → Moving-Average.
7. **BACK-CONV-7** — `config/settings.py`: add `EARLY_STOP_PATIENCE_ENABLED`, `KALMAN_CONVERGENCE_ENABLED` (both `False`), `kalman_process_noise_Q` (default 0.001), `kalman_measurement_noise_R` (default 0.005), `patience_k` (3), `patience_min_delta` (0.01).
8. **TEST-CONV-1** — `backend/tests/test_convergence.py`: parameterized tests across moving-average / patience / Kalman for three scenarios: (i) clean converging signal, (ii) single-spike mid-convergence, (iii) slowly drifting no-convergence. Assert algorithm-specific expected outcomes.
9. **ALGO-CONV-1** — `backend/tools/algorithm_tester.py`: add a Kalman-calibration mode. Run 100 personas with raw Delta-V logged; fit empirical `R` (measurement noise std) and choose `Q` to maintain a 2-3 like smoothing horizon. Emit recommended `Q, R` values.
10. **TELEM-CONV-1** — Log `delta_v`, `kalman_x`, `kalman_P`, and `phase` per swipe to a lightweight `SwipeConvergenceLog` table. Enables post-hoc calibration and false-positive rate measurement.

## Sources

- [Page 1954, "Continuous Inspection Schemes", *Biometrika*](https://www.jstor.org/stable/2333009) — CUSUM origin.
- [Killick, Fearnhead & Eckley 2012, "Optimal Detection of Changepoints with a Linear Computational Cost", *JASA*](https://www.tandfonline.com/doi/abs/10.1080/01621459.2012.737745) — PELT.
- [Adams & MacKay 2007, "Bayesian Online Changepoint Detection", arXiv:0710.3742](https://arxiv.org/abs/0710.3742) — BOCD.
- [Welch & Bishop 2006, "An Introduction to the Kalman Filter", UNC TR 95-041](https://www.cs.unc.edu/~welch/media/pdf/kalman_intro.pdf) — canonical Kalman tutorial.
- [Prechelt 1998, "Early Stopping — But When?"](https://link.springer.com/chapter/10.1007/3-540-49430-8_3) — UP/GL/PQ early-stopping rules.
- [Aminikhanghahi & Cook 2017, "A Survey of Methods for Time Series Change Point Detection", *Knowl. Inf. Syst.*](https://link.springer.com/article/10.1007/s10115-016-0987-z) — scale-of-N context.
- [Keras `EarlyStopping` API](https://keras.io/api/callbacks/early_stopping/) — patience+min_delta as shipped ML tooling norm.
- [research/search/06-clustering-alternatives.md](06-clustering-alternatives.md) — upstream N=3-15, D=384 sample-starvation framing; why K-Means jitter is unavoidable at our scale.
- [research/algorithm.md §Convergence Detection](../algorithm.md) — spec (relative Delta-V form) vs code (absolute) discrepancy noted here.
