# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-10-08 11:26
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ninetofiver', '0082_auto_20181005_0622'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contractestimate',
            name='contract_role',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='ninetofiver.ContractRole'),
        ),
    ]
