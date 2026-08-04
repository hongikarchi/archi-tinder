import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
# Guard: skip .env load under pytest — DB config comes from conftest setdefaults
# (plain pytest / local), inline env vars (make test-local), or the CI job env.
# Loading the real .env would overwrite those placeholders and connect to the
# real Neon DB, leaking the password in connection-DSN tracebacks (488 errors).
if 'pytest' not in sys.modules:
    load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    # Local
    'apps.accounts',
    'apps.recommendation',
    'apps.profiles',
    'apps.social',
    'apps.notifications',
    'apps.works',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# -- Database --------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST':     os.environ['DB_HOST'],
        'PORT':     os.getenv('DB_PORT', '5432'),
        'NAME':     os.environ['DB_NAME'],
        'USER':     os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'CONN_MAX_AGE': 600,  # Reuse DB connections for 10 minutes
        'CONN_HEALTH_CHECKS': True,  # Django 4.2+: close broken pooled connections proactively
        'TIME_ZONE': None,  # explicit so settings_dict["TIME_ZONE"] never raises on reconnect
        'OPTIONS': {
            'sslmode': os.getenv('DB_SSLMODE', 'require'),
        },
    },
    # Building reference data — Make-DB-owned, read-only. Separate Neon DB.
    # BUILDINGS_DB_* are required: a missing var fails loud at import rather
    # than silently routing building queries to the app DB (which has no
    # canonical_v2_buildings table). MakeWebRouter blocks migrate on this alias.
    'buildings': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST':     os.environ['BUILDINGS_DB_HOST'],
        'PORT':     os.getenv('BUILDINGS_DB_PORT', '5432'),
        'NAME':     os.environ['BUILDINGS_DB_NAME'],
        'USER':     os.environ['BUILDINGS_DB_USER'],
        'PASSWORD': os.environ['BUILDINGS_DB_PASSWORD'],
        'TIME_ZONE': None,  # explicit so settings_dict["TIME_ZONE"] never raises on reconnect
        'OPTIONS': {
            'sslmode': os.getenv('BUILDINGS_DB_SSLMODE', 'require'),
        },
    },
}

DATABASE_ROUTERS = ['config.db_router.MakeWebRouter']

# -- Auth ------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -- REST Framework --------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.accounts.authentication.CachedJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_RATES': {
        # Scoped throttle for the anonymous image-load telemetry beacon.
        # Budget: ~1-2 images/card × 30 swipes/min = 60-90 events/min; 120/min is a safe cap.
        'image_load_telemetry': '120/min',
        # React/unreact write throttle — prevents bulk-reaction abuse (SOC2).
        'reaction_write': '60/min',
        # Guest auth throttles — operator-overridable without code changes.
        'guest_login': '3/min',
        'guest_promote': '5/min',
        # AUTH-LOGIN-1: handle+password auth + email-link throttles.
        'register': '10/min',
        'password_login': '10/min',
        'link_email': '5/min',
        # AUTH-CRITICAL: set/change-password brute-force guard (current_password check).
        'set_password': '5/min',
        # FRONT-AVATAR-1: avatar upload is expensive (Pillow + R2 PUT); tight rate.
        'avatar_upload': '10/min',
        # Global fallback rates (applied to views that reference these scopes directly).
        'anon': '60/min',
        'user': '300/min',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    # FULL-LOGIN-REDESIGN-1: add is_guest claim to all tokens issued via
    # the standard obtain-pair endpoint (guest + promote endpoints inject
    # the claim directly via RefreshToken.for_user path).
    'TOKEN_OBTAIN_SERIALIZER':
        'apps.accounts.jwt_serializers.CustomTokenObtainPairSerializer',
}

# -- CORS ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://localhost:5174').split(',')
CORS_ALLOW_CREDENTIALS = True

# -- Cache (required for DRF throttling, IMP-5 Gemini context-cache, IMP-8 async prefetch) --
# INFRA-REDIS-1 (2026-05-26): Redis is the prod cache backend so PR 3 (BACK-AUTH-1 JWT user-row cache)
# and PR 4 (PERF-PREFETCH-CHAIN async consume) work across Railway's multi-worker
# Gunicorn (LocMemCache is per-process; bg thread in worker A -> next swipe in worker B
# would always miss). Local dev keeps LocMemCache when REDIS_URL is unset, so devs do
# not need to run a Redis daemon to spin up backend.
# IMP-8 (v1.6 §11.1): async prefetch background thread writes to default cache.
# IMP-5 (v1.5 §11.1): Gemini context-cache resource name stored in default cache.


def _check_async_prefetch_safety(debug: bool, async_prefetch_enabled: bool, redis_url: str) -> None:
    """Cache safety guard (INFRA-REDIS-1 follow-up, 2026-05-26 Codex retest).

    In production (DEBUG=False), if async prefetch is enabled, REDIS_URL MUST be
    set. LocMemCache is per-process; the async prefetch thread writes to worker
    A's cache and the next-swipe consumer in worker B reads its own empty cache.
    The chain silently degrades to zero benefit + wasted thread cost. Fail loud at
    startup instead so ops sees the misconfiguration immediately.

    Extracted as a module-level helper so unit tests can call it directly without
    monkeypatching os.environ or reloading the module (same pattern as
    _build_caches_dict).
    """
    if not debug and async_prefetch_enabled and not redis_url.strip():
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "async_prefetch_enabled=True in prod requires REDIS_URL. Set it on the "
            "Railway service to ${{Redis.REDIS_URL}}, or disable async prefetch in "
            "RECOMMENDATION['async_prefetch_enabled']."
        )


def _build_caches_dict(redis_url: str) -> dict:
    """Return a CACHES dict for the given redis_url (empty string -> LocMemCache).

    Extracted as a module-level helper so unit tests can call it directly
    without monkeypatching os.environ or reloading the module.
    Connection failures with a configured Redis URL are NOT swallowed -- ops
    team should see them loudly rather than silently falling back to
    LocMemCache, which would cause multi-worker cache incoherence in prod.
    """
    if redis_url:
        return {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': redis_url,
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                    # Sensible default timeout; matches the implicit 300s default Django
                    # cache TTL -- explicit so reviewers see it.
                    'SOCKET_CONNECT_TIMEOUT': 3,
                    'SOCKET_TIMEOUT': 3,
                },
                # Optional key prefix protects against accidentally sharing keys with
                # another app using the same Redis instance.
                'KEY_PREFIX': 'makeweb',
            }
        }
    return {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            # Default MAX_ENTRIES=300 thrashes with ~150-card pools per session;
            # bump to 2000 (~13 concurrent sessions x 150 building-card payloads).
            'OPTIONS': {'MAX_ENTRIES': 2000},
        }
    }


CACHES = _build_caches_dict(os.getenv('REDIS_URL', '').strip())

# -- Internationalization --------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# -- Static files ----------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -- Media (user uploads — avatars) ----------------------------------------
# MEDIA_ROOT: local filesystem write target (dev + CI filesystem fallback).
# In prod the R2 branch in apps/accounts/storage.py is active and Django never
# serves from MEDIA_ROOT; the debug-only media-serve in config/urls.py is a no-op.
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# -- Avatar upload settings ------------------------------------------------
# FRONT-AVATAR-1: R2 env vars — all optional; when ALL four are set the upload
# goes to Cloudflare R2. When any is missing, falls back to local filesystem.
R2_ENDPOINT_URL      = os.getenv('R2_ENDPOINT_URL', '')
R2_ACCESS_KEY_ID     = os.getenv('R2_ACCESS_KEY_ID', '')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY', '')
R2_AVATAR_BUCKET     = os.getenv('R2_AVATAR_BUCKET', '')
AVATAR_PUBLIC_BASE_URL = os.getenv('AVATAR_PUBLIC_BASE_URL', '')
R2_WORKS_BUCKET      = os.getenv('R2_WORKS_BUCKET', '')
WORKS_PUBLIC_BASE_URL = os.getenv('WORKS_PUBLIC_BASE_URL', '')
WORKS_R2_ENABLED = all([R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_WORKS_BUCKET])

# True only when all four R2 vars are set (non-empty).
AVATAR_R2_ENABLED = all([
    R2_ENDPOINT_URL,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_AVATAR_BUCKET,
])

# Hard limits — not magic numbers in the view.
AVATAR_MAX_BYTES      = 5 * 1024 * 1024   # 5 MB
AVATAR_MAX_PIXELS     = 25_000_000         # decompression-bomb dimension guard (5000x5000 — ample for any avatar source)
AVATAR_OUTPUT_EDGE    = 512                 # square output side in pixels

# -- Recommendation algorithm constants ------------------------------------
RECOMMENDATION = {
    'bounded_pool_target': 150,
    'min_likes_for_clustering': 4,  # Spec v1.8 Topic 06 N>=4 activation-cliff mitigation per Investigation 21 §closure -- defer K-Means until N>=4 to avoid the Investigation 09 worst-case window (1 Love + 2 Likes, k=2 forces centroid collapse onto Love)
    'decay_rate': 0.05,              # gamma -- recency weight decay
    'mmr_penalty': 0.3,              # lambda -- diversity penalty
    'convergence_threshold': 0.13,   # epsilon -- tuned for convergence inside the 10-swipe target window
    'convergence_window': 3,
    'target_swipes': 10,             # product goal: taste should be captured within ~10 swipes
    'convergence_min_recent_likes': 2,  # recent positive evidence required before backend declares convergence
    'k_clusters': 2,
    'min_likes_for_multimodal': 11,  # keep the <=10-swipe loop single-centroid; KMeans only after the target window
    'max_consecutive_dislikes': 5,
    'top_k_results': 20,
    'like_weight': 0.5,              # kept for pref vector update
    'dislike_weight': -1.0,
    'initial_explore_rounds': 10,    # kept for initial batch size
    'adaptive_k_clustering_enabled': False,  # Topic 06: silhouette-based k selection {1, 2}
    'soft_relevance_enabled':        False,  # Topic 06: softmax over centroid distances vs max
    'gemini_rerank_enabled':         False,  # Topic 02: Gemini setwise rerank at session end
    'mmr_lambda_ramp_enabled':       False,  # Topic 04 (a): per-swipe λ ramp
    'mmr_lambda_ramp_n_ref':         10,     # N_ref for ramp denominator
    'dpp_topk_enabled':              False,  # Topic 04 (b): DPP greedy MAP at session-final top-K
    'dpp_overfetch_multiplier':      3,      # Topic 04 (b): candidate window multiplier when DPP ON (n=k*mult so DPP can MAP-narrow)
    'dpp_alpha':                     1.0,    # Wilhelm-form diversity strength; Optuna search [0.5, 1.0]
    'dpp_singularity_eps':           1e-9,   # Cholesky residual threshold for singularity
    'hyde_vinitial_enabled':         False,  # Topic 03: HyDE V_initial embedding rerank
    'hyde_hf_model':                 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
    'hyde_hf_timeout_seconds':       5,
    'hyde_score_weight':             50.0,   # HyDE similarity score additive weight
    # Topic 01: Hybrid Retrieval (RRF) -- Cormack et al. 2009
    'hybrid_retrieval_enabled':      False,  # CRITICAL: default OFF for backward compat
    'hybrid_rrf_k':                  60,     # Cormack 2009 default; uniform fusion 1/(k+rank)
    'hybrid_bm25_dict':              'simple',  # tsvector dictionary; 'simple' = multilingual-safe (no stemming)
    'hybrid_filter_channel_enabled': True,   # True: filter is a 3rd RRF rank channel; False: filter is a predicate gate
    # IMP-7: per-building-id embedding cache (frozenset -> building_id key refactor)
    'pool_precompute_enabled': False,        # Currently gates a no-op: cache is warmed naturally via
                                             # the existing get_pool_embeddings(pool_ids) call in
                                             # SessionCreateView. Reserved for future explicit-warming
                                             # paths (e.g., IMP-8 async background warming).
    'pool_embedding_cache_max_size': 5000,   # IMP-7 FIFO eviction bound; ~5MB max. Bump for larger corpora.
    # IMP-8 (Spec v1.6 §11.1): async prefetch background thread
    'async_prefetch_enabled': True,                    # Re-enabled after PERF-PREFETCH-CHAIN (PR 4 of 4 perf sweep): thread write off-by-one fixed + cache.get consumer wired + Redis backend (INFRA-REDIS-1) provides multi-worker cache coherence.
    'async_prefetch_cache_timeout_seconds': 60,        # Django cache TTL for prefetch entries (seconds)
    # Per-card LRU TTL (PR #22 absorb): cache.get/set under 'bcard:<id>' keys.
    # 3600s default keeps building-card payloads warm across requests without
    # going stale relative to Make DB updates.
    'card_cache_ttl': 3600,
    # IMP-5 (Spec v1.5 §11.1): Gemini explicit context caching for _CHAT_PHASE_SYSTEM_PROMPT
    'context_caching_enabled': False,                  # default OFF; flip True only after Redis cache backend is wired
    'context_caching_ttl_seconds': 3600,               # Gemini cache TTL; also used as Django cache TTL for resource name
    # IMP-6 (Spec v1.10 §11.1): 2-stage decouple — late-binding V_initial plumbing.
    # Commit 1 (2d): scaffolding only. With flag OFF (default) all paths are byte-identical
    # to pre-IMP-6. With flag ON (Commit 2): parse_query returns Stage 1 output
    # (filters + reply, ~150-220 tokens) immediately; Stage 2 (visual_description,
    # ~140-180 tokens) fires async. SessionCreateView reads V_initial from Django cache
    # (key: v_initial:{user_id}:{sha256(raw_query)[:16]}); on cache miss, creates pool
    # with filters only (BM25-only RRF per spec v1.5 Topic 01 graceful-degrade).
    # Expected TTFC improvement (M1-grounded): ~45-55% Gemini wall-time drop.
    #
    # Production canary (Sprint D Commit 4): set STAGE_DECOUPLE_ENABLED=true in
    # Railway dashboard env vars to flip flag ON for production traffic. Default
    # 'false' preserves byte-identical pre-IMP-6 behavior. Roll back instantly by
    # unsetting the env var or changing to 'false'. No code redeploy needed for
    # rollback. Monitor parse_query_timing.stage='1' rate + stage2_timing.outcome
    # distribution + Brutalist sys_p50 trend post-flip.
    'stage_decouple_enabled': os.getenv('STAGE_DECOUPLE_ENABLED', 'false').lower() == 'true',  # default OFF; set STAGE_DECOUPLE_ENABLED=true in env to flip
    # Discovery tab v3.1 hyperparameters (10-card chunk + 3-Tier + Draft Board)
    'discovery_chunk_size': 10,
    'discovery_tier2_min_likes': 10,
    'discovery_tier3_min_projects': 4,
    'discovery_tier3_min_likes': 50,
    'discovery_tier2_local': 2,
    'discovery_tier2_global': 8,
    'discovery_tier3_local': 4,
    'discovery_tier3_global': 6,
    'discovery_dislike_history_window': 30,
    'discovery_dislike_zone_threshold': 0.15,   # pgvector cosine DISTANCE; candidates farther than this from dislike centroid pass
    'discovery_local_sim_radius': 0.55,          # cosine SIM to nearest centroid to count as local/취향
    'discovery_centroid_cache_ttl': 21600,       # 6h — app-session fixed
    'discovery_promote_threshold': 10,
    # ALGO-QCARD Phase 1: soft-vector bias hyperparameters
    'question_max_per_session': 2,      # ALGO-QCARD soft-vector: max question cards per session
    'question_cooldown_swipes': 15,     # min swipes between question cards
    'question_boost_weight': 2.0,       # Yes answer: + boost on keyword vector
    'question_penalty_weight': 1.0,     # No answer: - penalty on keyword vector
    # ALGO-QCARD Phase 2: TF-IDF discriminative keyword selection
    'corpus_df_cache_ttl_seconds': 86400,   # TF-IDF corpus DF cache TTL (24h)
    'question_common_tag_ratio': 0.4,        # tags with df/N above this are too common → skipped
    # Explicit generic-tag blacklist (leave empty; df/N ratio is the primary discriminator).
    # Ops can populate with domain-specific stop-tags if IDF alone is insufficient.
    'question_keyword_blacklist': [],
    'discovery_like_hard_cap': 50,  # Discovery draft hard stop: block likes beyond 50; client redirects to Taste
    # DISCOVERY-PERF-1: scope tier/exclude/dislike/centroid to most-recent N boards (tunable).
    # Older boards' liked/disliked/saved buildings may re-appear in Discovery — intended behaviour.
    'discovery_recent_boards_cap': 10,
    # DISCOVERY candidate fetch: TABLESAMPLE SYSTEM percentage — block-level random
    # sample that avoids a full seq scan of the large canonical_v2_buildings table
    # (VECTOR(384) + JSONB rows). ~2% of ~39k ≈ 780 sampled, ample for the 120-cap FPS.
    'discovery_tablesample_pct': 2.0,
    # ALGO-QCARD Phase 3: hyper-positive / fast-swipe detection (Trigger A)
    'question_fast_swipe_ms': 1500,          # avg inter-swipe latency below this = "fast" (hyper-positive)
    'question_hyperpositive_window': 10,     # look back this many swipes
    'question_hyperpositive_min_likes': 8,   # >= this many likes in the window triggers
    'recent_latencies_cap': 10,              # rolling latency window size
    # LLM-SEARCH-RANK-1: A+BM25 soft-score ranking hyperparameters for ParseQueryView.
    # Replaces ORDER BY RANDOM() + 3-tier relaxation ladder with a single ranked CTE.
    # All axes are soft (no hard gate except is_publishable=true).
    'llm_search_topk': 200,               # K: tag-score candidate set before BM25 rerank
    'llm_search_w_bm25': 8.0,             # w_bm25: BM25 contribution weight in final score
    'llm_search_priority_boost': 0.25,    # boost factor for filter_priority ordering
    'llm_search_top_priority_multiplier': 4.0,  # D2: rank-0 axis extra dominance multiplier
    'llm_search_idf_ceiling': 3.0,        # IDF ceiling clamp (rare tags capped at 3x)
    'llm_search_base_weights': {          # per-axis base scoring weights (soft, no hard gate)
        'program': 10.0,          # highest: program type is the strongest signal
        'typology_primary': 6.0,  # building typology (single TEXT, ILIKE)
        'location_country': 5.0,  # country-level geography
        'location_city': 5.0,     # city-level geography
        'material': 4.0,          # material (unnest array ILIKE)
        'style': 4.0,             # architectural style (ILIKE)
        'atmosphere': 3.0,        # mood/atmosphere (new soft axis, ILIKE)
        'color_tone': 2.0,        # color palette (new soft axis, ILIKE)
        # BACK-PARSER-VOCAB-1: architectural_elements (unnest array ILIKE), same
        # weight tier as material -- both are concrete-feature axes, not just mood.
        'architectural_elements': 4.0,
        'year_min': 1.0,          # year range (soft bonus, not exclusion)
        'year_max': 1.0,
    },
}

_check_async_prefetch_safety(
    DEBUG,
    RECOMMENDATION.get('async_prefetch_enabled', False),
    os.getenv('REDIS_URL', ''),
)

# -- External API keys -----------------------------------------------------
PERF_TIMING_ENABLED = os.environ.get('PERF_TIMING_ENABLED', 'False').lower() == 'true'

# -- External API keys -----------------------------------------------------
GEMINI_API_KEY              = os.getenv('GEMINI_API_KEY', '')
GEMINI_TEXT_MODEL           = os.getenv('GEMINI_TEXT_MODEL', 'gemini-3.1-flash-lite')
GEMINI_TEXT_MODEL_FALLBACK  = os.getenv('GEMINI_TEXT_MODEL_FALLBACK', 'gemini-2.5-flash')
GEMINI_IMAGE_MODEL          = os.getenv('GEMINI_IMAGE_MODEL', 'gemini-3.1-flash-image')
GEMINI_IMAGE_MODEL_FALLBACK = os.getenv('GEMINI_IMAGE_MODEL_FALLBACK', 'gemini-2.5-flash-image')
GEMINI_IMAGE_FORMAT         = os.getenv('GEMINI_IMAGE_FORMAT', 'webp')   # webp|native
# BACK-LLM-PROVIDER-1: A/B provider switch for the TEXT-PARSE path only
# (apps.recommendation.services._gemini). Image generation always uses Gemini
# regardless of this flag (see _get_gemini_client() in _gemini.py).
LLM_PROVIDER      = os.getenv('LLM_PROVIDER', 'gemini')  # gemini|openai
OPENAI_API_KEY    = os.getenv('OPENAI_API_KEY', '')
OPENAI_TEXT_MODEL = os.getenv('OPENAI_TEXT_MODEL', 'gpt-5.6-luna')
# Optional reasoning-effort knob; allowlist-validated here so a typo'd env var
# degrades to "not sent" instead of a per-request 400 on the parse path.
_OPENAI_EFFORT_ALLOWED = ('', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')
OPENAI_REASONING_EFFORT = os.getenv('OPENAI_REASONING_EFFORT', '')
if OPENAI_REASONING_EFFORT not in _OPENAI_EFFORT_ALLOWED:
    OPENAI_REASONING_EFFORT = ''
# BACK-LLM-PROVIDER-2: separate A/B provider switch for the IMAGE-GEN path
# (generation.py _gen_native), independent of LLM_PROVIDER above so text/image
# providers mix freely (e.g. LLM_PROVIDER=openai + LLM_IMAGE_PROVIDER=gemini).
LLM_IMAGE_PROVIDER = os.getenv('LLM_IMAGE_PROVIDER', 'gemini')  # gemini|openai
OPENAI_IMAGE_MODEL = os.getenv('OPENAI_IMAGE_MODEL', 'gpt-image-2')
_OPENAI_IMAGE_QUALITY_ALLOWED = ('low', 'medium', 'high')
OPENAI_IMAGE_QUALITY = os.getenv('OPENAI_IMAGE_QUALITY', 'medium')  # low|medium|high
if OPENAI_IMAGE_QUALITY not in _OPENAI_IMAGE_QUALITY_ALLOWED:
    OPENAI_IMAGE_QUALITY = 'medium'
HF_TOKEN          = os.getenv('HF_TOKEN', '')
IMAGE_BASE_URL    = os.getenv('IMAGE_BASE_URL', 'https://pub-5d2133d166fc4b65ad05295df352519f.r2.dev')
GOOGLE_CLIENT_ID  = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
KAKAO_CLIENT_ID   = os.getenv('KAKAO_CLIENT_ID', '')
KAKAO_CLIENT_SECRET = os.getenv('KAKAO_CLIENT_SECRET', '')
NAVER_CLIENT_ID   = os.getenv('NAVER_CLIENT_ID', '')
NAVER_CLIENT_SECRET = os.getenv('NAVER_CLIENT_SECRET', '')

# -- Production security ---------------------------------------------------
if not DEBUG:
    # HTTP headers
    SECURE_BROWSER_XSS_FILTER    = True
    SECURE_CONTENT_TYPE_NOSNIFF  = True
    X_FRAME_OPTIONS              = 'DENY'
    SECURE_HSTS_SECONDS          = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD          = True
    # Cookies (only meaningful if sessions/CSRF are used)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE    = True
    # SECRET_KEY sanity check
    if len(SECRET_KEY) < 50:
        raise RuntimeError('DJANGO_SECRET_KEY is too short for production (min 50 chars)')

# -- Logging ---------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'perf_timing': {
            'handlers': ['console'],
            'level': 'INFO' if PERF_TIMING_ENABLED else 'WARNING',
            'propagate': False,
        },
    },
}
