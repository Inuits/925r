# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2016-12-24 13:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ninetofiver', '0009_contract_performance_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='performance_types',
            field=models.ManyToManyField(blank=True, to='ninetofiver.PerformanceType'),
        ),
    ]