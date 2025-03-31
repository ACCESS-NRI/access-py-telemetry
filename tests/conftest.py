# type: ignore
from pytest import fixture
from access_py_telemetry.api import ApiHandler, ProductionToggle
from access_py_telemetry.utils import ENDPOINTS
from access_py_telemetry.registry import TelemetryRegister


@fixture
def api_handler():
    """
    Get an instance of the APIHandler class, and then reset it after the test.

    """
    yield ApiHandler()

    ApiHandler._instance = None
    ApiHandler._server_url = "https://reporting.access-nri-store.cloud.edu.au"
    ApiHandler.headers = {service: {} for service in ENDPOINTS}
    ApiHandler.endpoints = {key: val for key, val in ENDPOINTS.items()}
    ApiHandler._extra_fields = {ep_name: {} for ep_name in ENDPOINTS.keys()}
    ApiHandler._pop_fields = {}


@fixture
def reset_telemetry_register():
    """
    Get the TelemetryRegister class for the catalog service.
    """
    yield TelemetryRegister
    TelemetryRegister._instances = {}


@fixture
def production_toggle():
    """
    Get the production toggle for the APIHandler class.
    """
    _ = ProductionToggle()
    del _
    yield ProductionToggle()
    ProductionToggle._instance = None
    ProductionToggle._production = True
    ProductionToggle.STAGING_URL = (
        "https://staging-reporting.access-nri-store.cloud.edu.au/api/"
    )
    ProductionToggle.PRODUCTION_URL = (
        "https://reporting.access-nri-store.cloud.edu.au/api/"
    )
