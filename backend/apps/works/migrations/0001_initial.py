import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Work',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('upload_id', models.CharField(max_length=20, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('program', models.CharField(choices=[('residential', 'Residential'), ('commercial', 'Commercial'), ('cultural', 'Cultural'), ('educational', 'Educational'), ('healthcare', 'Healthcare'), ('hospitality', 'Hospitality'), ('industrial', 'Industrial'), ('infrastructure', 'Infrastructure'), ('landscape', 'Landscape'), ('mixed_use', 'Mixed Use'), ('office', 'Office'), ('public', 'Public'), ('religious', 'Religious'), ('sports', 'Sports')], max_length=20)),
                ('location_city', models.CharField(blank=True, max_length=100)),
                ('location_country', models.CharField(blank=True, max_length=100)),
                ('project_year', models.IntegerField(blank=True, null=True)),
                ('r2_keys', models.JSONField(default=list)),
                ('is_copyright_confirmed', models.BooleanField(default=False)),
                ('is_publishable', models.BooleanField(default=False)),
                ('gate_reason', models.CharField(blank=True, max_length=500)),
                ('report_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='works',
                    to='accounts.userprofile',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='work',
            index=models.Index(fields=['owner', 'is_publishable'], name='works_work_owner_i_idx'),
        ),
    ]
