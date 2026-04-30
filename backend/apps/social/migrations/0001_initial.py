from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0002_userprofile_phase13_extension'),
    ]

    operations = [
        migrations.CreateModel(
            name='Follow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('follower', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='following_set',
                    to='accounts.userprofile',
                )),
                ('followee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='follower_set',
                    to='accounts.userprofile',
                )),
            ],
            options={
                'indexes': [
                    models.Index(fields=['followee', '-created_at'], name='social_foll_followee_idx'),
                ],
                'unique_together': {('follower', 'followee')},
            },
        ),
    ]
