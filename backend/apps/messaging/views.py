"""apps.messaging views — conversations, messages, blocks, reports.

Every view inherits MessagingView: the MESSAGING_ENABLED gate (404 when OFF,
D12) + authentication, plus a non-guest requirement for write methods. Block and
Report use MessagingOrFollowEnabled instead (reachable when either flag is on).
Opening a conversation additionally needs FOLLOW_ENABLED and that the requester
follows the peer (SNS-FOLLOW-1); replying inside an existing conversation only
needs participant + open + not blocked. Participant-only resources answer 404
(never 403) to non-participants so existence is not revealed.
"""
from datetime import datetime, timezone as dt_timezone

from django.db import transaction
from django.db.models import (
    Case, Count, DateTimeField, F, IntegerField, OuterRef, Q, Subquery, Value, When,
)
from django.db.models.functions import Coalesce
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserProfile
from apps.accounts.permissions import IsVerifiedUser
from apps.social import services as social_services
from apps.social.models import UserFollow
from apps.social.permissions import FollowEnabled

from . import services
from .models import Block, Conversation, Message, Report
from .permissions import MessagingEnabled, MessagingOrFollowEnabled
from .serializers import (
    ConversationOpenSerializer, MessageCreateSerializer, ReportCreateSerializer,
    last_message_dict, message_dict, user_summary,
)
from .throttling import (
    ConversationOpenThrottle, MessageReadThrottle, MessageSendThrottle, ReportThrottle,
)

_EPOCH = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
_MESSAGES_LIMIT_DEFAULT = 50
_MESSAGES_LIMIT_MAX = 100
_CONVERSATIONS_CAP = 100


class MessagingView(APIView):
    """Base: flag gate -> auth -> (writes only) non-guest."""
    flag_permission = MessagingEnabled

    def get_permissions(self):
        perms = [self.flag_permission(), IsAuthenticated()]
        if self.request.method not in SAFE_METHODS:
            perms.append(IsVerifiedUser())
        return perms

    def my_profile(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            raise Http404()
        return profile


# -- Conversations ----------------------------------------------------------

def _get_conversation_or_404(me, conversation_id):
    if not services.id_in_range(conversation_id):
        raise Http404()
    conv = Conversation.objects.filter(pk=conversation_id).first()
    if conv is None or not conv.is_participant(me):
        raise Http404()
    return conv


class ConversationListView(MessagingView):
    """GET /api/v1/conversations/ — mine, last_message_at desc.

    POST /api/v1/conversations/ {peer_user_id} — open (or reuse) the 1:1
    conversation with a user I follow. Needs MESSAGING_ENABLED AND FOLLOW_ENABLED
    (404 otherwise), auth, a verified (non-guest) user.
      400 bad / out-of-range / self peer_user_id; 404 unknown peer;
      403 {'detail': 'not_allowed'} unless I follow the peer AND no block either
      way (one identical body for both reasons);
      201 {id, other, closed: false} when created, 200 when it already existed
      (a conversation closed by an earlier block is reopened -> 200).
    No system message is written. Replies are NOT gated on follow.
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [
                MessagingEnabled(), FollowEnabled(), IsAuthenticated(), IsVerifiedUser(),
            ]
        return super().get_permissions()

    def get_throttles(self):
        if self.request.method == 'POST':
            return [ConversationOpenThrottle()]
        return [MessageReadThrottle()]

    def post(self, request):
        ser = ConversationOpenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        peer_auth_id = ser.validated_data['peer_user_id']
        if not services.id_in_range(peer_auth_id, services.AUTH_USER_ID_MAX):
            return Response({'detail': 'invalid peer_user_id'}, status=status.HTTP_400_BAD_REQUEST)
        me = self.my_profile(request)
        peer = services.get_profile_by_auth_id(peer_auth_id)
        if peer is None:
            raise Http404()
        if peer.pk == me.pk:
            return Response({'detail': 'self_conversation'}, status=status.HTTP_400_BAD_REQUEST)
        if (
            not social_services.is_following(me, peer)
            or services.is_blocked_between(me, peer)
        ):
            return Response({'detail': 'not_allowed'}, status=status.HTTP_403_FORBIDDEN)
        conv, created = services.open_conversation(me, peer)
        return Response(
            {'id': conv.id, 'other': user_summary(peer), 'closed': False},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def get(self, request):
        me = self.my_profile(request)
        my_last_read = Coalesce(
            Case(When(user_a=me, then=F('a_last_read_at')), default=F('b_last_read_at')),
            Value(_EPOCH), output_field=DateTimeField(),
        )
        unread_sq = (
            Message.objects
            .filter(conversation=OuterRef('pk'), created_at__gt=OuterRef('my_last_read'))
            .filter(Q(sender__isnull=True) | ~Q(sender=me))
            .order_by().values('conversation').annotate(c=Count('id')).values('c')
        )
        last_id_sq = (
            Message.objects.filter(conversation=OuterRef('pk')).order_by('-id').values('id')[:1]
        )
        convs = list(
            Conversation.objects
            .filter(Q(user_a=me) | Q(user_b=me))
            .select_related('user_a', 'user_b')
            .annotate(
                my_last_read=my_last_read,
                unread=Coalesce(Subquery(unread_sq, output_field=IntegerField()), Value(0)),
                last_msg_id=Subquery(last_id_sq),
            )
            .order_by(F('last_message_at').desc(nulls_last=True), '-id')[:_CONVERSATIONS_CAP]
        )
        last_ids = [c.last_msg_id for c in convs if c.last_msg_id]
        last_msgs = Message.objects.in_bulk(last_ids)
        results = []
        for c in convs:
            other = c.user_b if c.user_a_id == me.pk else c.user_a
            last = last_msgs.get(c.last_msg_id)
            results.append({
                'id': c.id,
                'other': user_summary(other),
                'last_message': last_message_dict(last) if last else None,
                'last_message_at': c.last_message_at,
                'unread_count': 0 if c.closed_at else c.unread,
                'closed': c.closed_at is not None,
            })
        return Response({'results': results})


class ConversationMessagesView(MessagingView):
    """GET/POST /api/v1/conversations/<id>/messages/"""

    def get_throttles(self):
        if self.request.method == 'POST':
            return [MessageSendThrottle()]
        return [MessageReadThrottle()]

    def get(self, request, conversation_id):
        me = self.my_profile(request)
        conv = _get_conversation_or_404(me, conversation_id)
        try:
            limit = int(request.query_params.get('limit', _MESSAGES_LIMIT_DEFAULT))
        except (TypeError, ValueError):
            limit = _MESSAGES_LIMIT_DEFAULT
        limit = max(1, min(limit, _MESSAGES_LIMIT_MAX))

        qs = Message.objects.filter(conversation=conv).select_related('sender')
        after = request.query_params.get('after')
        if after not in (None, ''):
            try:
                after_id = int(after)
            except (TypeError, ValueError):
                return Response({'detail': 'after must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
            # Clamp to the id column's range: an oversized cursor is "past the end".
            after_id = max(0, min(after_id, services.BIGINT_ID_MAX))
            msgs = list(qs.filter(id__gt=after_id).order_by('id')[:limit])
        else:
            # Initial load: the latest `limit` messages, still returned ascending.
            msgs = list(qs.order_by('-id')[:limit])
            msgs.reverse()
        return Response({
            'results': [message_dict(m, viewer=me) for m in msgs],
            'closed': conv.closed_at is not None,
        })

    def post(self, request, conversation_id):
        me = self.my_profile(request)
        ser = MessageCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            conv = _get_conversation_or_404(me, conversation_id)
            conv = Conversation.objects.select_for_update().get(pk=conv.pk)
            if conv.closed_at is not None:
                return Response({'detail': 'conversation_closed'}, status=status.HTTP_403_FORBIDDEN)
            other = UserProfile.objects.get(pk=conv.other_id(me))
            if services.is_blocked_between(me, other):
                return Response({'detail': 'blocked'}, status=status.HTTP_403_FORBIDDEN)
            now = timezone.now()
            msg = Message.objects.create(
                conversation=conv, sender=me, kind=Message.KIND_USER,
                body=ser.validated_data['body'], created_at=now,
            )
            conv.last_message_at = now
            setattr(conv, conv.last_read_field(me), now)
            conv.save(update_fields=['last_message_at', conv.last_read_field(me)])
        return Response(message_dict(msg, viewer=me), status=status.HTTP_201_CREATED)


class ConversationReadView(MessagingView):
    """POST /api/v1/conversations/<id>/read/ — mark everything up to now as read."""

    def post(self, request, conversation_id):
        me = self.my_profile(request)
        conv = _get_conversation_or_404(me, conversation_id)
        Conversation.objects.filter(pk=conv.pk).update(
            **{conv.last_read_field(me): timezone.now()}
        )
        return Response({'status': 'ok'})


class UnreadCountView(MessagingView):
    """GET /api/v1/messages/unread-count/ -> {count}: unread messages only."""
    throttle_classes = [MessageReadThrottle]

    def get(self, request):
        me = self.my_profile(request)
        return Response({'count': services.unread_message_count(me)})


# -- Block / Report ---------------------------------------------------------

class BlockView(MessagingView):
    """POST/DELETE /api/v1/users/<user_id>/block/ (user_id = auth User id).

    Reachable when EITHER MESSAGING_ENABLED or FOLLOW_ENABLED is on. POST also
    deletes the follow edges between the pair in BOTH directions (unblock does
    not restore them).
    """
    flag_permission = MessagingOrFollowEnabled

    def _target(self, me, user_id):
        target = services.get_profile_by_auth_id(user_id)
        if target is None:
            raise Http404()
        return target

    def post(self, request, user_id):
        me = self.my_profile(request)
        target = self._target(me, user_id)
        if target.pk == me.pk:
            return Response({'detail': 'self_block'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            Block.objects.get_or_create(blocker=me, blocked=target)
            lo, hi = services.pair(me, target)
            Conversation.objects.filter(
                user_a=lo, user_b=hi, closed_at__isnull=True,
            ).update(closed_at=timezone.now())
            removed, _ = UserFollow.objects.filter(
                Q(follower=me, following=target) | Q(follower=target, following=me)
            ).delete()
        if removed:
            social_services.evict_follow_counts_cache(me, target)
        return Response({'blocked': True}, status=status.HTTP_201_CREATED)

    def delete(self, request, user_id):
        me = self.my_profile(request)
        target = self._target(me, user_id)
        # Conversation stays closed (design §4).
        Block.objects.filter(blocker=me, blocked=target).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportView(MessagingView):
    """POST /api/v1/reports/ {target_type, target_id, reason?}

    Reachable when EITHER MESSAGING_ENABLED or FOLLOW_ENABLED is on.
    """
    flag_permission = MessagingOrFollowEnabled
    throttle_classes = [ReportThrottle]

    def post(self, request):
        ser = ReportCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        me = self.my_profile(request)
        target_type = ser.validated_data['target_type']
        target_id = ser.validated_data['target_id'].strip()
        reason = ser.validated_data.get('reason', '').strip()

        # ASCII digits only (str.isdigit() also accepts e.g. '²', which int() rejects),
        # and the value must fit the target's id column -> 400, never a DB DataError.
        if not (target_id.isascii() and target_id.isdigit()):
            return Response({'detail': 'invalid target_id'}, status=status.HTTP_400_BAD_REQUEST)
        max_id = (
            services.BIGINT_ID_MAX if target_type == Report.TARGET_MESSAGE
            else services.AUTH_USER_ID_MAX
        )
        if not services.id_in_range(int(target_id), max_id):
            return Response({'detail': 'invalid target_id'}, status=status.HTTP_400_BAD_REQUEST)

        if target_type == Report.TARGET_MESSAGE:
            msg = Message.objects.select_related('conversation').filter(pk=int(target_id)).first()
            # Non-participants get 404 — message existence is not revealed.
            if msg is None or not msg.conversation.is_participant(me):
                raise Http404()
            if msg.kind == Message.KIND_SYSTEM:
                return Response({'detail': 'system_message_not_reportable'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            target = services.get_profile_by_auth_id(int(target_id))
            if target is None:
                raise Http404()
            if target.pk == me.pk:
                return Response({'detail': 'self_report'}, status=status.HTTP_400_BAD_REQUEST)

        report = Report.objects.create(
            reporter=me, target_type=target_type, target_id=target_id, reason=reason,
        )
        return Response({'id': report.id}, status=status.HTTP_201_CREATED)
