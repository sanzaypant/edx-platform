"""
Course Duration Limit Configuration Models
"""

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime
from django.db import models
from django.utils.translation import ugettext as _

from student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.config_model_utils.models import StackedConfigurationModel
from openedx.features.course_duration_limits.config import CONTENT_TYPE_GATING_FLAG


class CourseDurationLimitConfig(StackedConfigurationModel):

    STACKABLE_FIELDS = ('enabled', 'enabled_as_of')

    enabled_as_of = models.DateField(default=None, null=True, verbose_name=_('Enabled As Of'), blank=True)

    @classmethod
    def enabled_for_enrollment(cls, enrollment=None, user=None, course_key=None, today=None):
        if CONTENT_TYPE_GATING_FLAG.is_enabled():
            return True

        if enrollment is not None and (user is not None or course_key is not None):
            raise ValueError('Specify enrollment or user/course_key, but not both')

        if enrollment is None and (user is None or course_key is None):
            raise ValueError('Both user and course_key must be specified if no enrollment is provided')

        if enrollment is None and user is None and course_key is None:
            raise ValueError('At least one of enrollment or user and course_key must be specified')

        if course_key is None:
            course_key = enrollment.course_id

        if enrollment is None:
            enrollment = CourseEnrollment.get_enrollment(user, course_key)

        if enrollment is None:
            return cls.enabled_for_course(course_key=course_key, today=today)
        else:
            current_config = cls.current(course_key=enrollment.course_id)
            return current_config.enabled_now(today=enrollment.created.date())

    @classmethod
    def enabled_for_course(cls, course_key, today=None):
        if CONTENT_TYPE_GATING_FLAG.is_enabled():
            return True

        current_config = cls.current(course_key=course_key)
        return current_config.enabled_now(today=today)

    def clean(self):
        if self.enabled and self.enabled_as_of is None:
            raise ValidationError({'enabled_as_of': _('enabled_as_of must be set when enabled is True')})

    def enabled_now(self, today=None):
        if CONTENT_TYPE_GATING_FLAG.is_enabled():
            return True

        if today is None:
            today = datetime.utcnow().date()

        return bool(self.enabled and self.enabled_as_of <= today)

