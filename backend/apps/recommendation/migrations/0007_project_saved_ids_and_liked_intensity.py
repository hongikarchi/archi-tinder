from django.db import migrations, models


def backfill_liked_intensity(apps, schema_editor):
    """Convert legacy string entries in Project.liked_ids to {id, intensity:1.0} shape."""
    Project = apps.get_model('recommendation', 'Project')
    for project in Project.objects.all():
        new_liked = []
        changed = False
        for entry in project.liked_ids or []:
            if isinstance(entry, str):
                new_liked.append({'id': entry, 'intensity': 1.0})
                changed = True
            elif isinstance(entry, dict) and 'id' in entry:
                # Already migrated (idempotent guard if rerun); ensure intensity present.
                if 'intensity' not in entry:
                    entry = {**entry, 'intensity': 1.0}
                    changed = True
                new_liked.append(entry)
            # Silently drop malformed entries (defensive; should not happen in practice)
        if changed:
            project.liked_ids = new_liked
            project.save(update_fields=['liked_ids'])


def reverse_backfill(apps, schema_editor):
    """Reverse: convert dict entries back to plain strings. Loses intensity info."""
    Project = apps.get_model('recommendation', 'Project')
    for project in Project.objects.all():
        new_liked = []
        changed = False
        for entry in project.liked_ids or []:
            if isinstance(entry, dict) and 'id' in entry:
                new_liked.append(entry['id'])
                changed = True
            elif isinstance(entry, str):
                new_liked.append(entry)
        if changed:
            project.liked_ids = new_liked
            project.save(update_fields=['liked_ids'])


class Migration(migrations.Migration):
    dependencies = [
        ('recommendation', '0006_remove_total_rounds_and_scope_idempotency'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='saved_ids',
            field=models.JSONField(default=list),
        ),
        migrations.RunPython(backfill_liked_intensity, reverse_backfill),
    ]
