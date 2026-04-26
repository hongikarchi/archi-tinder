# Generated manually for Topic 01 Hybrid Retrieval (RRF)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0011_add_hyde_topic03'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysissession',
            name='original_q_text',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='sessionevent',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('session_start',      'Session Start'),
                    ('pool_creation',      'Pool Creation'),
                    ('swipe',              'Swipe'),
                    ('tag_answer',         'Tag Answer'),
                    ('confidence_update',  'Confidence Update'),
                    ('session_end',        'Session End'),
                    ('session_extend',     'Session Extend'),
                    ('bookmark',           'Bookmark'),
                    ('detail_view',        'Detail View'),
                    ('external_url_click', 'External URL Click'),
                    ('failure',            'Failure'),
                    ('probe_turn',         'Probe Turn'),
                    ('cohort_assignment',  'Cohort Assignment'),
                    ('parse_query_timing', 'Parse Query Timing'),
                    ('hyde_call_timing',   'HyDE Call Timing'),
                    ('hybrid_pool_timing', 'Hybrid Pool Timing'),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
