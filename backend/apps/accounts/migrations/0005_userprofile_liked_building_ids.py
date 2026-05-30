# Generated manually 2026-05-28 — SNS-LIKED-PROJECTS

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_userprofile_guest_onboarding_consent'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='liked_building_ids',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
