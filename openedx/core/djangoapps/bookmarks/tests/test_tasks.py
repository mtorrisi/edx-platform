"""
Tests for tasks.
"""
import ddt

from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from student.tests.factories import AdminFactory

from ..models import XBlockCache
from ..tasks import _calculate_course_xblocks_data, _update_xblocks_cache
from .test_models import BookmarksTestsBase


@ddt.ddt
class XBlockCacheTaskTests(BookmarksTestsBase):
    """
    Test the XBlockCache model.
    """
    def setUp(self):
        super(XBlockCacheTaskTests, self).setUp()

        self.course_expected_cache_data = {
            self.course.location: [
                [],
            ], self.chapter_1.location: [
                [
                    self.course.location,
                ],
            ], self.chapter_2.location: [
                [
                    self.course.location,
                ],
            ], self.sequential_1.location: [
                [
                    self.course.location,
                    self.chapter_1.location,
                ],
            ], self.sequential_2.location: [
                [
                    self.course.location,
                    self.chapter_1.location,
                ],
            ], self.vertical_1.location: [
                [
                    self.course.location,
                    self.chapter_1.location,
                    self.sequential_1.location,
                ],
            ], self.vertical_2.location: [
                [
                    self.course.location,
                    self.chapter_1.location,
                    self.sequential_2.location,
                ],
            ], self.vertical_3.location: [
                [
                    self.course.location,
                    self.chapter_1.location,
                    self.sequential_2.location,
                ],
            ],
        }

        self.other_course_expected_cache_data = {
            self.other_course.location: [
                [],
            ], self.other_chapter_1.location: [
                [
                    self.other_course.location,
                ],
            ], self.other_sequential_1.location: [
                [
                    self.other_course.location,
                    self.other_chapter_1.location,
                ],
            ], self.other_sequential_2.location: [
                [
                    self.other_course.location,
                    self.other_chapter_1.location,
                ],
            ], self.other_vertical_1.location: [
                [
                    self.other_course.location,
                    self.other_chapter_1.location,
                    self.other_sequential_1.location,
                ],
                [
                    self.other_course.location,
                    self.other_chapter_1.location,
                    self.other_sequential_2.location,
                ]
            ], self.other_vertical_2.location: [
                [
                    self.other_course.location,
                    self.other_chapter_1.location,
                    self.other_sequential_1.location,
                ],
            ],
        }

    @ddt.data(
        ('course',),
        ('other_course',)
    )
    @ddt.unpack
    def test_calculate_course_xblocks_data(self, course_attr):
        """
        Test that the xblocks data is calculated correctly.
        """
        course = getattr(self, course_attr)
        blocks_data = _calculate_course_xblocks_data(course.id)

        expected_cache_data = getattr(self, course_attr + '_expected_cache_data')
        for usage_key, __ in expected_cache_data.items():
            for path_index, path in enumerate(blocks_data[unicode(usage_key)]['paths']):
                for path_item_index, path_item in enumerate(path):
                    self.assertEqual(
                        path_item['usage_key'], expected_cache_data[usage_key][path_index][path_item_index]
                    )

    @ddt.data(
        ('course',),
        ('other_course',)
    )
    @ddt.unpack
    def test_update_xblocks_cache(self, course_attr):
        """
        Test that the xblocks data is persisted correctly.
        """
        course = getattr(self, course_attr)
        XBlockCache.objects.filter(course_key=course.id).delete()
        _update_xblocks_cache(course.id)

        expected_cache_data = getattr(self, course_attr + '_expected_cache_data')
        for usage_key, __ in expected_cache_data.items():
            xblock_cache = XBlockCache.objects.get(usage_key=usage_key)
            for path_index, path in enumerate(xblock_cache.paths):
                for path_item_index, path_item in enumerate(path):
                    self.assertEqual(
                        path_item.usage_key, expected_cache_data[usage_key][path_index][path_item_index + 1]
                    )
