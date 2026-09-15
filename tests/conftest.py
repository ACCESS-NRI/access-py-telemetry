# type: ignore
from pytest import fixture

from access_py_telemetry.api import ApiHandler, ProductionToggle
from access_py_telemetry.registry import TelemetryRegister
from access_py_telemetry.utils import ENDPOINTS

# Capture the pristine class-level defaults once, before any test can mutate
# them. These are restored around every test by the autouse fixture below.
_PRODUCTION_TOGGLE_DEFAULTS = {
    "_production": True,
    "STAGING_URL": ProductionToggle.STAGING_URL,
    "PRODUCTION_URL": ProductionToggle.PRODUCTION_URL,
}


def _reset_api_handler():
    """Return the ApiHandler singleton to a pristine state."""
    ApiHandler._instance = None
    ApiHandler.endpoints = {key: val for key, val in ENDPOINTS.items()}
    ApiHandler.headers = {service: {} for service in ENDPOINTS}
    ApiHandler._extra_fields = {ep_name: {} for ep_name in ENDPOINTS.keys()}
    ApiHandler._pop_fields = {}
    ApiHandler._request_timeout = None
    ApiHandler._mproc_override = None
    # Clear any leaked server_url; a fresh instance's __init__ resets the
    # instance attribute, and this keeps the class-level fallback clean too.
    ApiHandler._server_url = "https://reporting.access-nri-store.cloud.edu.au"


def _reset_production_toggle():
    """Return the ProductionToggle singleton to a pristine state."""
    ProductionToggle._instance = None
    for attr, value in _PRODUCTION_TOGGLE_DEFAULTS.items():
        setattr(ProductionToggle, attr, value)


@fixture(autouse=True)
def _reset_singletons():
    """
    Reset the process-wide ApiHandler / ProductionToggle singletons around every
    test.

    These are module-level singletons, so any test that mutates them - including
    tests that merely import the real ``access_nri_intake`` catalog, which
    configures the ApiHandler as a side effect - would otherwise leak state into
    unrelated tests. Resetting on setup (not just teardown) guarantees each test
    starts from a known-clean state regardless of execution order.
    """
    _reset_api_handler()
    _reset_production_toggle()
    yield
    _reset_api_handler()
    _reset_production_toggle()


@fixture
def api_handler():
    """
    Get an instance of the APIHandler class.

    State is reset around every test by the autouse ``_reset_singletons``
    fixture, which runs first, so this simply hands back a pristine instance.
    """
    return ApiHandler()


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
    return ProductionToggle()
