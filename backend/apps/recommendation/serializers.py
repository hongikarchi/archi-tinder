import json
from types import SimpleNamespace

from rest_framework import serializers
from apps.accounts.serializers import UserMiniSerializer
from .models import Project

# ── Conversation-history validation limits (mirrors search.py ParseQueryView) ──
# Mirrored here (not imported) because they are local vars inside ParseQueryView.post.
_MAX_CHAT_MESSAGES = 60   # max items in conversation_history['messages'] list
_MAX_HISTORY_LEN = 10     # max items in conversation_history['history'] list
_MAX_TEXT_LEN = 2000      # max chars per text string in either sub-list
_MAX_BLOB_BYTES = 65536   # 64 KB total JSON size cap


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
            'axis_scores',
            'report_image',
            'report_image_mime',
            'conversation_history',
            'is_temp',
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
            'axis_scores',
            'report_image',
            'report_image_mime',
            'raw_query',
            # conversation_history is read-only on ProjectSerializer (create path).
            # It is writable only via ProjectSelfUpdateSerializer (PATCH path).
            'conversation_history',
            # is_temp is read-only on ProjectSerializer (create path).
            # It is writable only via ProjectSelfUpdateSerializer (PATCH save-confirm).
            'is_temp',
            'latest_session_id',
            'latest_session_meta',
            'created_at',
            'updated_at',
        ]
        # `disliked_ids` intentionally excluded — never serialized to any caller


_LIST_EXCLUDE_FIELDS = {'analysis_report', 'conversation_history', 'axis_scores'}


class ProjectListSerializer(ProjectSerializer):
    """List-view variant of ProjectSerializer.

    Excludes ``analysis_report`` and ``conversation_history`` — both are heavy
    JSON fields deferred via `.defer(...)` on the list queryset (PERF-1 change C
    + BACK-LLM-2).  If DRF read them from Meta.fields they would trigger lazy
    DB round-trips per row (N+1).  Dropping them here keeps list output lean and
    consistent with the deferred queryset.

    detail-view contract: both fields are still returned by ProjectDetailView
    (which uses ProjectSerializer, not this class).
    """

    class Meta(ProjectSerializer.Meta):
        fields = [f for f in ProjectSerializer.Meta.fields if f not in _LIST_EXCLUDE_FIELDS]
        read_only_fields = [
            f for f in ProjectSerializer.Meta.read_only_fields
            if f not in _LIST_EXCLUDE_FIELDS
        ]


_PUBLIC_LIST_EXCLUDE_FIELDS = _LIST_EXCLUDE_FIELDS | {'report_image', 'report_image_mime'}


class PublicProjectListSerializer(ProjectListSerializer):
    """UserProjectsListView variant — additionally excludes report_image(_mime).

    BACK-PRIVACY-1: UserProjectsListView (GET /api/v1/users/<id>/projects/) is
    AllowAny, so ProjectListSerializer's report_image/report_image_mime
    (base64 TEXT, ~200KB each, up to 50/page) let anonymous callers bulk-
    harvest taste-report images off public boards. Profile board thumbnails
    already use a separate lazy pointer (accounts/views/profile.py
    has_report_image + report_image_url; reports.py ProjectReportImageFetchView),
    so nothing needs report_image inlined in this list response.

    Do NOT use this for ProjectListCreateView's owner list (GET /projects/) —
    App.jsx:929 login project-sync consumes report_image from that endpoint.
    """

    class Meta(ProjectListSerializer.Meta):
        fields = [f for f in ProjectListSerializer.Meta.fields if f not in _PUBLIC_LIST_EXCLUDE_FIELDS]
        read_only_fields = [
            f for f in ProjectListSerializer.Meta.read_only_fields
            if f not in _PUBLIC_LIST_EXCLUDE_FIELDS
        ]


class ProjectSelfUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/v1/projects/{project_id}/ — owner updates name, visibility, conversation_history, is_temp.

    All other fields (liked_ids, saved_ids, filters, reaction_count, etc.)
    are managed by swipe flow or system — silently ignored on PATCH.

    FEAT-TASTE-FLOW-1 save-confirm action: PATCH {is_temp: false, name, visibility}
    atomically confirms a temporary project as a permanent board.

    conversation_history validation:
    - must be a dict
    - total JSON size ≤ 64 KB (_MAX_BLOB_BYTES)
    - if 'messages' key present: must be a list ≤ _MAX_CHAT_MESSAGES items;
      each item's 'text' value ≤ _MAX_TEXT_LEN chars
    - if 'history' key present: must be a list ≤ _MAX_HISTORY_LEN items;
      each item's 'text' value ≤ _MAX_TEXT_LEN chars
    - extra keys are tolerated (frontend owns the blob shape)

    visibility validation: must be one of Project.VISIBILITY_CHOICES values.
    """

    def validate_is_temp(self, value):
        if value:
            raise serializers.ValidationError(
                "is_temp can only be set to false (finalize is one-way)."
            )
        return value

    def validate_visibility(self, value):
        valid_values = [choice[0] for choice in Project.VISIBILITY_CHOICES]
        if value not in valid_values:
            raise serializers.ValidationError(
                f'visibility must be one of: {", ".join(valid_values)}.'
            )
        return value

    def validate_conversation_history(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('conversation_history must be a dict.')

        # Total size gate — measure actual UTF-8 bytes (Korean chars = 3 bytes
        # each; ensure_ascii=True would inflate them to 6-byte \uXXXX escapes,
        # making the 64 KB cap ~3x tighter than the DB actually needs).
        try:
            blob_size = len(json.dumps(value, ensure_ascii=False).encode('utf-8'))
        except (TypeError, ValueError):
            raise serializers.ValidationError('conversation_history is not JSON-serializable.')
        if blob_size > _MAX_BLOB_BYTES:
            raise serializers.ValidationError(
                f'conversation_history too large (max {_MAX_BLOB_BYTES} bytes, got {blob_size}).'
            )

        # messages sub-list gate
        if 'messages' in value:
            messages = value['messages']
            if not isinstance(messages, list):
                raise serializers.ValidationError("conversation_history['messages'] must be a list.")
            if len(messages) > _MAX_CHAT_MESSAGES:
                raise serializers.ValidationError(
                    f"conversation_history['messages'] too long "
                    f"(max {_MAX_CHAT_MESSAGES} items, got {len(messages)})."
                )
            for i, item in enumerate(messages):
                if isinstance(item, dict):
                    text = item.get('text', '') or item.get('content', '') or ''
                    if isinstance(text, str) and len(text) > _MAX_TEXT_LEN:
                        raise serializers.ValidationError(
                            f"conversation_history['messages'][{i}].text too long "
                            f"(max {_MAX_TEXT_LEN} chars)."
                        )

        # history sub-list gate
        if 'history' in value:
            history = value['history']
            if not isinstance(history, list):
                raise serializers.ValidationError("conversation_history['history'] must be a list.")
            if len(history) > _MAX_HISTORY_LEN:
                raise serializers.ValidationError(
                    f"conversation_history['history'] too long "
                    f"(max {_MAX_HISTORY_LEN} items, got {len(history)})."
                )
            for i, item in enumerate(history):
                if isinstance(item, dict):
                    text = item.get('text', '')
                    if isinstance(text, str) and len(text) > _MAX_TEXT_LEN:
                        raise serializers.ValidationError(
                            f"conversation_history['history'][{i}].text too long "
                            f"(max {_MAX_TEXT_LEN} chars)."
                        )

        return value

    def update(self, instance, validated_data):
        # Edit Board / save-confirm must NOT bump updated_at (board ordering is by
        # -updated_at; only like/dislike swipes should move a board to the top).
        # Saving with explicit update_fields omits the auto_now updated_at column.
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if validated_data:
            instance.save(update_fields=list(validated_data.keys()))
        return instance

    class Meta:
        model  = Project
        fields = ['name', 'visibility', 'is_temp', 'conversation_history']
