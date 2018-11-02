import ddt
from datetime import timedelta, date, datetime, time
import itertools
from mock import Mock

from openedx.core.djangoapps.site_configuration.tests.factories import SiteConfigurationFactory
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from openedx.core.djangoapps.waffle_utils.testutils import override_waffle_flag
from openedx.core.djangolib.testing.utils import CacheIsolationTestCase
from openedx.features.content_type_gating.models import ContentTypeGatingConfig
from openedx.features.course_duration_limits.config import CONTENT_TYPE_GATING_FLAG
from student.tests.factories import CourseEnrollmentFactory, UserFactory



@ddt.ddt
class TestContentTypeGatingConfig(CacheIsolationTestCase):

    def setUp(self):
        self.course_overview = CourseOverviewFactory.create()
        self.user = UserFactory.create()
        super(TestContentTypeGatingConfig, self).setUp()

    @ddt.data(
        (True, True, True),
        (True, True, False),
        (True, False, True),
        (True, False, False),
        (False, False, True),
        (False, False, False),
    )
    @ddt.unpack
    def test_enabled_for_enrollment(
        self,
        already_enrolled,
        pass_enrollment,
        enrolled_before_enabled,
    ):
        config = ContentTypeGatingConfig.objects.create(
            enabled=True,
            course=self.course_overview,
            enabled_as_of=date(2018, 1, 1),
        )

        if already_enrolled:
            if enrolled_before_enabled:
                enrollment_create_date = config.enabled_as_of - timedelta(days=1)
            else:
                enrollment_create_date = config.enabled_as_of + timedelta(days=1)

            today = None

            existing_enrollment = CourseEnrollmentFactory.create(
                user=self.user,
                course=self.course_overview,
            )
            existing_enrollment.created = datetime.combine(enrollment_create_date, time())
            existing_enrollment.save()
        else:
            existing_enrollment = None
            if enrolled_before_enabled:
                today = config.enabled_as_of - timedelta(days=1)
            else:
                today = config.enabled_as_of + timedelta(days=1)

        if pass_enrollment:
            enrollment = existing_enrollment
            user = None
            course_key = None
        else:
            enrollment = None
            user = self.user
            course_key = self.course_overview.id

        if pass_enrollment:
            query_count = 4
        else:
            query_count = 5

        with self.assertNumQueries(query_count):
            enabled = ContentTypeGatingConfig.enabled_for_enrollment(
                enrollment=enrollment,
                user=user,
                course_key=course_key,
                today=today,
            )
            self.assertEqual(not enrolled_before_enabled, enabled)


    def test_enabled_for_enrollment_failure(self):
        with self.assertRaises(ValueError):
            ContentTypeGatingConfig.enabled_for_enrollment(None, None, None)
        with self.assertRaises(ValueError):
            ContentTypeGatingConfig.enabled_for_enrollment(Mock(name='enrollment'), Mock(name='user'), None)
        with self.assertRaises(ValueError):
            ContentTypeGatingConfig.enabled_for_enrollment(Mock(name='enrollment'), None, Mock(name='course_key'))

    @override_waffle_flag(CONTENT_TYPE_GATING_FLAG, True)
    def test_enabled_for_enrollment_flag_override(self):
        self.assertTrue(ContentTypeGatingConfig.enabled_for_enrollment(None, None, None))
        self.assertTrue(ContentTypeGatingConfig.enabled_for_enrollment(Mock(name='enrollment'), Mock(name='user'), None))
        self.assertTrue(ContentTypeGatingConfig.enabled_for_enrollment(Mock(name='enrollment'), None, Mock(name='course_key')))

    @ddt.data(True, False)
    def test_enabled_for_course(
        self,
        before_enabled,
    ):
        config = ContentTypeGatingConfig.objects.create(
            enabled=True,
            course=self.course_overview,
            enabled_as_of=date(2018, 1, 1),
        )

        if before_enabled:
            today = config.enabled_as_of - timedelta(days=1)
        else:
            today = config.enabled_as_of + timedelta(days=1)

        course_key = self.course_overview.id

        self.assertEqual(
            not before_enabled,
            ContentTypeGatingConfig.enabled_for_course(
                course_key=course_key,
                today=today,
            )
        )

    @ddt.data(
        # Generate all combinations of setting each configuration level to True/False/None
        *itertools.product(*[(True, False, None)]*4)
    )
    @ddt.unpack
    def test_config_overrides(self, global_setting, site_setting, org_setting, course_setting):
        # Set up disctractor objects
        non_test_course_enabled = CourseOverviewFactory.create(org='non-test-org-enabled')
        non_test_course_disabled = CourseOverviewFactory.create(org='non-test-org-disabled')
        non_test_site_cfg_enabled = SiteConfigurationFactory.create(values={'course_org_filter': non_test_course_enabled.org})
        non_test_site_cfg_disabled = SiteConfigurationFactory.create(values={'course_org_filter': non_test_course_disabled.org})

        ContentTypeGatingConfig.objects.create(course=non_test_course_enabled, enabled=True, enabled_as_of=date(2018, 1, 1))
        ContentTypeGatingConfig.objects.create(course=non_test_course_disabled, enabled=False)
        ContentTypeGatingConfig.objects.create(org=non_test_course_enabled.org, enabled=True, enabled_as_of=date(2018, 1, 1))
        ContentTypeGatingConfig.objects.create(org=non_test_course_disabled.org, enabled=False)
        ContentTypeGatingConfig.objects.create(site=non_test_site_cfg_enabled.site, enabled=True, enabled_as_of=date(2018, 1, 1))
        ContentTypeGatingConfig.objects.create(site=non_test_site_cfg_disabled.site, enabled=False)

        # Set up test objects
        test_course = CourseOverviewFactory.create(org='test-org')
        test_site_cfg = SiteConfigurationFactory.create(values={'course_org_filter': test_course.org})

        ContentTypeGatingConfig.objects.create(enabled=global_setting, enabled_as_of=date(2018, 1, 1))
        ContentTypeGatingConfig.objects.create(course=test_course, enabled=course_setting, enabled_as_of=date(2018, 1, 1))
        ContentTypeGatingConfig.objects.create(org=test_course.org, enabled=org_setting, enabled_as_of=date(2018, 1, 1))
        ContentTypeGatingConfig.objects.create(site=test_site_cfg.site, enabled=site_setting, enabled_as_of=date(2018, 1, 1))

        all_settings = [global_setting, site_setting, org_setting, course_setting]
        expected_global_setting = self._resolve_settings([global_setting])
        expected_site_setting = self._resolve_settings([global_setting, site_setting])
        expected_org_setting = self._resolve_settings([global_setting, site_setting, org_setting])
        expected_course_setting = self._resolve_settings([global_setting, site_setting, org_setting, course_setting])

        self.assertEqual(expected_global_setting, ContentTypeGatingConfig.current().enabled)
        self.assertEqual(expected_site_setting, ContentTypeGatingConfig.current(site=test_site_cfg.site).enabled)
        self.assertEqual(expected_org_setting, ContentTypeGatingConfig.current(org=test_course.org).enabled)
        self.assertEqual(expected_course_setting, ContentTypeGatingConfig.current(course_key=test_course.id).enabled)

    def _resolve_settings(self, settings):
        if all(setting is None for setting in settings):
            return None

        return [
            setting
            for setting
            in settings
            if setting is not None
        ][-1]
