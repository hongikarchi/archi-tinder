"""
Management command: purge_legacy_projects

Bulk-delete legacy `Project` rows that predate the canonical_v2_buildings cutover
(default cutoff: 2026-05-14). Pre-cutover projects reference building ids in
the old schema and surface as broken cards / missing covers in the UI.

Related `AnalysisSession` / `SwipeEvent` rows are removed via the on_delete=CASCADE
foreign keys on those models (see apps/recommendation/models.py).

Safety:
  - Default mode is dry-run: prints counts per user + grand total, deletes nothing.
  - `--confirm` switches to destructive mode. Required to actually delete.
  - `--before YYYY-MM-DD` overrides the cutoff (UTC date, treated as <YYYY-MM-DDT00:00:00Z).

Usage:
    python manage.py purge_legacy_projects
    python manage.py purge_legacy_projects --before 2026-05-01
    python manage.py purge_legacy_projects --confirm
"""
from collections import Counter
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from apps.recommendation.models import Project


DEFAULT_CUTOFF = "2026-05-14"


class Command(BaseCommand):
    help = (
        "Bulk-delete legacy Project rows created before --before (default %s). "
        "Dry-run by default; pass --confirm to actually delete." % DEFAULT_CUTOFF
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--before",
            type=str,
            default=DEFAULT_CUTOFF,
            help="Cutoff date in YYYY-MM-DD format (UTC). Projects with "
                 "created_at < this date are targeted. Default: %s" % DEFAULT_CUTOFF,
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Actually delete. Without this flag, the command is dry-run only.",
        )

    def handle(self, *args, **options):
        before_str = options["before"]
        confirm = bool(options["confirm"])
        dry_run = not confirm

        try:
            cutoff = datetime.strptime(before_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise CommandError(
                "Invalid --before value %r; expected YYYY-MM-DD. (%s)" % (before_str, exc)
            )

        qs = Project.objects.filter(created_at__lt=cutoff).select_related("user__user")

        # Tally per-user count. Project.user is a FK to UserProfile (not auth.User).
        # Surface auth.User.username when available, else fall back to display_name,
        # else the profile id — both for human-friendly dry-run output.
        per_user = Counter()
        rows = qs.values_list(
            "user__user__username",  # auth.User.username
            "user__display_name",
            "user_id",               # UserProfile.id (fallback)
        )
        for username, display_name, user_id in rows:
            label = username or display_name or ("user_id=%s" % user_id)
            per_user[label] += 1
        total = sum(per_user.values())

        mode_label = "DRY-RUN" if dry_run else "DELETE"
        self.stdout.write(
            "purge_legacy_projects [%s] cutoff=%s (UTC)" % (mode_label, cutoff.isoformat())
        )
        if not per_user:
            self.stdout.write("No matching projects found.")
            self.stdout.write("TOTAL: 0 projects")
            return

        for label, count in sorted(per_user.items()):
            self.stdout.write("%s: %d projects" % (label, count))
        self.stdout.write("TOTAL: %d projects" % total)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "Dry-run only — no rows deleted. Re-run with --confirm to actually delete."
            ))
            return

        # Destructive path. .delete() returns (total_rows, {model: count})
        deleted_total, _by_model = qs.delete()
        self.stdout.write(self.style.SUCCESS("DELETED: %d projects" % total))
        self.stdout.write(
            "Cascade summary (includes related rows): %d total rows" % deleted_total
        )
