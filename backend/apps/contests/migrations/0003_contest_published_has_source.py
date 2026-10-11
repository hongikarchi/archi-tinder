from django.db import migrations, models


def demote_published_without_source(apps, schema_editor):
    """The new CHECK would fail on pre-existing published rows with a blank source_url
    (e.g. a dev-seeded 한옥디자인 row): park them as pending instead."""
    Contest = apps.get_model('contests', 'Contest')
    Contest.objects.filter(status='published', source_url='').update(status='pending')


class Migration(migrations.Migration):

    dependencies = [
        ('contests', '0002_contest_interest_and_url_checks'),
    ]

    operations = [
        migrations.RunPython(demote_published_without_source, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='contest',
            constraint=models.CheckConstraint(
                condition=models.Q(('source_url', ''), ('status', 'published'), _negated=True),
                name='contest_published_has_source',
            ),
        ),
    ]
