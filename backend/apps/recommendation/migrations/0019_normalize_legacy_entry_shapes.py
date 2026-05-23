"""
0019 -- Normalize legacy str entries in Project.liked_ids / saved_ids to dict shape.

Background:
    Early swipe writes stored building IDs as bare strings (e.g. 'bld_000344')
    in liked_ids and saved_ids.  The canonical schema is list[dict] where every
    entry has at minimum an 'id' key (plus optional 'intensity' / 'saved_at').

    projects.py:116 calls item.get('id') on every entry — str entries have no
    .get() method and raise AttributeError → 500 on remove_building_ids PATCH.

Migration semantics:
    Forward: iterate every Project row; for each str entry e in liked_ids /
    saved_ids, replace with {'id': e}.  Dict entries are left untouched.
    Only .save() rows that actually changed (update_fields=['liked_ids',
    'saved_ids'] only) — intentionally excludes updated_at so timestamps
    reflect the last real user edit, not this housekeeping run.

    Reverse: RunPython.noop — dict→str is lossy; legacy strings are deprecated
    forever. Rolling back this migration is therefore a no-op (data stays dict-
    shaped, which the codebase already handles correctly).

    Idempotent: a second run finds no str entries and skips every row.
"""
from django.db import migrations


def normalize_entry_shapes(apps, schema_editor):
    """Convert any str entry in liked_ids / saved_ids to {'id': <string>}."""
    Project = apps.get_model('recommendation', 'Project')

    for project in Project.objects.only('pk', 'liked_ids', 'saved_ids').iterator(chunk_size=500):
        changed = False

        new_liked = []
        for entry in (project.liked_ids or []):
            if isinstance(entry, str):
                new_liked.append({'id': entry})
                changed = True
            else:
                new_liked.append(entry)

        new_saved = []
        for entry in (project.saved_ids or []):
            if isinstance(entry, str):
                new_saved.append({'id': entry})
                changed = True
            else:
                new_saved.append(entry)

        if changed:
            project.liked_ids = new_liked
            project.saved_ids = new_saved
            project.save(update_fields=['liked_ids', 'saved_ids'])


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0018_rename_swipeevent_canonical_bld_id'),
    ]

    operations = [
        migrations.RunPython(normalize_entry_shapes, migrations.RunPython.noop),
    ]
