import uuid
from django.db import models
from apps.accounts.models import UserProfile


class Project(models.Model):
    VISIBILITY_CHOICES = [
        ('public',  'Public'),
        ('private', 'Private'),
    ]

    project_id      = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user            = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='projects')
    name            = models.CharField(max_length=200)
    liked_ids       = models.JSONField(default=list)   # list[{id: str, intensity: float}] — Like 1.0, Love 1.8 (Sprint 3 A-1)
    disliked_ids    = models.JSONField(default=list)   # list[str] — building_ids only, no intensity
    saved_ids       = models.JSONField(default=list)   # list[{id: str, saved_at: ISO timestamp}] — bookmark (primary metric)
    filters         = models.JSONField(default=dict)
    raw_query       = models.TextField(null=True, blank=True)  # original user search text, shown on public Board
    analysis_report = models.JSONField(null=True, blank=True)
    final_report    = models.JSONField(null=True, blank=True)
    report_image    = models.TextField(null=True, blank=True)  # base64 image data
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    # -- Phase 13 BOARD1 additions --
    visibility     = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default='private',
        # Conservative default: user must opt-in to publish.
        # Existing rows backfilled via migration DEFAULT.
    )
    reaction_count = models.IntegerField(
        default=0,
        # Phase 15 SOC2 placeholder — denormalized counter updated by future Reaction events.
    )

    def __str__(self):
        return f'{self.name} ({self.user})'


class AnalysisSession(models.Model):
    STATUS_CHOICES = [
        ('active',    'Active'),
        ('completed', 'Completed'),
    ]
    PHASE_CHOICES = [
        ('exploring', 'Exploring'),
        ('analyzing', 'Analyzing'),
        ('converged', 'Converged'),
        ('completed', 'Completed'),
    ]
    session_id        = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user              = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    project           = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='sessions')
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    current_round     = models.IntegerField(default=0)
    preference_vector = models.JSONField(default=list)
    exposed_ids       = models.JSONField(default=list)
    initial_batch     = models.JSONField(default=list)  # building_ids for first 10 rounds
    phase               = models.CharField(max_length=20, choices=PHASE_CHOICES, default='exploring')
    pool_ids            = models.JSONField(default=list)
    pool_scores         = models.JSONField(default=dict)   # {building_id: relevance_score}
    like_vectors        = models.JSONField(default=list)   # list of {embedding: [...], round: int}
    convergence_history = models.JSONField(default=list)   # list of delta-V floats
    previous_pref_vector = models.JSONField(default=list)
    # Sprint 0 A4: pool exhaustion guard state (§5.6 + §6 Implementation Requirements item 1)
    original_filters         = models.JSONField(default=dict)  # filters used at session creation (for re-relaxation if pool exhausts)
    original_filter_priority = models.JSONField(default=list)
    original_seed_ids        = models.JSONField(default=list)
    current_pool_tier        = models.IntegerField(default=1)  # 1=full filter, 2=drop geo/numeric, 3=random pool
    v_initial         = models.JSONField(null=True, blank=True)  # Topic 03 HyDE: 384-dim float list
    original_q_text   = models.TextField(null=True, blank=True)  # Topic 01 RRF: original raw_query for re-relaxation
    # IMP-10 sub-task A / Spec v1.7 §11.1: top-10 id lists for bookmark provenance
    # Populated by SessionResultView when each ranking channel runs.
    # Null when the flag for that channel was off, or for sessions before migration 0013.
    cosine_top10_ids  = models.JSONField(null=True, blank=True)  # first 10 cosine-ordered ids at result time
    gemini_top10_ids  = models.JSONField(null=True, blank=True)  # first 10 Gemini-rerank ids (None when flag off)
    dpp_top10_ids     = models.JSONField(null=True, blank=True)  # first 10 DPP-ordered ids (None when flag off)
    created_at        = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Session {self.session_id} ({self.status})'


class SwipeEvent(models.Model):
    ACTION_CHOICES = [
        ('like',    'Like'),
        ('dislike', 'Dislike'),
    ]
    session         = models.ForeignKey(AnalysisSession, on_delete=models.CASCADE, related_name='swipes')
    building_id     = models.CharField(max_length=20)
    action          = models.CharField(max_length=10, choices=ACTION_CHOICES)
    idempotency_key = models.CharField(max_length=100, db_index=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('session', 'idempotency_key')]

    def __str__(self):
        return f'{self.action} {self.building_id}'


class SessionEvent(models.Model):
    """
    Event log for session lifecycle measurement (spec §6).

    Single model with event_type + JSON payload -- simpler than per-event-type
    tables and more flexible for spec-evolving events.

    Implementation notes (from spec §6):
    - Monotonic timestamp: db-level auto_now_add (default microsecond resolution).
      For tie-breaking within the same session, sequence_no is auto-incremented
      per session by the emit_event helper.
    - Anonymized aggregation: user FK + session FK chain, both nullable so failure
      events during pre-auth or pre-session paths can still be logged.
    - Bookmark rank_zone separation: payload['rank_zone'] is 'primary' (1-10) or
      'secondary' (11-50) -- used by primary-metric extractor to distinguish
      top-10 bookmark rate (objective) from exploration-zone clicks (secondary).
      Wired when bookmark endpoint ships in Sprint 4.
    """

    EVENT_TYPE_CHOICES = [
        ('session_start',      'Session Start'),
        ('pool_creation',      'Pool Creation'),
        ('swipe',              'Swipe'),
        ('tag_answer',         'Tag Answer'),
        ('confidence_update',  'Confidence Update'),
        ('session_end',        'Session End'),
        ('session_extend',     'Session Extend'),
        ('bookmark',           'Bookmark'),
        ('detail_view',        'Detail View'),
        ('external_url_click', 'External URL Click'),
        ('failure',            'Failure'),
        ('probe_turn',          'Probe Turn'),
        ('cohort_assignment',   'Cohort Assignment'),
        ('parse_query_timing',  'Parse Query Timing'),
        ('hyde_call_timing',    'HyDE Call Timing'),
        ('hybrid_pool_timing',  'Hybrid Pool Timing'),
        ('stage2_timing',       'Stage 2 Timing'),
    ]

    user        = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='session_events',
    )
    session     = models.ForeignKey(
        AnalysisSession, on_delete=models.CASCADE,
        null=True, blank=True, related_name='events',
    )
    event_type  = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES, db_index=True)
    payload     = models.JSONField(default=dict)
    sequence_no = models.PositiveIntegerField(default=0)  # per-session tie-breaker
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]

    def __str__(self):
        return f'{self.event_type} ({self.session_id}, {self.created_at.isoformat()})'
