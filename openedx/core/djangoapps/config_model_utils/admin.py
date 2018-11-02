from django import forms

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.lib.courses import clean_course_id

from config_models.admin import ConfigurationModelAdmin


class CourseOverviewField(forms.ModelChoiceField):
    def to_python(self, value):
        if value in self.empty_values:
            return None
        return super(CourseOverviewField, self).to_python(CourseKey.from_string(value))


class StackedConfigModelAdminForm(forms.ModelForm):
    class Meta:
        field_classes = {
            'course': CourseOverviewField
        }


class StackedConfigModelAdmin(ConfigurationModelAdmin):
    form = StackedConfigModelAdminForm
