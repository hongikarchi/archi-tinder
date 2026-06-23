from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0027_session_recent_latencies'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='is_temp',
            field=models.BooleanField(default=False),
        ),
    ]
