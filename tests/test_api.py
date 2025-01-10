#!/usr/bin/env python
# type: ignore

"""Tests for `access_py_telemetry` package."""

import access_py_telemetry.api
from access_py_telemetry.api import SessionID, ApiHandler
from pydantic import ValidationError
import pytest


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


def test_api_handler_server_url(local_host, default_url):
    """
    Check that the APIHandler class is a singleton.
    """
    ApiHandler._instance = None

    session1 = ApiHandler()
    session2 = ApiHandler()

    assert session1 is session2

    # Check defaults haven't changed by accident
    assert session1.server_url == default_url

    # Change the server url
    session1.server_url = local_host
    assert session2.server_url == local_host

    ApiHandler._instance = None


def test_api_handler_extra_fields(local_host):
    """
    Check that adding extra fields to the APIHandler class works as expected.
    """

    ApiHandler._instance = None

    session1 = ApiHandler()
    session2 = ApiHandler()

    session1.server_url = local_host
    assert session2.server_url == local_host

    # Change the extra fields - first
    with pytest.raises(AttributeError):
        session1.extra_fields = {"catalog_version": "1.0"}

    session1.add_extra_fields("catalog", {"version": "1.0"})

    blank_registries = {key: {} for key in session1.registries if key != "catalog"}

    assert session2.extra_fields == {"catalog": {"version": "1.0"}, **blank_registries}

    with pytest.raises(KeyError) as excinfo:
        session1.add_extra_fields("catalogue", {"version": "2.0"})
        assert str(excinfo.value) == "Endpoint catalogue not found"

    # Make sure that adding a new sesson doesn't overwrite the old one
    session3 = ApiHandler()
    assert session3 is session1
    assert session1.server_url == local_host
    assert session3.server_url == local_host

    ApiHandler._instance = None


def test_api_handler_extra_fields_validation():
    """
    Pydantic should make sure that if we try to update the extra fields, we have
    to pass the correct types, and only let us update fields through the
    add_extra_field method.
    """
    ApiHandler._instance = None
    api_handler = ApiHandler()

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

    # Reset endpoints to avoid breaking other tests - we have to be careful here
    # because we're using a singleton
    api_handler.endpoints = access_py_telemetry.api.ENDPOINTS
    api_handler._extra_fields = {
        ep_name: {} for ep_name in api_handler.endpoints.keys()
    }

    ApiHandler._instance = None


def test_api_handler_remove_fields():
    """
    Check that we can remove fields from the telemetry record.
    """
    ApiHandler._instance = None
    api_handler = ApiHandler()

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

    ApiHandler._instance = None


def test_api_handler_send_api_request_no_loop(local_host):
    """
    Create and send an API request with telemetry data.
    """

    ApiHandler._instance = None
    api_handler = ApiHandler()
    api_handler.server_url = local_host

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

    with pytest.warns(RuntimeWarning) as warnings_record:
        api_handler.send_api_request(
            service_name="payu",
            function_name="_test",
            args=[1, 2, 3],
            kwargs={"name": "test_username"},
        )

    # This should contain two warnings - one for the failed request and one for the
    # event loop
    assert len(warnings_record) == 2

    assert api_handler._last_record == {
        "function": "_test",
        "args": [1, 2, 3],
        "kwargs": {"name": "test_username"},
        "model": "ACCESS-OM2",
        "random_number": 2,
    }

    ApiHandler._instance = None


def test_api_handler_invalid_endpoint():
    """
    Create and send an API request with telemetry data.
    """

    ApiHandler._instance = None
    api_handler = ApiHandler()

    # Pretend we only have catalog & payu services and then mock the initialisation
    # of the _extra_fields attribute

    api_handler.endpoints = {
        "catalog": "/intake/update",
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
