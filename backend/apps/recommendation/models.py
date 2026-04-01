import uuid
from django.db import models
from apps.accounts.models import UserProfile


class Project(models.Model):
    project_id      = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user            = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='projects')
    name            = models.CharField(max_length=200)
    liked_ids       = models.JSONField(default=list)
    disliked_ids    = models.JSONField(default=list)
    filters         = models.JSONField(default=dict)
    analysis_report = models.JSONField(null=True, blank=True)
    final_report    = models.JSONField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

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
    total_rounds      = models.IntegerField(default=20)
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
    idempotency_key = models.CharField(max_length=100, unique=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.action} {self.building_id}'
