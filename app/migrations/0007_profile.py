# Generated by Django 4.2.7 on 2024-04-07 01:57

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('app', '0006_alter_listing_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='profile', serialize=False, to=settings.AUTH_USER_MODEL, verbose_name='user')),
                ('name', models.CharField(blank=True, max_length=50, null=True)),
                ('about', models.TextField(blank=True, max_length=500, null=True)),
                ('location', models.CharField(blank=True, max_length=100, null=True)),
                ('profile_picture', models.ImageField(default='pfps/default_pfp.png', upload_to='pfps')),
            ],
        ),
    ]
