# Generated manually for FULL-LOGIN-REDESIGN-1 (PR 1 — backend).
# Adds 4 fields to UserProfile: is_guest, onboarding_role,
# consent_accepted_at, consent_policy_version.
#
# Migration number: 0004 (latest on develop was 0003).
# Codex's archived 0004 was on feature/codex-guest-auth-backend only —
# never applied to any environment — so this is safe to name 0004.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_userprofile_font_userprofile_theme'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_guest',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='onboarding_role',
            field=models.CharField(
                blank=True,
                choices=[
                    ('student', 'Student'),
                    ('architect', 'Architect'),
                    ('designer', 'Designer'),
                    ('enthusiast', 'Architecture Enthusiast'),
                    ('other', 'Other'),
                ],
                default='',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='consent_accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='consent_policy_version',
            field=models.CharField(default='1.0', max_length=10),
        ),
    ]
