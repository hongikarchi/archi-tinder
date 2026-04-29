import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
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
        'OPTIONS': {
            'sslmode': os.getenv('DB_SSLMODE', 'require'),
        },
    }
}

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
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# -- CORS ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://localhost:5174').split(',')
CORS_ALLOW_CREDENTIALS = True

# -- Cache (required for DRF throttling) -----------------------------------
# IMP-8 (v1.6 §11.1): async prefetch background thread writes to default cache.
# IMP-5 (v1.5 §11.1): Gemini context-cache resource name stored in default cache.
# Production multi-worker deploys SHOULD swap LocMemCache for Redis (django-redis)
# to share cache across workers -- LocMemCache is per-process, so cache writes from
# bg thread in worker A are not visible to next swipe arriving on worker B.
# Single-worker dev / Render free tier with 1 worker: LocMemCache works fine.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

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

# -- Recommendation algorithm constants ------------------------------------
RECOMMENDATION = {
    'bounded_pool_target': 150,
    'min_likes_for_clustering': 4,  # Spec v1.8 Topic 06 N>=4 activation-cliff mitigation per Investigation 21 §closure -- defer K-Means until N>=4 to avoid the Investigation 09 worst-case window (1 Love + 2 Likes, k=2 forces centroid collapse onto Love)
    'decay_rate': 0.05,              # gamma -- recency weight decay
    'mmr_penalty': 0.3,              # lambda -- diversity penalty
    'convergence_threshold': 0.08,   # epsilon -- delta-V threshold
    'convergence_window': 3,
    'k_clusters': 2,
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
    'async_prefetch_enabled': False,                   # default OFF for safe rollout; flip True after Redis wired in prod
    'async_prefetch_cache_timeout_seconds': 60,        # Django cache TTL for prefetch entries (seconds)
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
}

# -- External API keys -----------------------------------------------------
GEMINI_API_KEY    = os.getenv('GEMINI_API_KEY', '')
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
    },
}
