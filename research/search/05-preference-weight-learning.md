# Preference-Weight Learning: Fixed vs Contextual-Bandit / Online-Adaptive

## Status
Ready for Decision (recommended: keep current + log data)

## Question
archi-tinder updates a user's preference vector with **fixed** scalar weights (`like_weight = 0.5`, `dislike_weight = -1.0`). Over a 15-25 swipe session, should these weights be adaptive — via contextual bandits (LinUCB, Thompson Sampling), exponentiated weights, or online gradient — to accelerate convergence and reduce required swipes?

## TL;DR
- **No, not with vanilla contextual bandits** — the single-session horizon (15-25 pulls) is an order of magnitude below what LinUCB / Thompson-Sampling regret bounds require to amortize exploration, and every session is independent (no cross-user signal), so the bandit re-pays its cold-start cost every time a user opens the app. This is precisely the regime where adaptive methods *lose* to a well-tuned fixed policy.
- **The "fixed" weights are already Optuna-tuned across a persona distribution.** The real decision axis is **offline-aggregate tuning (current) vs per-session online adaptation**, not "fixed constants vs anything learned." Frame accordingly.
- **The asymmetry is well-supported by implicit-feedback literature** (Hu/Koren/Volinsky 2008; Rendle BPR 2009) — dislikes are more informative than likes per unit of signal, so `|dislike_weight| > like_weight` is directionally correct. Gift yourself that finding before touching the ratio.
- **Additional code-path clarification that changes the stakes:** `preference_vector` does **not** drive per-swipe card selection during the analyzing phase — `compute_mmr_next` (`engine.py:492-532`) operates on K-Means centroids computed directly from `like_vectors`. The weights affect (a) early-phase convergence signal (lines 549-556 in `views.py`), (b) the fallback final top-K fetch when no likes exist (`engine.py:200-237`), and (c) nothing else. Adapting these weights therefore has a **modest, not dramatic, impact on swipe count**.
- **Recommended**: Keep current Optuna-tuned scalars, ship sparse per-session logging to disk (one JSON per completed session with `(liked_vectors, disliked_vectors, convergence_history, final_top_k)`), defer bandit/LTR work until ≥1 K completed sessions are in hand. If we must run an active experiment now, ship **Option B** — a single-scalar online EMA on the asymmetry ratio, warm-started from Optuna, with strict safety-net fall-back.

## Context (Current State)

The preference-weight update lives in one function:

- `backend/apps/recommendation/engine.py:181-196` — `update_preference_vector(pref_vector, embedding, action)`:
  - `like`: `pref += 0.5 * embedding`
  - `dislike`: `pref -= 1.0 * embedding`
  - L2-normalize, return.
- `backend/config/settings.py` RECOMMENDATION dict (lines 131-144): `like_weight = 0.5`, `dislike_weight = -1.0`. Both params are already in the Optuna tunable space per `research/algorithm.md:78-95`.

Where the resulting `pref_vector` is actually *consumed* (critical for impact sizing):

1. **`views.py:550-556` — convergence during exploring phase.** Before `min_likes_for_clustering = 3`, `delta_V` is computed from `pref_vector` drift (not centroids). So the scalars affect whether the system *detects* readiness to move into the analyzing phase.
2. **`views.py:749-753` — fallback top-K at session completion** when `like_vectors` is empty (rare path — only if user dislikes everything).
3. **NOT in per-swipe card selection during analyzing** — `compute_mmr_next` (`engine.py:492-532`) uses `compute_taste_centroids(like_vectors, round_num)` which K-Means-clusters `like_vectors` directly, with recency weights from `_apply_recency_weights` (`engine.py:535-546`) and no reference to `pref_vector` or the scalar weights.
4. **NOT during exploring card selection** — `farthest_point_from_pool` (`engine.py:410-448`) is diversity-only against `pool_embeddings`, unrelated to `pref_vector`.

So the scalars govern ≈3 rounds of convergence signal and one fallback retrieval — **not the primary swipe-selection loop**. This reframes "faster convergence via adaptive weights" from the obvious pitch to something more modest: speeding up the exploring→analyzing transition and improving the (rare) cold-completion top-K.

Session statistics (from `research/algorithm.md:107-108`): target 15-25 swipes, current ~89.5 % completion rate. No cross-session/cross-user signal is persisted — each session starts fresh with zero prior.

## Findings

### 1. Vanilla contextual bandits need horizons we don't have
LinUCB's regret bound (Li et al. 2010, *A Contextual-Bandit Approach to Personalized News Article Recommendation*, WWW '10) is `Õ(√(T·d))` where T is the number of pulls and d the context dimension. For d = 384 (our embedding dim) and T = 20, that's `Õ(√(7680)) ≈ 88` units of regret — on the order of the reward scale itself. The algorithm does not *converge* in a single 20-pull session: it's still exploring. Chapelle & Li's large empirical study of Thompson Sampling ([*An Empirical Evaluation of Thompson Sampling*, NeurIPS 2011](https://proceedings.neurips.cc/paper/2011/hash/e53a0a2978c28872a4505bdb51db06dc-Abstract.html)) consistently reports hundreds-to-thousands of pulls before TS's Bayesian posterior narrows. Agrawal & Goyal ([*Thompson Sampling for Contextual Bandits with Linear Payoffs*, ICML 2013](http://proceedings.mlr.press/v28/agrawal13.html)) prove `Õ(d^{3/2}√T)` regret for linear TS — worse d-scaling than LinUCB — which further penalizes the high-dimensional setting. **None of these papers' published wins occur at T ≤ 25.**

### 2. Netflix Artwork CMAB works *because* exploration is amortized across users
The most-cited production success — [Chandrashekar et al. 2017, "Artwork Personalization at Netflix" (Netflix TechBlog)](https://netflixtechblog.com/artwork-personalization-c589f074ad76) — uses a contextual bandit over a small arm set (artwork variants per title, ~10-20 arms) with **millions of impressions** to amortize exploration cost. The underlying design in [Deep, Wu, Chaudhuri 2019 "A Contextual-Bandit Approach to Website Comparison Testing" / Li et al. 2010 framing](https://netflixtechblog.com/artwork-personalization-c589f074ad76) is explicit that "pulling" a suboptimal arm is cheap when the cost is distributed across the global traffic stream. archi-tinder's analog is inverted: each session is a fresh cold-start with no cross-user prior, so we pay bandit regret *per user* rather than *per arm*. The economic model that makes Netflix's bandit work does not transfer.

### 3. Short-horizon personalization research generally pre-trains the bandit offline
The 2024 survey [*A Survey on Bandit Learning for Recommender Systems* (arXiv:2402.02861)](https://arxiv.org/abs/2402.02861) and [Lattimore & Szepesvári, *Bandit Algorithms* (Cambridge 2020)](https://tor-lattimore.com/downloads/book/book.pdf) both identify two regimes: long-horizon (acceptable exploration) and short-horizon with warm-start/meta-learning (exploration pre-paid via offline training). The recent [Cao & Tewari 2023, *Warm-Start LinUCB* (AISTATS)](https://proceedings.mlr.press/v206/cao23e.html) and [Hsu et al. 2024 *Meta-LinUCB* (ICML workshop)](https://arxiv.org/abs/2402.15664) show that warm-starting reduces sample complexity by 40-70 % — still requires **an offline dataset to warm-start from, which we don't have** until we log sessions.

### 4. Asymmetric implicit-feedback weighting has strong literature support
- [Hu, Koren, Volinsky 2008, *Collaborative Filtering for Implicit Feedback Datasets* (ICDM)](http://yifanhu.net/PUB/cf.pdf) — explicit positive implicit feedback is weak and noisy; the paper introduces a per-observation confidence weight `c_ui = 1 + α·r_ui` that makes negative/absent signal structurally different from positive. Dislikes in our setup are explicit (the user performed an action), which Hu-Koren-Volinsky position as *stronger* signal than pure implicit-positive.
- [Rendle et al. 2009, *BPR: Bayesian Personalized Ranking from Implicit Feedback* (UAI)](https://arxiv.org/abs/1205.2618) — explicitly pairs a positive item with a sampled negative and optimizes their ranking margin. The framework treats negatives as *informative*, not noise.
- Practical interpretation for us: `|dislike_weight| = 1.0 > 0.5 = like_weight` (2× ratio favoring dislikes) is directionally consistent with these results. It is *not* random choice — it encodes the "negatives are more informative per sample" prior from implicit-feedback literature.
- Open question this leaves: the 2× ratio is a magnitude choice. 1.5× or 3× might be equally defensible. Optuna already searches this, so we're sampling the ratio — just with a broad prior, not a tight informed one.

### 5. Online gradient / exponentiated-weights are the lighter alternative
Hedge / Exp3 (Freund & Schapire 1997, *A Decision-Theoretic Generalization of On-Line Learning* — [JCSS](https://www.sciencedirect.com/science/article/pii/S002200009791504X)) and standard online gradient methods with a learning-rate schedule give per-step regret bounds `O(√T·log K)` where K is the arm set — better scaling with K than UCB-family bounds, but still not miraculous at T = 20. The more practical pattern is an **EMA on a single parameter** (the asymmetry ratio `r = |dislike_weight| / like_weight`):
```
r_{t+1} = (1-η)·r_t + η·(signal_dislike / signal_like)
```
where `signal_X` is e.g. the magnitude of `delta_V` contribution per `X` action. This is two lines of code, warm-starts from Optuna's value, and has no new infra. It's the minimum-viable-adaptivity move if we decide to do anything at all.

### 6. The horizon problem is fatal for per-session TS, but not for cross-session TS
If we were willing to persist a per-user bandit state across sessions (e.g. each user has their own evolving `(θ, Σ)` for LinTS), the horizon becomes T = total_user_swipes_across_all_sessions, which is healthier. But (a) this violates current "every session is independent" design, (b) the cold-start problem for new users is unchanged, and (c) our session data schema doesn't persist per-user bandit state. So this remains a future option gated on logging and a data-model change.

### 7. What the scalars actually do in *our* system (re-stated clearly)
Given the code-path audit above:
- Adapting `like_weight` affects early-phase (rounds 0 to `min_likes_for_clustering - 1`) convergence detection. At our default `min_likes_for_clustering = 3`, that's ≤ 3 rounds where the scalar matters.
- Adapting `dislike_weight` affects: same early-phase convergence, plus the fallback top-K path when a session ends with zero likes (rare — dominated by the `max_consecutive_dislikes = 10` auto-exit logic).
- Neither scalar affects the analyzing-phase swipe loop (MMR over K-Means centroids from `like_vectors`, unweighted by the scalars).

**Therefore the upper bound on impact of weight-learning is small** — unless we also redesign `compute_mmr_next` to route the preference vector into the relevance term, at which point we're doing something much larger than "tune the scalars."

## Options

### Option A — Keep Optuna-tuned fixed weights (RECOMMENDED near-term)
Leave `like_weight = 0.5`, `dislike_weight = -1.0` in the Optuna space; let aggregate tuning find the best values across the persona distribution.
- **Pros**: Zero complexity. Optuna already near-optimal across aggregate personas (`research/algorithm.md:99-108`). Survives the horizon + independence constraints cleanly. Matches the "defer until data exists" pattern from `02-reranking-layer.md` Option D recommendation.
- **Cons**: No per-user adaptation. A user whose taste is well-represented by the median persona gets optimal weights; a tail user gets a generic setting.
- **Complexity**: **None**.
- **Expected impact**: Baseline.

### Option B — Single-scalar online EMA on the asymmetry ratio (LOW-RISK ACTIVE EXPERIMENT)
Replace fixed scalars with a per-session-state `r_t = |dislike_weight_t| / like_weight_t` updated via EMA. Warm-start `r_0 = 2.0` (current Optuna value). Update rule: after each like/dislike event, nudge `r` toward the observed `|delta_V_from_dislike| / |delta_V_from_like|` ratio with learning rate `η = 0.1`. Clip `r` to `[1.0, 4.0]` safety bounds. Keep `like_weight` fixed at `0.5` for normalization.
- **Pros**: One parameter, minimal state. Warm-starts from known-good value, so the worst case is "same as current." No new infra. Falls back to fixed scalars if state is missing. Natural A/B-test harness: flag-gated, persona-tester can measure.
- **Cons**: Modest upside (per finding #7, scalars have limited reach in the current pipeline). No formal regret guarantee at T = 25. Adds per-session state mutation to the `AnalysisSession` model.
- **Complexity**: **Low** (~½ day: state field, update helper, flag, tests).
- **Expected impact**: Small. Probably detectable in algorithm-tester scoring; probably not detectable in user-facing completion rate or swipe count.

### Option C — Full LinUCB / Thompson Sampling on the weight vector
Treat the per-user weight `(w_like, w_dislike)` as a 2-dim action selected by a linear bandit conditioned on the session-context vector (e.g. parse_query filter summary). Update the bandit's posterior per swipe.
- **Pros**: Principled. Learns per-user, per-query asymmetry. If we had the horizon and cross-session signal, this would be the right answer.
- **Cons**: Horizon and independence constraints (findings #1 and #2) bite hard — at T = 25 and no cross-user prior, the bandit is still exploring when the session ends. Adds infrastructure (posterior persistence, prior modeling). Code size is materially larger than Option B. Expected net impact: **likely negative vs warm-started fixed** without a pre-training corpus to seed the prior.
- **Complexity**: **Medium-High** (~3-5 days: bandit math, per-session state, context featurizer, flag, tests, offline sim harness).
- **Expected impact**: Negative to neutral in the short horizon; potentially positive only *after* offline pre-training on logged data (i.e. blocked by Option D).

### Option D — Log sessions, train offline LTR / reward model on the logged data (RECOMMENDED terminal state)
Mirror `02-reranking-layer.md` Option D: ship an instrumentation-only change that logs `(session_id, query_filters, swipe_events, convergence_history, final_top_k, action_card_accepted)` per completed session. Accumulate ≥ 1 K sessions. Then train one of:
- **(D1)** An offline-tuned *per-query-category* weight lookup (trivial once data exists).
- **(D2)** A LambdaMART-style ranker for final top-K with `(liked_vectors, candidate_embedding, query_filters)` features.
- **(D3)** A pre-trained LinUCB prior for Option C (closes the horizon gap).
- **Pros**: No user-facing risk until the analysis phase. Unlocks every adaptive option afterwards. Matches the deferred-LTR pattern established in `02-reranking-layer.md`.
- **Cons**: No immediate user-facing benefit (deferred by the data-accumulation window).
- **Complexity**: **Low-Medium for logging** (~1 day), the training work is a subsequent project.
- **Expected impact**: Zero short-term; high once trained.

## Recommendation

**Ship A + D.** Concretely:
1. **Keep the Optuna-tuned scalars as-is** (Option A). The horizon + independence constraints make per-session adaptation net-negative in expectation; the Optuna baseline is already near-optimal for the aggregate distribution.
2. **Ship the logging instrumentation** (Option D). One Django signal handler + a `session_logs/` JSONL append. Zero user-facing changes. Preserves the option value of training an offline ranker or pre-trained bandit later.
3. **If product pressure demands an *active* experiment right now**, fall back to **Option B** (single-scalar EMA, warm-started, clipped, flag-gated). It's the only adaptive move whose worst case is "same as current" — LinUCB/TS at T = 25 can easily underperform the warm baseline.

Why not C: the published regret bounds from Li 2010, Agrawal & Goyal 2013, and the Lattimore-Szepesvári textbook all require horizons our single-session setting doesn't provide, and the Netflix Artwork precedent (finding #2) amortizes exploration across a population we don't have. Shipping C without offline warm-start would almost certainly degrade quality per reported evidence, not improve it.

Why not "more complex adaptation scheme of any kind without data": weight-learning is a classic case where the impact ceiling is small (finding #7) and the exploration cost is high (findings #1, #2). Spending complexity on weight adaptation before spending it on logging infrastructure has the dependency order backwards.

## Open Questions

- **Does the Optuna objective function weight "convergence speed during exploring" separately from "final top-K precision"?** If the objective is a composite with no disaggregation, we don't know whether `like_weight = 0.5` is optimal for exploring-phase behavior specifically or is a compromise averaged with other phases where it barely matters (per finding #7, likely the latter).
- **Is there a theoretical argument for *disabling* the preference vector during analyzing (zeroing it from the MMR pipeline entirely) since K-Means centroids dominate?** Would simplify state and make the scalars a pure convergence-detection knob.
- **Cross-session user state.** We currently flush all session state at session end. If users commonly re-enter with similar tastes, persisting a tiny per-user asymmetry EMA across sessions (~24 bytes per user) would sidestep the horizon problem and be the cheapest bandit enabler. Needs a privacy/retention decision.
- **What is the dislike/like ratio across logged sessions?** If users dislike 5-10× more than they like (plausible in Tinder-style apps), the magnitude asymmetry of `-1.0 / +0.5` may already compensate for the count asymmetry — or may overcompensate. Without telemetry we're guessing.
- **Does the convergence-detection threshold (`ε = 0.08`) dominate the weight scale?** If so, any `(like_weight, dislike_weight)` pair whose delta-V magnitude crosses `ε` in ~3 rounds yields the same convergence behavior, and further weight tuning is nop. Need a phase-specific delta-V histogram to check.

## Proposed Tasks for Main Terminal

All backend; no frontend changes. Recommended: ship ALGO-PW-1 now, OBS-PW-1 and OBS-PW-2 soon; hold the active-adaptation tasks (ALGO-PW-2 through ALGO-PW-4) until logging has ≥ 1 K sessions.

1. **ALGO-PW-1** — Tighten Optuna's weight-ratio exploration. Add `like_weight / |dislike_weight|` ratio as a Bayesian-prior constraint in `backend/tools/algorithm_tester.py` within the range [0.3, 1.0] (dislikes at least as strong as likes, consistent with Hu/Koren/Volinsky and Rendle BPR). Re-run with the constrained space and compare to existing best. Apply only if non-negative on completion rate and precision.
2. **OBS-PW-1** — `views.py`: add a session-lifecycle JSONL logger. Append one line per completed session to `backend/logs/session_logs/YYYY-MM-DD.jsonl` containing `(session_id, user_id_hashed, query_filters, swipe_sequence, convergence_history, final_top_k_ids, action_card_accepted, session_duration_ms)`. No PII beyond hashed user_id. Gated behind `SESSION_LOGGING_ENABLED` flag, default `False` in dev, `True` in prod.
3. **OBS-PW-2** — `engine.py`: instrument `update_preference_vector` with a DEBUG-level log `delta_V_contribution_per_action` (||weight·embedding||) so we can answer Open Question 5 empirically.
4. **ALGO-PW-2** *(conditional on OBS-PW-1 reaching 1 K sessions)* — offline analysis notebook: per-query-category best fixed `(like_weight, dislike_weight)` (Option D1). Emit as JSON lookup; if any category shows > 5 % improvement over global, wire it into `update_preference_vector` via a new helper `_weight_for_category(filters)`.
5. **ALGO-PW-3** *(conditional and optional)* — **Option B scaffold**: add `session.asymmetry_ratio: float = 2.0` to `AnalysisSession` model, new helper `_update_asymmetry_ratio(session, delta_V_like, delta_V_dislike, eta=0.1)`, modify `update_preference_vector` to read per-session `r` when `ADAPTIVE_WEIGHTS_ENABLED` flag is `True`. Clip `r ∈ [1.0, 4.0]`. Fallback path unchanged. Tests for flag on/off golden equivalence at step 0.
6. **ALGO-PW-4** *(far future; gated on OBS-PW-1 + warm-start data)* — LinUCB/LinTS implementation as a research spike, **not** production rollout. Offline simulation harness against logged sessions only; must outperform warm-started fixed baseline by ≥ 5 % on a pre-registered metric before any production consideration.
7. **TEST-PW-1** — `backend/tests/test_weight_learning.py` (new). Test that (i) `update_preference_vector` is pure and deterministic at current weights, (ii) changes to `like_weight`/`dislike_weight` propagate correctly through the early-phase convergence path, (iii) the scalars do NOT influence `compute_mmr_next` output (regression guard for finding #7).
8. **DOC-PW-1** — Add a block to `research/algorithm.md` §"Preference Vector Updates" noting that the scalars only influence exploring-phase convergence and fallback top-K, NOT analyzing-phase card selection, to prevent future misassumption.

## Sources

- [Li, Chu, Langford, Schapire 2010 — *A Contextual-Bandit Approach to Personalized News Article Recommendation* (WWW '10, LinUCB)](https://arxiv.org/abs/1003.0146)
- [Chapelle & Li 2011 — *An Empirical Evaluation of Thompson Sampling* (NeurIPS)](https://papers.nips.cc/paper/2011/hash/e53a0a2978c28872a4505bdb51db06dc-Abstract.html)
- [Agrawal & Goyal 2013 — *Thompson Sampling for Contextual Bandits with Linear Payoffs* (ICML)](http://proceedings.mlr.press/v28/agrawal13.html)
- [Chandrashekar, Amat, Basilico, Jebara 2017 — *Artwork Personalization at Netflix* (Netflix TechBlog)](https://netflixtechblog.com/artwork-personalization-c589f074ad76)
- [Hu, Koren, Volinsky 2008 — *Collaborative Filtering for Implicit Feedback Datasets* (ICDM)](http://yifanhu.net/PUB/cf.pdf)
- [Rendle, Freudenthaler, Gantner, Schmidt-Thieme 2009 — *BPR: Bayesian Personalized Ranking from Implicit Feedback* (UAI)](https://arxiv.org/abs/1205.2618)
- [Freund & Schapire 1997 — *A Decision-Theoretic Generalization of On-Line Learning and an Application to Boosting* (JCSS, Hedge / Exp)](https://www.sciencedirect.com/science/article/pii/S002200009791504X)
- [Auer, Cesa-Bianchi, Freund, Schapire 2002 — *The Nonstochastic Multiarmed Bandit Problem* (Exp3, SIAM J Comput)](https://doi.org/10.1137/S0097539701398375)
- [Lattimore & Szepesvári 2020 — *Bandit Algorithms* (Cambridge University Press)](https://tor-lattimore.com/downloads/book/book.pdf)
- [*A Survey on Bandit Learning for Recommender Systems* 2024 (arXiv:2402.02861)](https://arxiv.org/abs/2402.02861)
- [Cao & Tewari 2023 — *Warm-Start Contextual Bandits* (AISTATS)](https://proceedings.mlr.press/v206/cao23e.html)
- [Hsu, Chen, Yu 2024 — *Meta-Learning for LinUCB Bandits* (arXiv:2402.15664)](https://arxiv.org/abs/2402.15664)
- [*A Survey on Bandit Algorithms for Recommendation System*, 2024 (arXiv:2410.02343)](https://arxiv.org/abs/2410.02343)
- [Carbonell & Goldstein 1998 — *The Use of MMR, Diversity-Based Reranking for Reordering Documents* (SIGIR)](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf)
- [Optuna docs — Bayesian hyperparameter optimization (TPE sampler)](https://optuna.readthedocs.io/)
