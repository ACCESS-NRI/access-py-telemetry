#!/usr/bin/env python
# type: ignore

"""Tests for `access_py_telemetry` package."""

import access_py_telemetry.api
from access_py_telemetry.api import SessionID, ApiHandler, send_in_loop
from pydantic import ValidationError
import pytest

import time


@pytest.fixture
def local_host():
    return "http://localhost:8000"


@pytest.fixture
def default_url():
    return access_py_telemetry.api.SERVER_URL


def test_session_id_properties():
    """
    Check that the SessionID class is a lazily evaluated singleton.
    """
    id1 = SessionID()

    assert hasattr(SessionID, "_instance")

    id2 = SessionID()

    assert id1 is id2

    assert type(id1) is str

    assert len(id1) == 64

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

    ApiHandler._instance = None


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

    blank_registries = {key: {} for key in session1.registries if key != XF_NAME}

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
        "catalog": "/intake/update",
        "payu": "/payu/update",
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
        "catalog": "/intake/update",
        "payu": "/payu/update",
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


def test_api_handler_send_api_request(api_handler, capsys):
    """
    Create and send an API request with telemetry data - just to make sure that
    the request is being sent correctly.
    """
    api_handler.server_url = "http://dud/host/endpoint"

    # Pretend we only have catalog & payu services and then mock the initialisation
    # of the _extra_fields attribute

    api_handler.endpoints = {
        "catalog": "/intake/update",
        "payu": "/payu/update",
    }

    api_handler._extra_fields = {
        ep_name: {} for ep_name in api_handler.endpoints.keys()
    }

    api_handler.add_extra_fields("payu", {"model": "ACCESS-OM2", "random_number": 2})

    # Remove indeterminate fields
    api_handler.remove_fields("payu", ["session_id", "name"])

    # We should get a warning because we've used a dud url, but pytest doesn't
    # seem to capture subprocess warnings. I'm not sure there is really a good
    # way test for this.
    api_handler.send_api_request(
        service_name="payu",
        function_name="_test",
        args=[1, 2, 3],
        kwargs={"name": "test_username"},
    )

    assert api_handler._last_record == {
        "function": "_test",
        "args": [1, 2, 3],
        "kwargs": {"name": "test_username"},
        "model": "ACCESS-OM2",
        "random_number": 2,
    }


def test_send_in_loop_is_bg():
    """
    Send a request, but make sure that it runs in the background (ie. is non-blocking).

    There will be some overhead associated with the processes startup and teardown,
    but we shouldn't be waiting for the requests to finish. Using a long timeout
    and only sending 3 requests should be enough to ensure that we're not accidentally
    testing the process startup/teardown time.
    """
    start_time = time.time()

    for _ in range(3):
        send_in_loop(endpoint="https://dud/endpoint", telemetry_data={}, timeout=3)

    print("Requests sent")

    end_time = time.time()

    dt = end_time - start_time

    assert dt < 4


def test_api_handler_invalid_endpoint(api_handler):
    """
    Create and send an API request with telemetry data.
    """

    # Pretend we only have catalog & payu services and then mock the initialisation
    # of the _extra_fields attribute

    api_handler.endpoints = {
        "intake_catalog": "/intake/catalog",
    }

    api_handler._extra_fields = {
        ep_name: {} for ep_name in api_handler.endpoints.keys()
    }

    with pytest.raises(KeyError) as excinfo:
        api_handler.send_api_request(
            service_name="payu",
            function_name="_test",
            args=[1, 2, 3],
            kwargs={"name": "test_username"},
        )

    assert "Endpoint for 'payu' not found " in str(excinfo.value)

    ApiHandler._instance = None
    api_handler._instance = None
