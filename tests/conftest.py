from pytest import fixture
from access_py_telemetry.api import ApiHandler, SERVER_URL, ENDPOINTS
from access_py_telemetry.registry import TelemetryRegister, REGISTRIES
import copy


@fixture(scope="session")
def api_handler():
    """
    Get an instance of the APIHandler class, and then reset it after the test.
    """
    yield ApiHandler()

    # Reset the api_handler to avoid breaking other tests

    for ep_name in ENDPOINTS.keys():
        TelemetryRegister(ep_name).registry = copy.deepcopy(REGISTRIES.get(ep_name, {}))

    ApiHandler().endpoints = ENDPOINTS
    ApiHandler()._extra_fields = {ep_name: {} for ep_name in ENDPOINTS.keys()}
    ApiHandler()._pop_fields = {}
    ApiHandler()._server_url = SERVER_URL


@fixture(scope="session")
def cat_register():
    """
    Get an instance of the TelemetryRegister class for the catalog service.
    """
    yield TelemetryRegister("catalog")

    # Reset the register to avoid breaking other tests
    TelemetryRegister("catalog").registry = copy.deepcopy(REGISTRIES["catalog"])


@fixture(scope="session")
def payu_register():
    """
    Get an instance of the TelemetryRegister class for the catalog service.
    """
    yield TelemetryRegister("payu")

    # Reset the register to avoid breaking other tests
    TelemetryRegister("payu").registry = copy.deepcopy(REGISTRIES.get("payu", {}))
