from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0019_normalize_legacy_entry_shapes'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysissession',
            name='tag_axis_counts',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='analysissession',
            name='recent_like_tag_sets',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='analysissession',
            name='question_cooldown',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='analysissession',
            name='q_card_consecutive_dislikes',
            field=models.IntegerField(default=0),
        ),
    ]
