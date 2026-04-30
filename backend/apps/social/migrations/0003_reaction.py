from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0002_rename_social_foll_followee_idx_social_foll_followe_0eabb0_idx_and_more'),
        ('recommendation', '0016_alter_sessionevent_event_type'),
        ('accounts', '0002_userprofile_phase13_extension'),
    ]

    operations = [
        migrations.CreateModel(
            name='Reaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reactions',
                    to='accounts.userprofile',
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reactions',
                    to='recommendation.project',
                )),
            ],
            options={
                'indexes': [
                    models.Index(fields=['project', '-created_at'], name='social_reac_project_idx'),
                ],
                'unique_together': {('user', 'project')},
            },
        ),
    ]
