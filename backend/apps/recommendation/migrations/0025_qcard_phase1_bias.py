from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0024_project_axis_scores'),
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
