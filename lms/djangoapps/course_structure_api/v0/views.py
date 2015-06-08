""" API implementation for course-oriented interactions. """

from collections import namedtuple
import json
import logging

from django.conf import settings
from django.http import Http404
from rest_framework.authentication import OAuth2Authentication, SessionAuthentication
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed, ParseError
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework.reverse import reverse
from xmodule.modulestore.django import modulestore
from opaque_keys.edx.keys import CourseKey

from course_structure_api.v0 import api, serializers
from course_structure_api.v0.errors import CourseNotFoundError, CourseStructureNotAvailableError
from courseware import courses
from courseware.access import has_access
from courseware.model_data import FieldDataCache
from courseware.module_render import get_module_for_descriptor
from openedx.core.lib.api.view_utils import view_course_access, view_auth_classes
from openedx.core.lib.api.permissions import IsAuthenticatedOrDebug
from openedx.core.lib.api.serializers import PaginationSerializer
from student.roles import CourseInstructorRole, CourseStaffRole
from util.module_utils import get_dynamic_descriptor_children


log = logging.getLogger(__name__)


class CourseViewMixin(object):
    """
    Mixin for views dealing with course content. Also handles authorization and authentication.
    """
    lookup_field = 'course_id'
    authentication_classes = (OAuth2Authentication, SessionAuthentication,)
    permission_classes = (IsAuthenticatedOrDebug,)

    def get_course_or_404(self):
        """
        Retrieves the specified course, or raises an Http404 error if it does not exist.
        Also checks to ensure the user has permissions to view the course
        """
        try:
            course_id = self.kwargs.get('course_id')
            course_key = CourseKey.from_string(course_id)
            course = courses.get_course(course_key)
            self.check_course_permissions(self.request.user, course_key)

            return course
        except ValueError:
            raise Http404

    @staticmethod
    def course_check(func):
        """Decorator responsible for catching errors finding and returning a 404 if the user does not have access
        to the API function.

        :param func: function to be wrapped
        :returns: the wrapped function
        """
        def func_wrapper(self, *args, **kwargs):
            """Wrapper function for this decorator.

            :param *args: the arguments passed into the function
            :param **kwargs: the keyword arguments passed into the function
            :returns: the result of the wrapped function
            """
            try:
                course_id = self.kwargs.get('course_id')
                self.course_key = CourseKey.from_string(course_id)
                self.check_course_permissions(self.request.user, self.course_key)
                return func(self, *args, **kwargs)
            except CourseNotFoundError:
                raise Http404

        return func_wrapper

    def user_can_access_course(self, user, course):
        """
        Determines if the user is staff or an instructor for the course.
        Always returns True if DEBUG mode is enabled.
        """
        return (settings.DEBUG
                or has_access(user, CourseStaffRole.ROLE, course)
                or has_access(user, CourseInstructorRole.ROLE, course))

    def check_course_permissions(self, user, course):
        """
        Checks if the request user can access the course.
        Raises PermissionDenied if the user does not have course access.
        """
        if not self.user_can_access_course(user, course):
            raise PermissionDenied

    def perform_authentication(self, request):
        """
        Ensures that the user is authenticated (e.g. not an AnonymousUser), unless DEBUG mode is enabled.
        """
        super(CourseViewMixin, self).perform_authentication(request)
        if request.user.is_anonymous() and not settings.DEBUG:
            raise AuthenticationFailed


class CourseList(CourseViewMixin, ListAPIView):
    """
    **Use Case**

        Get a paginated list of courses in the edX Platform.

        The list can be filtered by course_id.

        Each page in the list can contain up to 10 courses.

    **Example Requests**

          GET /api/course_structure/v0/courses/

          GET /api/course_structure/v0/courses/?course_id={course_id1},{course_id2}

    **Response Values**

        * count: The number of courses in the edX platform.

        * next: The URI to the next page of courses.

        * previous: The URI to the previous page of courses.

        * num_pages: The number of pages listing courses.

        * results:  A list of courses returned. Each collection in the list
          contains these fields.

            * id: The unique identifier for the course.

            * name: The name of the course.

            * category: The type of content. In this case, the value is always
              "course".

            * org: The organization specified for the course.

            * run: The run of the course.

            * course: The course number.

            * uri: The URI to use to get details of the course.

            * image_url: The URI for the course's main image.

            * start: The course start date.

            * end: The course end date. If course end date is not specified, the
              value is null.
    """
    paginate_by = 10
    paginate_by_param = 'page_size'
    pagination_serializer_class = PaginationSerializer
    serializer_class = serializers.CourseSerializer

    def get_queryset(self):
        course_ids = self.request.QUERY_PARAMS.get('course_id', None)

        results = []
        if course_ids:
            course_ids = course_ids.split(',')
            for course_id in course_ids:
                course_key = CourseKey.from_string(course_id)
                course_descriptor = courses.get_course(course_key)
                results.append(course_descriptor)
        else:
            results = modulestore().get_courses()

        # Ensure only course descriptors are returned.
        results = (course for course in results if course.scope_ids.block_type == 'course')

        # Ensure only courses accessible by the user are returned.
        results = (course for course in results if self.user_can_access_course(self.request.user, course))

        # Sort the results in a predictable manner.
        return sorted(results, key=lambda course: unicode(course.id))


class CourseDetail(CourseViewMixin, RetrieveAPIView):
    """
    **Use Case**

        Get details for a specific course.

    **Example Request**:

        GET /api/course_structure/v0/courses/{course_id}/

    **Response Values**

        * id: The unique identifier for the course.

        * name: The name of the course.

        * category: The type of content.

        * org: The organization that is offering the course.

        * run: The run of the course.

        * course: The course number.

        * uri: The URI to use to get details about the course.

        * image_url: The URI for the course's main image.

        * start: The course start date.

        * end: The course end date. If course end date is not specified, the
          value is null.
    """
    serializer_class = serializers.CourseSerializer

    def get_object(self, queryset=None):
        return self.get_course_or_404()


class CourseStructure(CourseViewMixin, RetrieveAPIView):
    """
    **Use Case**

        Get the course structure. This endpoint returns all blocks in the
        course.

    **Example requests**:

        GET /api/course_structure/v0/course_structures/{course_id}/

    **Response Values**

        * root: The ID of the root node of the course structure.

        * blocks: A dictionary that maps block IDs to a collection of
          information about each block. Each block contains the following
          fields.

          * id: The ID of the block.

          * type: The type of block. Possible values include sequential,
            vertical, html, problem, video, and discussion. The type can also be
            the name of a custom type of block used for the course.

          * display_name: The display name configured for the block.

          * graded: Whether or not the sequential or problem is graded. The
            value is true or false.

          * format: The assignment type.

          * children: If the block has child blocks, a list of IDs of the child
            blocks.
    """

    @CourseViewMixin.course_check
    def get(self, request, **kwargs):
        try:
            return Response(api.course_structure(self.course_key))
        except CourseStructureNotAvailableError:
            # If we don't have data stored, we will try to regenerate it, so
            # return a 503 and as them to retry in 2 minutes.
            return Response(status=503, headers={'Retry-After': '120'})


class CourseGradingPolicy(CourseViewMixin, ListAPIView):
    """
    **Use Case**

        Get the course grading policy.

    **Example requests**:

        GET /api/course_structure/v0/grading_policies/{course_id}/

    **Response Values**

        * assignment_type: The type of the assignment, as configured by course
          staff. For example, course staff might make the assignment types Homework,
          Quiz, and Exam.

        * count: The number of assignments of the type.

        * dropped: Number of assignments of the type that are dropped.

        * weight: The weight, or effect, of the assignment type on the learner's
          final grade.
    """

    allow_empty = False

    @CourseViewMixin.course_check
    def get(self, request, **kwargs):
        return Response(api.course_grading_policy(self.course_key))


@view_auth_classes()
class CourseBlocksAndNavigation(ListAPIView):
    """
    **Use Case**

        The following endpoints return the content of the course according to the requesting user's access level.

        * Blocks - Get the course's blocks.

        * Navigation - Get the course's navigation information per the navigation depth requested.

        * Blocks+Navigation - Get both the course's blocks and the course's navigation information.

    **Example requests**:

        GET api/course_structure/v0/courses/{course_id}/blocks/
        GET api/course_structure/v0/courses/{course_id}/navigation/
        GET api/course_structure/v0/courses/{course_id}/blocks+navigation/
           &block_count=video
           &block_json={"video":{"profiles":["mobile_low"]}}
           &fields=graded,format,responsive_ui

    **Parameters**:

        * block_json: (dict) Indicates for which block types to return student_view_json data.  The key is the block
          type and the value is the "context" that is passed to the block's student_view_json method.

          Example: block_json={"video":{"profiles":["mobile_high","mobile_low"]}}

        * block_count: (list) Indicates for which block types to return the aggregate count of the blocks.

          Example: block_count="video,problem"

        * fields: (list) Indicates which additional fields to return for each block.
          Default is "children,graded,format,responsive_ui"

          Example: fields=graded,format,responsive_ui

        * navigation_depth (integer) Indicates how far deep to traverse into the course hierarchy before bundling
          all the descendants.
          Default is 3.

          Example: navigation_depth=3

    **Response Values**

        * root: The ID of the root node of the course blocks.

        * blocks: A dictionary that maps block usage IDs to a collection of information about each block.
          Each block contains the following fields.

          * id: (string) The usage ID of the block.

          * type: (string) The type of block. Possible values include course, chapter, sequential, vertical, html,
            problem, video, and discussion. The type can also be the name of a custom type of block used for the course.

          * display_name: (string) The display name of the block.

          * children: (list) If the block has child blocks, a list of IDs of the child blocks.
            Returned only if the "children" input parameter is True.

          * block_count: (dict) For each block type specified in the block_count parameter to the endpoint, the
            aggregate number of blocks of that type for this block and all of its descendants.
            Returned only if the "block_count" input parameter contains this block's type.

          * block_json: (dict) The JSON data for this block.
            Returned only if the "block_json" input parameter contains this block's type.

          * block_url: (string) The URL to retrieve the HTML rendering of this block.  The HTML could include
            CSS and Javascript code.  This URL can be used as a fallback if the custom block_json for this
            block type is not requested and not supported.

          * web_url: (string) The URL to the website location of this block.  This URL can be used as a further
            fallback if the block_url and the block_json is not supported.

          * graded (boolean) Whether or not the block or any of its descendants is graded.
            Returned only if "graded" is included in the "fields" parameter.

          * format: (string) The assignment type of the block.
            Possible values can be "Homework", "Lab", "Midterm Exam", and "Final Exam".
            Returned only if "format" is included in the "fields" parameter.

          * responsive_ui: (boolean) Whether or not the block's rendering obtained via block_url is responsive.
            Returned only if "responsive_ui" is included in the "fields" parameter.

        * navigation: A dictionary that maps block IDs to a collection of navigation information about each block.
          Each block contains the following fields.

          * descendants: (list) A list of IDs of the children of the block if the block's depth in the
            course hierarchy is less than the navigation_depth.  Otherwise, a list of IDs of the aggregate descendants
            of the block.

        * blocks_navigation: A dictionary that combines both the blocks and navigation data.

    """
    DEFAULT_FIELDS = "children,graded,format,responsive_ui"
    BlockApiField = namedtuple('BlockApiField', 'block_field_name api_field_default')
    FIELD_MAP = {
        'graded': BlockApiField(block_field_name='graded', api_field_default=False),
        'format': BlockApiField(block_field_name='format', api_field_default=None),
        'responsive_ui': BlockApiField(block_field_name='has_responsive_ui', api_field_default=False),
    }

    @view_course_access(depth=None)
    def list(self, request, course, return_blocks=True, return_nav=True, *args, **kwargs):

        # check what fields are requested
        try:
            # fields
            fields_requested = set(request.GET.get('fields', self.DEFAULT_FIELDS).split(","))

            # children
            children_requested = 'children' in fields_requested
            fields_requested.discard('children')

            # block_count
            block_count_requested = request.GET.get('block_count', "")
            block_count_requested = block_count_requested.split(",") if block_count_requested else []

            # navigation_depth
            navigation_depth_requested = int(request.GET.get('navigation_depth', '3'))

            # block_json
            block_json_requested = json.loads(request.GET.get('block_json', "{}"))
            if block_json_requested and not isinstance(block_json_requested, dict):
                raise ParseError
        except:
            raise ParseError

        # prepare the response
        response = {}
        blocks = {}
        navigation = {}
        if return_blocks and return_nav:
            navigation = blocks
            response["blocks+navigation"] = blocks
        elif return_blocks:
            response["blocks"] = blocks
        elif return_nav:
            response["navigation"] = navigation

        def recurse_blocks_nav(block, block_depth, descendants_of_parent):
            """
            A depth-first recursive function that supports calculation of both the list of blocks in the course
            and the navigation information upto block_depth of the course.

            Arguments:
              block: the block for which the recursion is being computed.

              block_depth: the block's depth in the course hierarchy.  It is compared with the
                navigation_depth_requested parameter to determine whether the descendants of the block should
                be appended to the descendants of the block (if block_depth <= navigation_depth_requested) or
                to the given descendants of the block's parents (if block_depth > navigation_depth_requested).

              descendants_of_parent: the list of descendants for this block's parent.
            """
            block_type = block.category
            block = create_module(block, course.id, request)

            # verify the user has access to this block
            if not has_access(self.request.user, 'load', block, course_key=course.id):
                return

            # set basic field values for the block
            block_value = {
                "id": unicode(block.location),
                "type": block_type,
                "display_name": block.display_name,
                "web_url": reverse(
                    "jump_to",
                    kwargs={"course_id": unicode(course.id), "location": unicode(block.location)},
                    request=request,
                ),
                "block_url": reverse(
                    "courseware.views.render_xblock",
                    kwargs={"usage_key_string": unicode(block.location)},
                    request=request,
                ),
            }
            blocks[unicode(block.location)] = block_value

            # descendants
            # descendants_of_parent contains the descendants of this block's parents and should be
            #   updated with this block if this block is visible in the navigation (i.e., hide_from_toc is False).
            # descendants_of_self is the list of descendants that is passed to this block's children.
            #   It should be either:
            #      [] - if this block's hide_from_toc is True.
            #      descendants_of_parent - if this block's depth is greater than the requested navigation_depth.
            #      navigation[block.location]["descendants"] - if this block's depth is within the requested navigation
            #        depth and so its descendants can be added to this block's descendants value.

            descendants_of_self = []
            # Blocks with the 'hide_from_toc' setting are accessible, just not navigatable from the table-of-contents.
            # If the 'hide_from_toc' setting is set on the block, do not add this block to the parent's descendants
            # list and let the block's descendants add themselves to a dangling (unreferenced) descendants list.
            if not block.hide_from_toc:
                # add this block to the parent's descendants
                descendants_of_parent.append(unicode(block.location))

                # if this block's depth in the hierarchy is greater than the requested navigation depth,
                # have the block's descendants add themselves to the parent's descendants.
                if block_depth > navigation_depth_requested:
                    descendants_of_self = descendants_of_parent

                # otherwise, have the block's descendants add themselves to this block's descendants by
                # referencing/attaching descendants_of_self from this block's navigation value.
                else:
                    navigation.setdefault(unicode(block.location), {})["descendants"] = descendants_of_self

            # children
            children = []
            if block.has_children:
                # Recursively call the function for each of the children, while supporting dynamic children.
                children = get_dynamic_descriptor_children(block)
                for child in children:
                    recurse_blocks_nav(child, block_depth + 1, descendants_of_self)
                if children_requested:
                    block_value["children"] = [unicode(child.location) for child in children]

            # block count
            # For all the block types that are requested to be counted, include the count of
            # that block type as aggregated from the block's descendants.
            for b_type in block_count_requested:
                block_value.setdefault("block_count", {})[b_type] = (
                    sum(
                        blocks.get(unicode(child.location), {}).get("block_count", {}).get(b_type, 0)
                        for child in children
                    ) +
                    (1 if b_type == block_type else 0)
                )

            # block JSON data
            # If the data for this block's type is requested, and the block supports the 'student_view_json' method,
            # add the response from the 'student_view_json" method as the data for the block.
            if block_type in block_json_requested:
                if getattr(block, 'student_view_json', None):
                    block_value["block_json"] = block.student_view_json(
                        context=block_json_requested[block_type]
                    )

            # additional fields
            for field_name in fields_requested:
                if field_name in self.FIELD_MAP:
                    block_value[field_name] = getattr(
                        block,
                        self.FIELD_MAP[field_name].block_field_name,
                        self.FIELD_MAP[field_name].api_field_default,
                    )

        # start the recursion with the course at block_depth 0
        start_block = course
        response["root"] = unicode(start_block.location)
        recurse_blocks_nav(start_block, block_depth=0, descendants_of_parent=[])

        # return response
        return Response(response)


def create_module(descriptor, course_id, request):
    """
    Factory method for creating and binding a module for the given descriptor.
    """
    field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
        course_id, request.user, descriptor, depth=0,
    )
    return get_module_for_descriptor(
        request.user, request, descriptor, field_data_cache, course_id
    )
