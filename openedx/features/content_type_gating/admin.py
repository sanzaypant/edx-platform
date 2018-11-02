# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from openedx.core.djangoapps.config_model_utils.admin import StackedConfigModelAdmin
from .models import ContentTypeGatingConfig


admin.site.register(ContentTypeGatingConfig, StackedConfigModelAdmin)
