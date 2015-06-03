"""
Views for the credit Django app.

TODO: description of API contract with the credit provider.

"""
import json

from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden
)
from django.views.decorators.http import require_POST

from opaque_keys.edx.keys import CourseKey
from opaque_keys import InvalidKeyError

from util.json_request import JsonResponse
from openedx.core.djangoapps.credit import api


@require_POST
def create_credit_request(request, provider_id):
    """
    Initiate a request for credit in a course.

    This end-point will get-or-create a record in the database to track
    the request.  It will then calculate the parameters to send to
    the credit provider and digitially sign the parameters, using a secret
    key shared with the credit provider.

    The user's browser is responsible for POSTing these parameters
    directly to the credit provider.

    **Example Usage:**

        POST /api/credit/v1/provider/hogwarts/request/
        {
            "username": "ron",
            "course_key": "edX/DemoX/Demo_Course"
        }

        Response: 200 OK
        Content-Type: application/json
        {
            "url": "http://example.com/request-credit",
            "method": "POST",
            "parameters": {
                request_uuid: "557168d0f7664fe59097106c67c3f847"
                timestamp: "2015-05-04T20:57:57.987119+00:00"
                course_org: "ASUx"
                course_num: "DemoX"
                course_run: "1T2015"
                final_grade: 0.95,
                user_username: "john",
                user_email: "john@example.com"
                user_full_name: "John Smith"
                user_mailing_address: "",
                user_country: "US",
                signature: "cRCNjkE4IzY+erIjRwOQCpRILgOvXx4q2qvx141BCqI="
            }
        }

    **Parameters:**

        * username (unicode): The username of the user requesting credit.

        * course_key (unicode): The identifier for the course for which the user
            is requesting credit.

    **Responses:**

        * 200 OK: The request was created successfully.  Returned content
            is a JSON-encoded dictionary describing what the client should
            send to the credit provider.

        * 400 Bad Request:
            - The provided course key did not correspond to a valid credit course.
            - The user already has a completed credit request for this course and provider.

        * 403 Not Authorized:
            - The username does not match the name of the logged in user.
            - The user is not eligible for credit in the course.

        * 404 Not Found:
            - The provider does not exist.

    """
    # Validate parameters
    try:
        parameters = json.loads(request.body)
    except (TypeError, ValueError):
        return HttpResponseBadRequest("TODO")

    if not isinstance(parameters, dict):
        return HttpResponseBadRequest("TODO")

    if "username" not in parameters:
        return HttpResponseBadRequest("TODO")
    elif "course_key" not in parameters:
        return HttpResponseBadRequest("TODO")

    try:
        username = parameters["username"]
        course_key = CourseKey.from_string(parameters["course_key"])
    except InvalidKeyError:
        return HttpResponseBadRequest("TODO")

    # Check user authorization
    if not (request.user and request.user.username == username):
        return HttpResponseForbidden("TODO")

    # Initiate the request
    try:
        credit_request = api.create_credit_request(course_key, provider_id, username)
    except:
        # TODO
        raise
    else:
        return JsonResponse(credit_request)


@require_POST
def credit_provider_callback(request, provider_id):
    """
    Callback end-point used by credit providers to approve or reject
    a request for credit.

    **Example Usage:**

        POST /api/credit/v1/provider/{provider-id}/callback
        {
            "request_uuid": "557168d0f7664fe59097106c67c3f847",
            "status": "approved",
            "timestamp": "2015-05-04T20:57:57.987119+00:00",
            "signature": "cRCNjkE4IzY+erIjRwOQCpRILgOvXx4q2qvx141BCqI="
        }

        Response: 200 OK

    **Parameters:**

        * request_uuid (string): The UUID of the request.

        * status (string): Either "approved" or "rejected".

        * timestamp (string): The datetime at which the POST request was made, in ISO 8601 format.
            This will always include time-zone information.

        * signature (string): A digital signature of the request parameters,
            created using a secret key shared with the credit provider.

    **Responses:**

        * 200 OK: The user's status was updated successfully.

        * 400 Bad request: The provided parameters were not valid.
            Response content will be a JSON-encoded string describing the error.

        * 403 Forbidden: Signature was invalid or timestamp was too far in the past.

        * 404 Not Found: Could not find a request with the specified UUID associated with this provider.

    """
    # Validate parameters
    try:
        parameters = json.loads(request.body)
    except (TypeError, ValueError):
        return HttpResponseBadRequest("TODO")

    if not isinstance(parameters, dict):
        return HttpResponseBadRequest("TODO")

    if "request_uuid" not in parameters:
        return HttpResponseBadRequest("TODO")
    elif "status" not in parameters:
        return HttpResponseBadRequest("TODO")
    elif "timestamp" not in parameters:
        return HttpResponseBadRequest("TODO")
    elif "signature" not in parameters:
        return HttpResponseBadRequest("TODO")

    # TODO -- validate the signature
    # TODO -- validate the timestamp

    try:
        api.update_credit_request_status(
            parameters["request_uuid"],
            parameters["status"]
        )
    except:
        # TODO
        raise
    else:
        return HttpResponse()
