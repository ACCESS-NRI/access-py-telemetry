#!/usr/bin/env python
# type: ignore

"""Tests for `access_py_telemetry` package."""

from access_py_telemetry.api import (
    SessionID,
    ApiHandler,
    ProductionToggle,
    send_in_loop,
    send_telemetry,
    _format_endpoint,
    _run_event_loop,
)
from pydantic import ValidationError
import pytest
from pytest_httpserver import HTTPServer, RequestMatcher
import time


@pytest.fixture
def local_host():
    return "http://localhost:8000"


@pytest.fixture
def default_url():
    return "https://reporting.access-nri-store.cloud.edu.au"


def test_session_id_properties():
    """
    Check that the SessionID class is a lazily evaluated singleton.
    """
    id1 = SessionID()

    assert hasattr(SessionID, "_instance")

    id2 = SessionID()

    assert id1 is id2

    assert type(id1) is str

    assert len(id1) == 36

    assert id1 != SessionID.create_session_id()


def test_api_handler_server_url(local_host, default_url, api_handler):
    """
    Check that the APIHandler class is a singleton.
    """

    session1 = api_handler
    session2 = ApiHandler()

    assert session1 is session2

    # Check defaults haven't changed by accident
    assert session1.server_url == default_url

    # Change the server url
    session1.server_url = local_host
    assert session2.server_url == local_host

    # ApiHandler._instance = None


def test_api_handler_extra_fields(local_host, api_handler):
    """
    Check that adding extra fields to the APIHandler class works as expected.
    """

    session1 = api_handler
    session2 = ApiHandler()

    session1.server_url = local_host
    assert session2.server_url == local_host

    # Change the extra fields - first
    with pytest.raises(AttributeError):
        session1.extra_fields = {"catalog_version": "1.0"}

    XF_NAME = "intake_catalog"

    session1.add_extra_fields(XF_NAME, {"version": "1.0"})

    blank_registries = {key: {} for key in session1.endpoints if key != XF_NAME}

    assert session2.extra_fields == {
        "intake_catalog": {"version": "1.0"},
        **blank_registries,
    }

    with pytest.raises(KeyError) as excinfo:
        session1.add_extra_fields("catalog", {"version": "2.0"})
        assert str(excinfo.value) == "Endpoint catalog not found"

    # Make sure that adding a new sesson doesn't overwrite the old one
    session3 = ApiHandler()
    assert session3 is session1
    assert session1.server_url == local_host
    assert session3.server_url == local_host


def test_api_handler_extra_fields_validation(api_handler):
    """
    Pydantic should make sure that if we try to update the extra fields, we have
    to pass the correct types, and only let us update fields through the
    add_extra_field method.
    """

    # Mock a couple of extra services

    api_handler.endpoints = {
        "catalog": "intake/update",
        "payu": "payu/update",
    }

    with pytest.raises(AttributeError):
        api_handler.extra_fields = {
            "catalog": {"version": "1.0"},
            "payu": {"version": "1.0"},
        }

    with pytest.raises(KeyError):
        api_handler.add_extra_fields("catalogue", {"version": "2.0"})

    with pytest.raises(ValidationError):
        api_handler.add_extra_fields("catalog", ["invalid", "type"])

    api_handler.add_extra_fields("payu", {"model": "ACCESS-OM2", "random_number": 2})


def test_api_handler_remove_fields(api_handler):
    """
    Check that we can remove fields from the telemetry record.
    """

    # Pretend we only have catalog & payu services and then mock the initialisation
    # of the _extra_fields attribute

    api_handler.endpoints = {
        "catalog": "intake/update",
        "payu": "payu/update",
    }

    api_handler._extra_fields = {
        ep_name: {} for ep_name in api_handler.endpoints.keys()
    }

    # Payu wont need a 'session_id' field, so we'll remove it

    api_handler.remove_fields("payu", ["session_id"])

    api_handler.add_extra_fields("payu", {"model": "ACCESS-OM2", "random_number": 2})

    payu_record = api_handler._create_telemetry_record(
        service_name="payu", function_name="_test", args=[], kwargs={}
    )
    payu_record["name"] = "test_username"

    assert payu_record == {
        "function": "_test",
        "args": [],
        "kwargs": {},
        "name": "test_username",
        "model": "ACCESS-OM2",
        "random_number": 2,
    }

    assert api_handler._pop_fields == {"payu": ["session_id"]}

    # Now remove the 'model' field from the payu record, as a string.
    api_handler.remove_fields("payu", "model")


def test_api_handler_send_api_request(api_handler, capfd):
    """
    Create and send an API request with telemetry data - just to make sure that
    the request is being sent correctly.
    """

    # Set the private production toggle to false, so that we don't invoke the hook
    # that changes the server url to the staging server
    api_handler.server_url = "http://dud/host/endpoint"

    # Pretend we only have catalog & payu services and then mock the initialisation
    # of the _extra_fields attribute

    api_handler.endpoints = {
        "catalog": "intake/update",
        "payu": "payu/update",
    }

    api_handler._extra_fields = {
        ep_name: {} for ep_name in api_handler.endpoints.keys()
    }

    api_handler.add_extra_fields("payu", {"model": "ACCESS-OM2", "random_number": 2})

    # Remove indeterminate fields
    api_handler.remove_fields("payu", ["session_id"])

    api_handler.send_api_request(
        service_name="payu",
        function_name="_test",
        args=[1, 2, 3],
        kwargs={"random": "item"},
    )
    assert api_handler._last_record == {
        "function": "_test",
        "args": [1, 2, 3],
        "kwargs": {"random": "item"},
        "model": "ACCESS-OM2",
        "random_number": 2,
    }


def test_api_handler_invalid_endpoint(api_handler):
    """
    Create and send an API request with telemetry data.
    """

    # Pretend we only have catalog & payu services and then mock the initialisation
    # of the _extra_fields attribute

    with pytest.raises(KeyError) as excinfo:
        api_handler._get_endpoints(
            service_name="payu",
        )

    assert "Endpoint for 'payu' not found " in str(excinfo.value)


def test_send_in_loop_is_bg(httpserver: HTTPServer):
    """
    Send a request, but make sure that it runs in the background (ie. is non-blocking).

    There will be some overhead associated with the processes startup and teardown,
    but we shouldn't be waiting for the requests to finish. Using a long timeout
    and only sending 3 requests should be enough to ensure that we're not accidentally
    testing the process startup/teardown time.
    """
    httpserver.expect_request("/loop-endpoint").respond_with_data("Request received")
    httpserver.expect_request("/slow-endpoint").respond_with_handler(time.sleep(2))

    assert len(httpserver.log) == 0

    for _ in range(3):
        send_in_loop(
            endpoint=httpserver.url_for("/loop-endpoint"), telemetry_data={}, timeout=3
        )

    httpserver.assert_request_made(RequestMatcher("/loop-endpoint"), count=3)
    assert len(httpserver.log) == 3

    start_time = time.time()
    for _ in range(3):
        send_in_loop(
            endpoint=httpserver.url_for("/sleep-endpoint"), telemetry_data={}, timeout=3
        )

    end_time = time.time()

    dt = end_time - start_time

    assert dt < 4
    assert len(httpserver.log) == 6


def test_api_handler_set_timeout(api_handler):
    """
    Make sure that we can set the timeout for the APIHandler class, and that it
    is either a positive float or None.
    """

    with pytest.raises(ValueError):
        api_handler.request_timeout = -1

    with pytest.raises(TypeError):
        api_handler.request_timeout = "string"

    api_handler.request_timeout = 1.0

    assert api_handler.request_timeout == 1.0

    api_handler.request_timeout = None

    assert api_handler.request_timeout is None


def test_api_handler_url_warnings(api_handler):
    """
    Make sure that we get a warning if we try to set the server_url to a non-reporting
    url.
    """

    with pytest.warns(
        UserWarning, match="Server URL not an ACCESS-NRI Reporting API URL"
    ):
        api_handler.server_url = "http://localhost:8000"

    with pytest.warns(
        UserWarning, match="Server URL does not end with 'api' or 'api/'"
    ):
        api_handler.server_url = "https://localhost:8000"


def test_api_handler_url_no_warnings(api_handler, recwarn):
    """
    If we set NRI_USER to False, we shouldn't get any warnings - other orgs/users
    can do what they like.
    """
    assert len(recwarn) == 0

    import access_py_telemetry.api

    access_py_telemetry.api.NRI_USER = False
    # Would trigger two warnings if NRI_USER was True
    api_handler.server_url = "http://localhost:8000"
    # Clean this up
    access_py_telemetry.api.NRI_USER = True

    assert len(recwarn) == 0


@pytest.mark.parametrize(
    "server_url, endpoint, expected",
    [
        (
            "http://localhost:8000",
            "/some/endpoint",
            "http://localhost:8000/some/endpoint/",
        ),
        (
            "http://localhost:8000/",
            "some/endpoint/",
            "http://localhost:8000/some/endpoint/",
        ),
        (
            "https://localhost:8000",
            "/some/endpoint",
            "https://localhost:8000/some/endpoint/",
        ),
        (
            "https://localhost:8000/",
            "some/endpoint/",
            "https://localhost:8000/some/endpoint/",
        ),
    ],
)
def test_format_endpoint(server_url, endpoint, expected):
    assert _format_endpoint(server_url, endpoint) == expected


def test_api_handler_add_generic_token(api_handler):
    """
    Add a token to the APIHandler class, without specifying a service, and make
    sure it's applied to each service.
    """
    api_handler.set_headers(None, {"generic_token": "password123"})

    assert api_handler.headers == {
        endpoint: {"generic_token": "password123"} for endpoint in api_handler.endpoints
    }

    api_handler.clear_headers(None)

    assert api_handler.headers == {endpoint: {} for endpoint in api_handler.endpoints}


def test_api_handler_add_single_service_token(api_handler):
    """
    Add a token to the APIHandler class, specifying a service, and make sure it's
    only applied to that service.
    """
    endpoints = [k for k in api_handler.endpoints.keys()]
    specified_service, *unspecified_services = endpoints
    api_handler.set_headers(specified_service, {"catalog_token": "password123"})

    assert api_handler.headers == {
        specified_service: {"catalog_token": "password123"},
        **{service: {} for service in unspecified_services},
    }

    api_handler.clear_headers("intake_catalog")

    assert api_handler.headers == {endpoint: {} for endpoint in api_handler.endpoints}


def test_api_handler_sends_correct_headers(api_handler, httpserver):
    api_handler.server_url = httpserver.url_for("/")
    api_handler.endpoints = {"endpoint": "endpoint"}
    api_handler.set_headers(None, {"generic_token": "password123"})
    httpserver.expect_request(
        "/endpoint", headers={"generic_token": "password123"}
    ).respond_with_data("Request received")
    api_handler.send_api_request(
        service_name="endpoint",
        function_name="test",
        args=[1, 2, 3],
        kwargs={"random": "item"},
    )


def test_api_handler_raises_invalid_service_headers(api_handler):
    """
    Make sure that we can't set headers for a service that doesn't exist.
    """
    with pytest.raises(KeyError):
        api_handler.set_headers("invalid_service", {"catalog_token": "password123"})

    with pytest.raises(KeyError):
        api_handler.clear_headers("invalid_service")


def test__run_event_loop(httpserver):
    """
    USe the _run_event_loop function to send a request to a server, and make sure
    that the request is sent correctly.
    """
    _run_event_loop(httpserver.url_for("/"), {}, {})
    httpserver.assert_request_made(RequestMatcher("/"), count=1)


def test_production_toggle(production_toggle, api_handler):
    """
    Make sure that the production toggle works as expected.
    """

    # Check that the production toggle is set to True by default
    assert production_toggle._production
    assert production_toggle.production

    s = str(production_toggle)
    assert s == "ProductionToggle(production=True)"

    # Check that the production toggle can be set to False
    production_toggle.production = False

    assert not production_toggle._production
    assert not production_toggle.production
    assert api_handler.server_url == ProductionToggle.STAGING_URL

    # Check that the production toggle can be set back to True
    production_toggle.production = True

    assert production_toggle._production
    assert production_toggle.production
    assert api_handler.server_url == ProductionToggle.PRODUCTION_URL

    with pytest.raises(TypeError):
        production_toggle.production = 1


@pytest.mark.parametrize(
    "warn_set, response, raise_warning",
    [
        (  # No warning on 200
            True,
            {"response_data": "Success!", "status": 200},
            False,
        ),
        (  # Warn on 403, if warn_set is True
            True,
            {"response_data": "Auth Failure!", "status": 403},
            True,
        ),
        (  # Dont warn on 403, if warn_set is False
            False,
            {"response_data": "Auth Failure!", "status": 403},
            False,
        ),
        (  # Warn on 404, if warn_set is True
            True,
            {"response_data": "Auth Failure!", "status": 404},
            True,
        ),
        (  # Dont warn on 404, if warn_set is False
            False,
            {"response_data": "Auth Failure!", "status": 404},
            False,
        ),
        (  # Warn on 500, if warn_set is True
            True,
            {"response_data": "Auth Failure!", "status": 500},
            True,
        ),
        (  # Dont warn on 500, if warn_set is False
            False,
            {"response_data": "Auth Failure!", "status": 500},
            False,
        ),
    ],
)
@pytest.mark.asyncio
async def test_send_telemetry_warning_toggle(
    httpserver: HTTPServer, warn_set, response, raise_warning
):
    """
    Send a request, but make sure that it runs in the background (ie. is non-blocking).

    There will be some overhead associated with the processes startup and teardown,
    but we shouldn't be waiting for the requests to finish. Using a long timeout
    and only sending 3 requests should be enough to ensure that we're not accidentally
    testing the process startup/teardown time.
    """
    httpserver.expect_request("/endpoint").respond_with_data(**response)

    if raise_warning:
        with pytest.warns(RuntimeWarning, match="Request failed"):
            await send_telemetry(
                endpoint=httpserver.url_for("/endpoint"),
                data={},
                headers={},
                warn=warn_set,
            )
    else:
        await send_telemetry(
            endpoint=httpserver.url_for("/endpoint"),
            data={},
            headers={},
            warn=warn_set,
        )
