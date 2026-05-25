from types import SimpleNamespace

from rest_framework import serializers
from apps.accounts.serializers import UserMiniSerializer
from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    """Public Project (Board) serializer — Phase 13 BOARD1.

    CRITICAL: `disliked_ids` is DELIBERATELY ABSENT from every response.
    Algorithm reads the model directly; this serializer never exposes dislikes.
    Applies to owner, public, admin — all contexts.

    `user` is a nested minimal shape: user_id + display_name + avatar_url.

    `latest_session_meta` / `latest_session_id` are OWNER-ONLY fields.
    Non-owners (including anonymous callers) always receive null for both.
    This prevents IDOR: a viewer querying another user's public board must not
    learn whether that user has an in-progress session or its like activity.

    Ownership check: request.user must equal the Project owner's Django User.
    When request is absent from context (e.g. direct serializer instantiation
    without a request) the fields return null conservatively.

    Session lookup is memoised per Project instance via obj.__dict__ to avoid
    two separate DB hits for the two SerializerMethodFields.

    `latest_session_meta` shape (when visible):
      - id: str(session_id)
      - like_count: len(like_vectors) — canonical source, same as swipe.py:518
      - created_at: ISO timestamp of session creation (AnalysisSession has no
        updated_at column; created_at is the next-best proxy for recency)
    Returns null when no session exists or caller is not the owner.
    """
    project_id = serializers.UUIDField(read_only=True)
    user = UserMiniSerializer(read_only=True)
    latest_session_id = serializers.SerializerMethodField()
    latest_session_meta = serializers.SerializerMethodField()

    # ------------------------------------------------------------------
    # Ownership gate: returns True iff the requesting user owns this project
    # ------------------------------------------------------------------
    def _is_owner(self, obj):
        """Return True only when the authenticated request user is the project owner."""
        request = self.context.get('request')
        if request is None or not request.user or not request.user.is_authenticated:
            return False
        # Project.user is a UserProfile; UserProfile.user is the Django User.
        return request.user == obj.user.user

    # ------------------------------------------------------------------
    # Session lookup with per-instance memoisation (Defect 2 fix)
    # ------------------------------------------------------------------
    def _get_latest_session(self, obj):
        """Return the most-recent AnalysisSession for this Project, or None.

        Ownership is gated by the caller (_is_owner check) BEFORE this method
        is invoked, so by the time we reach the DB lookup we are sure the
        requesting user is entitled to the data.

        Memoisation: the result is cached in obj.__dict__ under a private key
        so both get_latest_session_id and get_latest_session_meta share a
        single DB round-trip per serialised object.  A sentinel value of
        False is used to distinguish "cached None" from "not yet cached".

        Two lookup paths:

        1. Annotated queryset (ProjectListCreateView / UserProjectsListView) —
           the view annotates each Project with ``_latest_session_id`` via a
           Subquery.  When present we inspect the annotation directly:
           - annotation is None → no session exists → return None (no extra query)
           - annotation is a UUID → fetch the full Session row (1 query, not N)

        2. Single-object context (ProjectDetailView, serializer unit tests) —
           the ``_latest_session_id`` attribute is absent, so we fall back to a
           queryset call.  One extra query per single-object GET is acceptable.

        This design keeps the list-view query count at O(1) regardless of
        project count.
        """
        cache_key = '_latest_session_cache'
        if cache_key in obj.__dict__:
            cached = obj.__dict__[cache_key]
            # False is the sentinel meaning "cached result is None"
            return None if cached is False else cached

        session = None
        # Annotated path: attribute present (even when None/falsy).
        # ProjectListCreateView and UserProjectsListView annotate three attrs:
        #   _latest_session_id, _latest_like_vectors, _latest_session_created_at
        # Using a SimpleNamespace avoids the N+1 AnalysisSession.objects.get()
        # that the old code issued once per project in the list response.
        if hasattr(obj, '_latest_session_id'):
            if obj._latest_session_id:
                # PERF-1 change B: consume the like-count annotation when present
                # (list-view path), avoiding the 384-dim × N float vector transfer.
                # Fall back to len(like_vectors) for the detail-view path where
                # the annotation is absent and a real AnalysisSession is fetched.
                if hasattr(obj, '_latest_like_count'):
                    like_count = obj._latest_like_count or 0
                else:
                    lvs = getattr(obj, '_latest_like_vectors', None) or []
                    like_count = len(lvs)
                session = SimpleNamespace(
                    session_id=obj._latest_session_id,
                    _like_count=like_count,
                    created_at=getattr(obj, '_latest_session_created_at', None),
                )
        else:
            # Fallback for non-annotated single-object contexts
            # (e.g. ProjectDetailView, serializer unit tests).
            session = obj.sessions.order_by('-created_at').first()

        obj.__dict__[cache_key] = session if session is not None else False
        return session

    def get_latest_session_id(self, obj):
        if not self._is_owner(obj):
            return None
        session = self._get_latest_session(obj)
        return str(session.session_id) if session else None

    def get_latest_session_meta(self, obj):
        if not self._is_owner(obj):
            return None
        session = self._get_latest_session(obj)
        if not session:
            return None
        # PERF-1 change B: SimpleNamespace (list-view path) carries _like_count;
        # real AnalysisSession (detail-view fallback) carries like_vectors.
        if hasattr(session, '_like_count'):
            like_count = session._like_count
        else:
            like_count = len(getattr(session, 'like_vectors', None) or [])
        return {
            'id': str(session.session_id),
            'like_count': like_count,
            'created_at': session.created_at.isoformat() if session.created_at else None,
        }

    class Meta:
        model  = Project
        fields = [
            'project_id',
            'user',
            'name',
            'visibility',
            'reaction_count',
            'liked_ids',
            'saved_ids',
            'filters',
            'raw_query',
            'analysis_report',
            'final_report',
            'report_image',
            'latest_session_id',
            'latest_session_meta',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'project_id',
            'user',
            'liked_ids',
            'saved_ids',
            'reaction_count',
            'analysis_report',
            'final_report',
            'report_image',
            'raw_query',
            'latest_session_id',
            'latest_session_meta',
            'created_at',
            'updated_at',
        ]
        # `disliked_ids` intentionally excluded — never serialized to any caller


class ProjectListSerializer(ProjectSerializer):
    """List-view variant of ProjectSerializer.

    Excludes ``analysis_report`` — the heavy LLM JSON field is deferred by
    `.defer('analysis_report')` on the list queryset (PERF-1 change C).
    If DRF read it from Meta.fields it would trigger a lazy DB round-trip per
    row (N+1).  Dropping it here keeps the output consistent with the deferred
    query and preserves the detail-view contract where ``analysis_report`` is
    still returned (ProjectDetailView uses ProjectSerializer, not this class).
    """

    class Meta(ProjectSerializer.Meta):
        fields = [f for f in ProjectSerializer.Meta.fields if f != 'analysis_report']
        read_only_fields = [
            f for f in ProjectSerializer.Meta.read_only_fields if f != 'analysis_report'
        ]


class ProjectSelfUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/v1/projects/{project_id}/ — owner updates name + visibility only.

    All other fields (liked_ids, saved_ids, filters, reaction_count, etc.)
    are managed by swipe flow or system — silently ignored on PATCH.
    """
    class Meta:
        model  = Project
        fields = ['name', 'visibility']
