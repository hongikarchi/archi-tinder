from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0026_qcard_phase1_bias'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysissession',
            name='recent_latencies',
            field=models.JSONField(default=list),
        ),
    ]
