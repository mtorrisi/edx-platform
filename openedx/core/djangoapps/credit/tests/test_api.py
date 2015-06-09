"""
Tests for credit course api.
"""

import ddt

from opaque_keys.edx.keys import CourseKey

from openedx.core.djangoapps.credit.api import (
    get_credit_requirements, set_credit_requirements, _get_requirements_to_disable, set_credit_requirement_status
)
from openedx.core.djangoapps.credit.exceptions import InvalidCreditRequirements, InvalidCreditCourse
from openedx.core.djangoapps.credit.models import CreditCourse, CreditRequirement
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


@ddt.ddt
class ApiTestCases(ModuleStoreTestCase):
    """
    Tests for credit course api.
    """

    def setUp(self, **kwargs):
        super(ApiTestCases, self).setUp()
        self.course_key = CourseKey.from_string("edX/DemoX/Demo_Course")

    @ddt.data(
        [
            {
                "namespace": "grade",
                "criteria": {
                    "min_grade": 0.8
                }
            }
        ],
        [
            {
                "name": "grade",
                "criteria": {
                    "min_grade": 0.8
                }
            }
        ],
        [
            {
                "namespace": "grade",
                "name": "grade",
                "display_name": "Grade"
            }
        ]
    )
    def test_set_credit_requirements_invalid_requirements(self, requirements):
        self.add_credit_course()
        with self.assertRaises(InvalidCreditRequirements):
            set_credit_requirements(self.course_key, requirements)

    def test_set_credit_requirements_invalid_course(self):
        """Test that 'InvalidCreditCourse' exception is raise if we try to
        set credit requirements for a non credit course.
        """
        requirements = [
            {
                "namespace": "grade",
                "name": "grade",
                "display_name": "Grade",
                "criteria": {}
            }
        ]
        with self.assertRaises(InvalidCreditCourse):
            set_credit_requirements(self.course_key, requirements)

        self.add_credit_course(enabled=False)
        with self.assertRaises(InvalidCreditCourse):
            set_credit_requirements(self.course_key, requirements)

    def test_set_get_credit_requirements(self):
        """Test that if same requirement is added multiple times
        then it is added only one time and update for next all iterations.
        """
        self.add_credit_course()
        requirements = [
            {
                "namespace": "grade",
                "name": "grade",
                "display_name": "Grade",
                "criteria": {
                    "min_grade": 0.8
                }
            },
            {
                "namespace": "grade",
                "name": "grade",
                "display_name": "Grade",
                "criteria": {
                    "min_grade": 0.9
                }
            }
        ]
        set_credit_requirements(self.course_key, requirements)
        self.assertEqual(len(get_credit_requirements(self.course_key)), 1)

        # now verify that the saved requirement has values of last requirement
        # from all same requirements
        self.assertEqual(get_credit_requirements(self.course_key)[0], requirements[1])

    def test_disable_credit_requirements(self):
        self.add_credit_course()
        requirements = [
            {
                "namespace": "grade",
                "name": "grade",
                "display_name": "Grade",
                "criteria": {
                    "min_grade": 0.8
                }
            }
        ]
        set_credit_requirements(self.course_key, requirements)
        self.assertEqual(len(get_credit_requirements(self.course_key)), 1)

        requirements = [
            {
                "namespace": "reverification",
                "name": "i4x://edX/DemoX/edx-reverification-block/assessment_uuid",
                "display_name": "Assessment 1",
                "criteria": {}
            }
        ]
        set_credit_requirements(self.course_key, requirements)
        self.assertEqual(len(get_credit_requirements(self.course_key)), 1)

        grade_req = CreditRequirement.objects.filter(namespace="grade", name="grade")
        self.assertEqual(len(grade_req), 1)
        self.assertEqual(grade_req[0].active, False)

    def test_requirements_to_disable(self):
        self.add_credit_course()
        requirements = [
            {
                "namespace": "grade",
                "name": "grade",
                "display_name": "Grade",
                "criteria": {
                    "min_grade": 0.8
                }
            }
        ]

        set_credit_requirements(self.course_key, requirements)
        old_requirements = CreditRequirement.get_course_requirements(self.course_key)
        self.assertEqual(len(old_requirements), 1)

        requirements = [
            {
                "namespace": "reverification",
                "name": "i4x://edX/DemoX/edx-reverification-block/assessment_uuid",
                "display_name": "Assessment 1",
                "criteria": {}
            }
        ]
        requirements_to_disabled = _get_requirements_to_disable(old_requirements, requirements)
        self.assertEqual(len(requirements_to_disabled), 1)
        self.assertEqual(requirements_to_disabled[0], old_requirements[0].id)

        requirements = [
            {
                "namespace": "grade",
                "name": "grade",
                "display_name": "Grade",
                "criteria": {
                    "min_grade": 0.8
                }
            },
            {
                "namespace": "reverification",
                "name": "i4x://edX/DemoX/edx-reverification-block/assessment_uuid",
                "display_name": "Assessment 1",
                "criteria": {}
            }
        ]
        requirements_to_disabled = _get_requirements_to_disable(old_requirements, requirements)
        self.assertEqual(len(requirements_to_disabled), 0)

    def test_set_credit_requirement_status(self):
        self.add_credit_course()
        requirements = [
            {
                "namespace": "grade",
                "name": "grade",
                "display_name": "Grade",
                "criteria": {
                    "min_grade": 0.8
                }
            },
            {
                "namespace": "reverification",
                "name": "i4x://edX/DemoX/edx-reverification-block/assessment_uuid",
                "display_name": "Assessment 1",
                "criteria": {}
            }
        ]

        set_credit_requirements(self.course_key, requirements)
        course_requirements = CreditRequirement.get_course_requirements(self.course_key)
        self.assertEqual(len(course_requirements), 2)

        requirement = CreditRequirement.get_course_requirement(self.course_key, "grade", "grade")
        status, created = set_credit_requirement_status("staff", requirement, 'satisfied', {})
        self.assertTrue(created)
        self.assertEqual(status.requirement.namespace, requirement.namespace)

        status, created = set_credit_requirement_status(
            "staff", requirement, 'failed', {'failure_reason': "requirements not satisfied"}
        )
        self.assertFalse(created)
        self.assertEqual(status.requirement.namespace, requirement.namespace)

    def add_credit_course(self, enabled=True):
        """
        Mark the course as a credit.
        """
        credit_course = CreditCourse(course_key=self.course_key, enabled=enabled)
        credit_course.save()
        return credit_course
