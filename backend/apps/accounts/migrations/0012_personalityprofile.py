import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_login_onboard_1_unified_id_and_is_guest'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalityProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('axis_1', models.FloatField()),
                ('axis_2', models.FloatField()),
                ('axis_3', models.FloatField()),
                ('axis_4', models.FloatField()),
                ('axis_5', models.FloatField()),
                ('type_code', models.CharField(max_length=4)),
                ('discovery_opt_in', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='personality',
                        to='accounts.userprofile',
                    ),
                ),
            ],
            options={
                'indexes': [
                    models.Index(
                        fields=['discovery_opt_in'],
                        name='personality_optin_idx',
                    ),
                ],
            },
        ),
    ]
