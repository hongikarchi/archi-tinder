"""SNS-FOLLOW-1: contact request -> follow. Retire ContactRequest WITHOUT deleting data.

The DB is shared (and also prod), so nothing here deletes rows or tables:

1. RunPython `convert_contact_requests` — carry existing relations over to
   social.UserFollow so nobody loses a connection:
     accepted -> follow edges in BOTH directions (existing relations survive a
                 later discovery opt-out, so no opt-out check);
     pending  -> one edge sender -> recipient, skipped when the recipient is a
                 guest or opted out of discovery (the accepts_new_followers rule,
                 replicated inline: services cannot be imported in a migration);
     ignored  -> not converted.
   A pair with a Block in either direction is skipped; self edges are never
   created. Idempotent (ignore_conflicts), a no-op with 0 accepted + 0 pending
   rows, and it prints the per-status counts and the number of follows created.
   Reverse is a no-op (the follow edges are kept on a rollback).

2. Drop the FOREIGN KEY constraints of the orphaned messaging_contactrequest
   table (Postgres only; no-op elsewhere or when the table is missing). Once
   Django no longer knows the model it will not cascade, so deleting a
   UserProfile that still has old ContactRequest rows would hit an FK violation
   (account deletion, #412). Constraints only — no rows, no table. Reverse no-op.
   (Done with RunPython + schema_editor.execute so the Postgres-only DO block is
   skipped on the SQLite test database; it is the same SQL RunSQL would run.)

3. SeparateDatabaseAndState: forget the ContactRequest model in migration state
   only. The messaging_contactrequest table stays in the database; a follow-up
   issue will drop it.
"""
from django.db import migrations

_STATUS_ACCEPTED = 'accepted'
_STATUS_PENDING = 'pending'


def plan_follows(rows, blocked_pairs, ineligible_pending_recipient_ids):
    """Pure conversion rule. Returns a set of (follower_id, following_id).

    rows: iterable of (sender_id, recipient_id, status) UserProfile pks.
    blocked_pairs: iterable of (blocker_id, blocked_id); a block in either
        direction skips the pair.
    ineligible_pending_recipient_ids: recipients (guest / discovery opt-out) that
        a PENDING request must not convert for. Accepted rows ignore it.
    """
    blocked = {frozenset(p) for p in blocked_pairs}
    ineligible = set(ineligible_pending_recipient_ids)
    edges = set()
    for sender_id, recipient_id, status in rows:
        if sender_id == recipient_id or frozenset((sender_id, recipient_id)) in blocked:
            continue
        if status == _STATUS_ACCEPTED:
            edges.add((sender_id, recipient_id))
            edges.add((recipient_id, sender_id))
        elif status == _STATUS_PENDING and recipient_id not in ineligible:
            edges.add((sender_id, recipient_id))
    return edges


def convert_contact_requests(apps, schema_editor):
    ContactRequest = apps.get_model('messaging', 'ContactRequest')
    Block = apps.get_model('messaging', 'Block')
    UserFollow = apps.get_model('social', 'UserFollow')
    UserProfile = apps.get_model('accounts', 'UserProfile')
    PersonalityProfile = apps.get_model('accounts', 'PersonalityProfile')

    counts = {}
    for status in ContactRequest.objects.values_list('status', flat=True):
        counts[status] = counts.get(status, 0) + 1
    print(
        f'\n  [SNS-FOLLOW-1] contact requests by status: {counts or "none"}',
    )
    if not counts.get(_STATUS_ACCEPTED) and not counts.get(_STATUS_PENDING):
        print('  [SNS-FOLLOW-1] nothing to convert (0 accepted, 0 pending)')
        return

    rows = list(
        ContactRequest.objects
        .filter(status__in=[_STATUS_ACCEPTED, _STATUS_PENDING])
        .values_list('sender_id', 'recipient_id', 'status')
    )
    blocked_pairs = list(Block.objects.values_list('blocker_id', 'blocked_id'))
    pending_recipients = {r for _, r, status in rows if status == _STATUS_PENDING}
    ineligible = set(
        UserProfile.objects.filter(pk__in=pending_recipients, is_guest=True)
        .values_list('pk', flat=True)
    ) | set(
        PersonalityProfile.objects.filter(
            user_id__in=pending_recipients, discovery_opt_in=False,
        ).values_list('user_id', flat=True)
    )

    edges = plan_follows(rows, blocked_pairs, ineligible)
    before = UserFollow.objects.count()
    UserFollow.objects.bulk_create(
        [UserFollow(follower_id=f, following_id=t) for f, t in sorted(edges)],
        ignore_conflicts=True,
    )
    created = UserFollow.objects.count() - before
    print(f'  [SNS-FOLLOW-1] follows created: {created} (planned {len(edges)})')


_DROP_CONTACTREQUEST_FKS = """
DO $$
DECLARE r record;
BEGIN
    IF to_regclass('messaging_contactrequest') IS NOT NULL THEN
        FOR r IN
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'messaging_contactrequest'::regclass AND contype = 'f'
        LOOP
            EXECUTE format('ALTER TABLE messaging_contactrequest DROP CONSTRAINT %I', r.conname);
        END LOOP;
    END IF;
END $$;
"""


def drop_contactrequest_fks(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    # params=None: the SQL contains a literal %I (format()), so skip %-placeholder parsing.
    schema_editor.execute(_DROP_CONTACTREQUEST_FKS, params=None)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_personalityprofile'),
        ('messaging', '0001_initial'),
        ('social', '0008_userfollow'),
    ]

    operations = [
        migrations.RunPython(convert_contact_requests, reverse_code=noop),
        migrations.RunPython(drop_contactrequest_fks, reverse_code=noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.DeleteModel(name='ContactRequest')],
            database_operations=[],
        ),
    ]
