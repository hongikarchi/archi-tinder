from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0025_analysissession_multimodal_floor'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysissession',
            name='question_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='analysissession',
            name='question_bias_vector',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
