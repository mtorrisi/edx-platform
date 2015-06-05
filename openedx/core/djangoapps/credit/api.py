""" Contains the APIs for course credit requirements """
import logging
import uuid
import datetime
import pytz
from django.db import transaction

from student.models import User

from .exceptions import (
    InvalidCreditRequirements,
    InvalidCreditCourse,
    UserIsNotEligible,
    RequestAlreadyCompleted,
    CreditRequestNotFound,
    InvalidCreditStatus,
)
from .models import (
    CreditCourse,
    CreditRequirement,
    CreditRequirementStatus,
    CreditRequest,
    CreditRequestStatus,
    CreditEligibility,
)


log = logging.getLogger(__name__)


def set_credit_requirements(course_key, requirements):
    """
    Add requirements to given course.

    Args:
        course_key(CourseKey): The identifier for course
        requirements(list): List of requirements to be added

    Example:
        >>> set_credit_requirements(
                "course-v1-edX-DemoX-1T2015",
                [
                    {
                        "namespace": "reverification",
                        "name": "i4x://edX/DemoX/edx-reverification-block/assessment_uuid",
                        "display_name": "Assessment 1",
                        "criteria": {},
                    },
                    {
                        "namespace": "proctored_exam",
                        "name": "i4x://edX/DemoX/proctoring-block/final_uuid",
                        "display_name": "Final Exam",
                        "criteria": {},
                    },
                    {
                        "namespace": "grade",
                        "name": "grade",
                        "display_name": "Grade",
                        "criteria": {"min_grade": 0.8},
                    },
                ])

    Raises:
        InvalidCreditRequirements

    Returns:
        None
    """

    invalid_requirements = _validate_requirements(requirements)
    if invalid_requirements:
        invalid_requirements = ", ".join(invalid_requirements)
        raise InvalidCreditRequirements(invalid_requirements)

    try:
        credit_course = CreditCourse.get_credit_course(course_key=course_key)
    except CreditCourse.DoesNotExist:
        raise InvalidCreditCourse()

    old_requirements = CreditRequirement.get_course_requirements(course_key=course_key)
    requirements_to_disable = _get_requirements_to_disable(old_requirements, requirements)
    if requirements_to_disable:
        CreditRequirement.disable_credit_requirements(requirements_to_disable)

    for requirement in requirements:
        CreditRequirement.add_or_update_course_requirement(credit_course, requirement)


def get_credit_requirements(course_key, namespace=None):
    """
    Get credit eligibility requirements of a given course and namespace.

    Args:
        course_key(CourseKey): The identifier for course
        namespace(str): Namespace of requirements

    Example:
        >>> get_credit_requirements("course-v1-edX-DemoX-1T2015")
                {
                    requirements =
                    [
                        {
                            "namespace": "reverification",
                            "name": "i4x://edX/DemoX/edx-reverification-block/assessment_uuid",
                            "display_name": "Assessment 1",
                            "criteria": {},
                        },
                        {
                            "namespace": "proctored_exam",
                            "name": "i4x://edX/DemoX/proctoring-block/final_uuid",
                            "display_name": "Final Exam",
                            "criteria": {},
                        },
                        {
                            "namespace": "grade",
                            "name": "grade",
                            "display_name": "Grade",
                            "criteria": {"min_grade": 0.8},
                        },
                    ]
                }

    Returns:
        Dict of requirements in the given namespace
    """

    requirements = CreditRequirement.get_course_requirements(course_key, namespace)
    return [
        {
            "namespace": requirement.namespace,
            "name": requirement.name,
            "display_name": requirement.display_name,
            "criteria": requirement.criteria
        }
        for requirement in requirements
    ]


# Wrap in a transaction to ensure that the request and initial pending status are consistent.
@transaction.commit_on_success
def create_credit_request(course_key, provider_id, username):
    """
    Initiate a request for credit from a credit provider.

    This will return the parameters that the user's browser will need to POST
    to the credit provider.  It does NOT calculate the signature

    Only users who are eligible for credit (have satisfied all credit requirements) are allowed to make requests.

    A database record will be created to track the request with a 32-character UUID.
    The returned dictionary can be used by the user's browser to send a POST request to the credit provider.

    If a pending request already exists, this function should return a request description with the same UUID.
    (Other parameters, such as the user's full name may be different than the original request).

    If a completed request (either accepted or rejected) already exists, this function will
    raise an exception.  Users are not allowed to make additional requests once a request
    has been completed.

    Arguments:
        course_key (CourseKey): The identifier for the course.
        provider_id (str): The identifier of the credit provider.
        user (User): The user initiating the request.

    Returns: dict

    Raises:
        UserIsNotEligible: The user has not satisfied eligibility requirements for credit.
        RequestAlreadyCompleted: The user has already submitted a request and received a response
            from the credit provider.

    Example Usage:
        >>> create_credit_request(course.id, "hogwarts", "ron")
        {
            "uuid": "557168d0f7664fe59097106c67c3f847",
            "timestamp": "2015-05-04T20:57:57.987119+00:00",
            "course_org": "HogwartsX",
            "course_num": "Potions101",
            "course_run": "1T2015",
            "final_grade": 0.95,
            "user_username": "ron",
            "user_email": "ron@example.com",
            "user_full_name": "Ron Weasley",
            "user_mailing_address": "",
            "user_country": "US",
        }

    """
    try:
        user_eligibility = CreditEligibility.objects.select_related('course', 'provider').get(
            username=username,
            course__course_key=course_key,
            provider__provider_id=provider_id
        )
    except CreditEligibility.DoesNotExist:
        raise UserIsNotEligible
    else:
        credit_course = user_eligibility.course
        credit_provider = user_eligibility.provider

    # Initiate a new request if one has not already been created
    credit_request, created = CreditRequest.objects.get_or_create(
        course=credit_course,
        provider=credit_provider,
        username=username,
    )

    # Check whether we've already gotten a response for a request,
    # If so, we're not allowed to issue any further requests.
    # Skip checking the status if we know that we just created this record.
    if not created and credit_request.current_status() != "pending":
        raise RequestAlreadyCompleted

    if created:
        credit_request.uuid = uuid.uuid4().hex

    # Retrieve user account and profile info
    user = User.objects.select_related('profile').get(username=username)

    # Retrieve the final grade from the eligibility table
    try:
        final_grade = CreditRequirementStatus.objects.filter(
            username=username,
            requirement__namespace="grade",
            requirement__name="grade",
            status="satisfied"
        ).latest().reason["final_grade"]
    except (CreditRequirementStatus.DoesNotExist, TypeError, KeyError):
        log.exception(
            "Could not retrieve final grade from the credit eligibility table "
            "for user %s in course %s.",
            user.id, course_key
        )
        raise UserIsNotEligible

    parameters = {
        "uuid": credit_request.uuid,
        "timestamp": datetime.datetime.now(pytz.UTC).isoformat(),
        "course_org": course_key.org,
        "course_num": course_key.course,
        "course_run": course_key.run,
        "final_grade": final_grade,
        "user_username": user.username,
        "user_email": user.email,
        "user_full_name": user.profile.name,
        "user_mailing_address": (
            user.profile.mailing_address
            if user.profile.mailing_address is not None
            else ""
        ),
        "user_country": (
            user.profile.country.code
            if user.profile.country.code is not None
            else ""
        ),
    }

    credit_request.parameters = parameters
    credit_request.save()

    # Save the initial status as pending
    CreditRequestStatus.objects.create(
        request=credit_request,
        status="pending"
    )

    return parameters


def update_credit_request_status(request_uuid, status):
    """
    Update the status of a credit request.

    Approve or reject a request for a student to receive credit in a course
    from a particular credit provider.

    This function does NOT check that the status update is authorized.
    The caller needs to handle authentication and authorization (checking the signature
    of the message received from the credit provider)

    The function is idempotent; if the request has already been updated to the status,
    the function does nothing.

    Arguments:
        request_uuid (str): The unique identifier for the credit request.
        status (str): Either "approved" or "rejected"

    Returns: None

    Raises:
        CreditRequestNotFound: The request does not exist.
        InvalidCreditStatus: The status is not either "approved" or "rejected".

    """
    if status not in ["approved", "rejected"]:
        raise InvalidCreditStatus

    try:
        request = CreditRequest.objects.get(uuid=request_uuid)
    except CreditRequest.DoesNotExist:
        raise CreditRequestNotFound

    # For auditing purposes, we don't modify credit request status
    # records once they're created.  Instead, we use the most recently
    # created status record as the current status.
    CreditRequestStatus.objects.create(
        request=request,
        status=status,
    )


def get_credit_requests_for_user(username):
    """
    Retrieve the status of a credit request.

    Returns either "pending", "accepted", or "rejected"

    Arguments:
        username (unicode): The username of the user who initiated the requests.

    Returns: list

    Example Usage:
    >>> get_credit_request_status_for_user("bob")
    [
        {
            "uuid": "557168d0f7664fe59097106c67c3f847",
            "timestamp": "2015-05-04T20:57:57.987119+00:00",
            "course_key": "course-v1:HogwartsX+Potions101+1T2015",
            "provider": {
                "id": "HogwartsX",
                "display_name": "Hogwarts School of Witchcraft and Wizardry",
            },
            "status": "pending"  # or "approved" or "rejected"
        }
    ]

    """
    return CreditRequest.credit_requests_for_user(username)


def _get_requirements_to_disable(old_requirements, new_requirements):
    """
    Get the ids of 'CreditRequirement' entries to be disabled that are
    deleted from the courseware.

    Args:
        old_requirements(QuerySet): QuerySet of CreditRequirement
        new_requirements(list): List of requirements being added

    Returns:
        List of ids of CreditRequirement that are not in new_requirements
    """
    requirements_to_disable = []
    for old_req in old_requirements:
        found_flag = False
        for req in new_requirements:
            # check if an already added requirement is modified
            if req["namespace"] == old_req.namespace and req["name"] == old_req.name:
                found_flag = True
                break
        if not found_flag:
            requirements_to_disable.append(old_req.id)
    return requirements_to_disable


def _validate_requirements(requirements):
    """
    Validate the requirements.

    Args:
        requirements(list): List of requirements

    Returns:
        List of strings of invalid requirements
    """
    invalid_requirements = []
    for requirement in requirements:
        invalid_params = []
        if not requirement.get("namespace"):
            invalid_params.append("namespace")
        if not requirement.get("name"):
            invalid_params.append("name")
        if not requirement.get("display_name"):
            invalid_params.append("display_name")
        if "criteria" not in requirement:
            invalid_params.append("criteria")

        if invalid_params:
            invalid_requirements.append(
                u"{requirement} has missing/invalid parameters: {params}".format(
                    requirement=requirement,
                    params=invalid_params,
                )
            )
    return invalid_requirements
