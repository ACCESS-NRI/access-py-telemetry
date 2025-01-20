# type: ignore
from pytest import fixture
from access_py_telemetry.api import ApiHandler, ENDPOINTS, SERVER_URL, REGISTRIES
from access_py_telemetry.registry import TelemetryRegister


@fixture
def api_handler():
    """
    Get an instance of the APIHandler class, and then reset it after the test.

    """
    yield ApiHandler()

    ApiHandler._instance = None
    ApiHandler._server_url = SERVER_URL[:]
    ApiHandler.endpoints = {key: val for key, val in ENDPOINTS.items()}
    ApiHandler.registries = {key for key in REGISTRIES}
    ApiHandler._extra_fields = {ep_name: {} for ep_name in ENDPOINTS.keys()}
    ApiHandler._pop_fields = {}


@fixture
def reset_telemetry_register():
    """
    Get the TelemetryRegister class for the catalog service.
    """
    yield TelemetryRegister
    TelemetryRegister._instances = {}
