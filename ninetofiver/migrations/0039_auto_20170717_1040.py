# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-07-17 10:40
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
        ('ninetofiver', '0038_auto_20170714_0947'),
    ]

    operations = [
        migrations.CreateModel(
            name='RedmineProjectInfo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('redmine_project_id', models.PositiveIntegerField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RedmineTimeEntryInfo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('redmine_time_entry_id', models.PositiveIntegerField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RedmineUserInfo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('redmine_user_id', models.PositiveIntegerField()),
                ('polymorphic_ctype', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_ninetofiver.redmineuserinfo_set+', to='contenttypes.ContentType')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.RemoveField(
            model_name='contract',
            name='redmine_project_id',
        ),
        migrations.RemoveField(
            model_name='performance',
            name='redmine_time_entry_id',
        ),
        migrations.RemoveField(
            model_name='userinfo',
            name='redmine_user_id',
        ),
        migrations.AddField(
            model_name='redminetimeentryinfo',
            name='performance',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='ninetofiver.Performance'),
        ),
        migrations.AddField(
            model_name='redminetimeentryinfo',
            name='polymorphic_ctype',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_ninetofiver.redminetimeentryinfo_set+', to='contenttypes.ContentType'),
        ),
        migrations.AddField(
            model_name='redmineprojectinfo',
            name='contract',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='ninetofiver.Contract'),
        ),
        migrations.AddField(
            model_name='redmineprojectinfo',
            name='polymorphic_ctype',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_ninetofiver.redmineprojectinfo_set+', to='contenttypes.ContentType'),
        ),
    ]