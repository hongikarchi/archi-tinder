"""apps.messaging views — contact requests, conversations, blocks, reports.

Every view inherits MessagingView: the MESSAGING_ENABLED gate (404 when OFF,
D12) + authentication, plus a non-guest requirement for write methods.
Participant-only resources answer 404 (never 403) to non-participants so
existence is not revealed.
"""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.db import IntegrityError, transaction
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

from . import services
from .models import Block, ContactRequest, Conversation, Message, Report
from .permissions import MessagingEnabled
from .serializers import (
    ContactRequestCreateSerializer, MessageCreateSerializer, ReportCreateSerializer,
    last_message_dict, message_dict, user_summary,
)
from .throttling import ContactRequestThrottle, MessageSendThrottle, ReportThrottle

_EPOCH = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
_MESSAGES_LIMIT_DEFAULT = 50
_MESSAGES_LIMIT_MAX = 100
_CONVERSATIONS_CAP = 100


class MessagingView(APIView):
    """Base: flag gate -> auth -> (writes only) non-guest."""

    def get_permissions(self):
        perms = [MessagingEnabled(), IsAuthenticated()]
        if self.request.method not in SAFE_METHODS:
            perms.append(IsVerifiedUser())
        return perms

    def my_profile(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            raise Http404()
        return profile


def _unavailable():
    return Response({'detail': 'recipient_unavailable'}, status=status.HTTP_400_BAD_REQUEST)


def _sent():
    """The ONE success shape for every non-connecting outcome (D10: never reveal ignore)."""
    return Response({'status': 'sent'}, status=status.HTTP_201_CREATED)


# -- Contact requests -------------------------------------------------------

class ContactRequestCreateView(MessagingView):
    """POST /api/v1/contact-requests/ {recipient_id, greeting?}

    201 {status: 'sent'} for a normal send AND for every silent no-op (pending
    already / already connected / ignored within 30 days).
    201 {status: 'connected', conversation_id} when a reverse pending request
    existed (mutual interest -> auto-accept).
    """
    throttle_classes = [ContactRequestThrottle]

    def post(self, request):
        ser = ContactRequestCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sender = self.my_profile(request)
        greeting = ser.validated_data.get('greeting', '').strip()

        recipient = services.get_profile_by_auth_id(ser.validated_data['recipient_id'])
        if recipient is None:
            return _unavailable()
        if recipient.pk == sender.pk:
            return Response({'detail': 'self_request'}, status=status.HTTP_400_BAD_REQUEST)
        if services.is_blocked_between(sender, recipient) or not services.recipient_eligible(recipient):
            return _unavailable()

        now = timezone.now()
        with transaction.atomic():
            reverse = (
                ContactRequest.objects.select_for_update()
                .filter(sender=recipient, recipient=sender, status=ContactRequest.STATUS_PENDING)
                .first()
            )
            if reverse is not None:
                # Mutual interest: keep a record of the new request as accepted too,
                # stamped just before the system message so greetings stay chronological.
                new_req = ContactRequest.objects.create(
                    sender=sender, recipient=recipient, greeting=greeting,
                    status=ContactRequest.STATUS_ACCEPTED,
                    created_at=now - timedelta(milliseconds=1), responded_at=now,
                )
                reverse.status = ContactRequest.STATUS_ACCEPTED
                reverse.responded_at = now
                reverse.save(update_fields=['status', 'responded_at'])
                conv = services.connect([reverse, new_req], actor=sender, now=now)
                return Response(
                    {'status': 'connected', 'conversation_id': conv.pk},
                    status=status.HTTP_201_CREATED,
                )

            existing = services.find_conversation(sender, recipient)
            if existing is not None and existing.closed_at is None:
                return _sent()
            if ContactRequest.objects.filter(
                sender=sender, recipient=recipient, status=ContactRequest.STATUS_PENDING,
            ).exists():
                return _sent()
            if services.recent_ignore_exists(sender, recipient, now):
                return _sent()
            try:
                with transaction.atomic():
                    ContactRequest.objects.create(
                        sender=sender, recipient=recipient, greeting=greeting, created_at=now,
                    )
            except IntegrityError:
                # Concurrent duplicate pending request — same silent success.
                pass
        return _sent()


class ContactRequestReceivedView(MessagingView):
    """GET /api/v1/contact-requests/received/ — my pending requests, newest first."""

    def get(self, request):
        me = self.my_profile(request)
        qs = (
            ContactRequest.objects
            .filter(recipient=me, status=ContactRequest.STATUS_PENDING)
            .select_related('sender')
            .order_by('-created_at', '-id')
        )
        blocked = services.blocked_profile_ids(me)
        if blocked:
            qs = qs.exclude(sender_id__in=blocked)
        return Response({'results': [
            {
                'id': r.id,
                'sender': user_summary(r.sender),
                'greeting': r.greeting,
                'created_at': r.created_at,
            }
            for r in qs[:100]
        ]})


class ContactRequestStatusView(MessagingView):
    """GET /api/v1/contact-requests/status/?user_id= -> {state, can_request}.

    state: 'none' | 'sent' | 'connected'. Ignored (within the 30-day cooldown)
    maps to 'sent' — the sender is never told.
    """

    def get(self, request):
        me = self.my_profile(request)
        try:
            target_auth_id = int(request.query_params.get('user_id', ''))
        except (TypeError, ValueError):
            return Response({'detail': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
        target = services.get_profile_by_auth_id(target_auth_id)
        if target is None:
            raise Http404()

        is_self = target.pk == me.pk
        blocked = (not is_self) and services.is_blocked_between(me, target)
        can_request = (
            not is_self and not blocked and not me.is_guest
            and services.recipient_eligible(target)
        )

        state = 'none'
        if not is_self:
            conv = services.find_conversation(me, target)
            if conv is not None and conv.closed_at is None:
                state = 'connected'
            elif (
                ContactRequest.objects.filter(
                    sender=me, recipient=target, status=ContactRequest.STATUS_PENDING,
                ).exists()
                or services.recent_ignore_exists(me, target)
            ):
                state = 'sent'
        return Response({'state': state, 'can_request': can_request})


class ContactRequestAcceptView(MessagingView):
    """POST /api/v1/contact-requests/<id>/accept/ (recipient only, pending only)."""

    def post(self, request, request_id):
        me = self.my_profile(request)
        with transaction.atomic():
            cr = (
                ContactRequest.objects.select_for_update()
                .select_related('sender', 'recipient')
                .filter(pk=request_id, recipient=me)
                .first()
            )
            if cr is None:
                raise Http404()
            if cr.status != ContactRequest.STATUS_PENDING:
                return Response({'detail': 'not_pending'}, status=status.HTTP_409_CONFLICT)
            if services.is_blocked_between(me, cr.sender):
                return Response({'detail': 'blocked'}, status=status.HTTP_400_BAD_REQUEST)
            now = timezone.now()
            cr.status = ContactRequest.STATUS_ACCEPTED
            cr.responded_at = now
            cr.save(update_fields=['status', 'responded_at'])
            conv = services.connect([cr], actor=me, now=now)
        return Response({'status': 'accepted', 'conversation_id': conv.pk})


class ContactRequestIgnoreView(MessagingView):
    """POST /api/v1/contact-requests/<id>/ignore/ (recipient only, pending only)."""

    def post(self, request, request_id):
        me = self.my_profile(request)
        with transaction.atomic():
            cr = (
                ContactRequest.objects.select_for_update()
                .filter(pk=request_id, recipient=me)
                .first()
            )
            if cr is None:
                raise Http404()
            if cr.status != ContactRequest.STATUS_PENDING:
                return Response({'detail': 'not_pending'}, status=status.HTTP_409_CONFLICT)
            cr.status = ContactRequest.STATUS_IGNORED
            cr.responded_at = timezone.now()
            cr.save(update_fields=['status', 'responded_at'])
        return Response({'status': 'ignored'})


# -- Conversations ----------------------------------------------------------

def _get_conversation_or_404(me, conversation_id):
    conv = Conversation.objects.filter(pk=conversation_id).first()
    if conv is None or not conv.is_participant(me):
        raise Http404()
    return conv


class ConversationListView(MessagingView):
    """GET /api/v1/conversations/ — mine, last_message_at desc."""

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
        return []

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
    """GET /api/v1/messages/unread-count/ -> {count}: pending requests + unread messages."""

    def get(self, request):
        me = self.my_profile(request)
        return Response({
            'count': services.pending_received_count(me) + services.unread_message_count(me),
        })


# -- Block / Report ---------------------------------------------------------

class BlockView(MessagingView):
    """POST/DELETE /api/v1/users/<user_id>/block/ (user_id = auth User id)."""

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
        return Response({'blocked': True}, status=status.HTTP_201_CREATED)

    def delete(self, request, user_id):
        me = self.my_profile(request)
        target = self._target(me, user_id)
        # Conversation stays closed (design §4).
        Block.objects.filter(blocker=me, blocked=target).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportView(MessagingView):
    """POST /api/v1/reports/ {target_type, target_id, reason?}"""
    throttle_classes = [ReportThrottle]

    def post(self, request):
        ser = ReportCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        me = self.my_profile(request)
        target_type = ser.validated_data['target_type']
        target_id = ser.validated_data['target_id'].strip()
        reason = ser.validated_data.get('reason', '').strip()

        if target_type == Report.TARGET_MESSAGE:
            if not target_id.isdigit():
                return Response({'detail': 'invalid target_id'}, status=status.HTTP_400_BAD_REQUEST)
            msg = Message.objects.select_related('conversation').filter(pk=int(target_id)).first()
            # Non-participants get 404 — message existence is not revealed.
            if msg is None or not msg.conversation.is_participant(me):
                raise Http404()
            if msg.kind == Message.KIND_SYSTEM:
                return Response({'detail': 'system_message_not_reportable'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            if not target_id.isdigit():
                return Response({'detail': 'invalid target_id'}, status=status.HTTP_400_BAD_REQUEST)
            target = services.get_profile_by_auth_id(int(target_id))
            if target is None:
                raise Http404()
            if target.pk == me.pk:
                return Response({'detail': 'self_report'}, status=status.HTTP_400_BAD_REQUEST)

        report = Report.objects.create(
            reporter=me, target_type=target_type, target_id=target_id, reason=reason,
        )
        return Response({'id': report.id}, status=status.HTTP_201_CREATED)
