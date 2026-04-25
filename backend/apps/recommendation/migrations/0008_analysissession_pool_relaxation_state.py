from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Sprint 0 A4: Add pool exhaustion guard state fields to AnalysisSession.

    Stores the original session-creation filters/priority/seed_ids so that
    refresh_pool_if_low() can re-run the 3-tier relaxation during swiping.
    Also tracks current_pool_tier (1/2/3) to avoid re-escalating needlessly.

    Legacy sessions (pre-0008) get empty defaults: original_filters={},
    original_filter_priority=[], original_seed_ids=[], current_pool_tier=1.
    If they exhaust mid-swipe, refresh_pool_if_low falls through to tier 3
    (random pool) — graceful degradation, not a regression.
    """
    dependencies = [
        ('recommendation', '0007_project_saved_ids_and_liked_intensity'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysissession',
            name='original_filters',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='analysissession',
            name='original_filter_priority',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='analysissession',
            name='original_seed_ids',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='analysissession',
            name='current_pool_tier',
            field=models.IntegerField(default=1),
        ),
    ]
