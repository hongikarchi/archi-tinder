from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0030_remove_extended_rounds'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='analysissession',
            name='recent_latencies',
        ),
        migrations.RemoveField(
            model_name='analysissession',
            name='question_count',
        ),
        migrations.RemoveField(
            model_name='analysissession',
            name='question_cooldown',
        ),
        migrations.RemoveField(
            model_name='analysissession',
            name='q_card_consecutive_dislikes',
        ),
    ]
