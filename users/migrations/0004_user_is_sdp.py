# Generated by Django 4.0 on 2022-09-21 15:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_user_profile_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_sdp',
            field=models.BooleanField(default=False),
        ),
    ]
