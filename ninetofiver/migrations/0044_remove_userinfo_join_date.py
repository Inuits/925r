# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-08-23 11:30
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ninetofiver', '0043_leavetype_description'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userinfo',
            name='join_date',
        ),
    ]
