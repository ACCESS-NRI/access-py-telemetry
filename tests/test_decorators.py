# type: ignore

from access_py_telemetry.decorators import ipy_register_func, register_func
from access_py_telemetry.registry import TelemetryRegister
from access_py_telemetry.api import ApiHandler
import pytest
import asyncio


def test_ipy_register_func(api_handler, reset_telemetry_register):
    """
    Make sure that the decorator registers the function correctly.
    """

    @ipy_register_func(
        service="intake_catalog",
        extra_fields={"model": "ACCESS-OM2", "random_number": 2},
        pop_fields=["session_id"],
    )
    def my_func():
        pass

    my_func()

    register = TelemetryRegister("intake_catalog")
    api_handler = ApiHandler()
    blank_registries = {
        key: {} for key in api_handler.endpoints if key != "intake_catalog"
    }

    assert api_handler.extra_fields == {
        "intake_catalog": {"model": "ACCESS-OM2", "random_number": 2},
        **blank_registries,
    }

    assert api_handler.pop_fields == {"intake_catalog": ["session_id"]}

    assert my_func.__name__ in register

    # Reset the register to avoid breaking other tests

    register.deregister(my_func.__name__)


@pytest.mark.asyncio
async def test_register_func(api_handler, reset_telemetry_register):
    """
    Use the register_func decorator factory to register a function.
    """

    @register_func(
        service="intake_catalog",
        extra_fields={"model": "ACCESS-OM2", "random_number": 2},
        pop_fields=["session_id"],
    )
    def my_func():
        pass

    register = TelemetryRegister("intake_catalog")
    api_handler = ApiHandler()

    blank_registries = {
        key: {} for key in api_handler.endpoints if key != "intake_catalog"
    }

    assert api_handler.extra_fields == {
        "intake_catalog": {"model": "ACCESS-OM2", "random_number": 2},
        **blank_registries,
    }

    assert api_handler.pop_fields == {"intake_catalog": ["session_id"]}

    assert my_func.__name__ in register

    my_func()
    await asyncio.sleep(0)

    # Not quiet how to test this part of the code right now...

    # api_handler.server_url = "http://test_server.com"
    # with pytest.warns(RuntimeWarning):
    #     my_func()
    #     await asyncio.sleep(0)

    # Shtudown the event loop

    # Reset the register to avoid breaking other tests

    register.deregister(my_func.__name__)
