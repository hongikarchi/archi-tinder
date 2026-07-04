from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0029_action_card_shown'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='analysissession',
            name='extended_rounds',
        ),
    ]
