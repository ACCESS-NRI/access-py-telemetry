#!/usr/bin/env python
# type: ignore

"""Tests for `access_py_telemetry` package."""

from access_py_telemetry.registry import TelemetryRegister
from pydantic import ValidationError
import pytest


def test_telemetry_register_unique(reset_telemetry_register):
    """
    Check that the TelemetryRegister class is a singleton & that we can register
    and deregister functions as we would expect.
    """
    TelemetryRegister._instances = {}
    session1 = TelemetryRegister("intake_catalog")
    session2 = TelemetryRegister("intake_catalog")

    # assert session1 is session2

    assert set(session1) >= {
        "esm_datastore.search",
        "DfFileCatalog.search",
        "DfFileCatalog.__getitem__",
    }

    session1.register("test_function")

    assert set(session2) >= {
        "esm_datastore.search",
        "DfFileCatalog.search",
        "DfFileCatalog.__getitem__",
        "test_function",
    }

    session1.deregister("test_function", "DfFileCatalog.__getitem__")

    session3 = TelemetryRegister("intake_catalog")

    assert set(session3) >= {
        "esm_datastore.search",
        "DfFileCatalog.search",
    }

    assert "test_function" not in session3
    assert "DfFileCatalog.__getitem__" not in session3

    assert set(session2) >= {
        "esm_datastore.search",
        "DfFileCatalog.search",
    }

    assert "test_function" not in session2
    assert "DfFileCatalog.__getitem__" not in session2


def test_telemetry_register_validation(reset_telemetry_register):
    session_register = TelemetryRegister("intake_catalog")

    with pytest.raises(ValidationError):
        session_register.register(1.0)

    with pytest.raises(ValidationError):
        session_register.deregister(1.0, 2.0, [3.0])

    def test_function():
        pass

    session_register.register(test_function)

    assert "test_function" in session_register

    for func_str in [
        "test_function",
        "esm_datastore.search",
        "DfFileCatalog.__getitem__",
        "DfFileCatalog.search",
    ]:
        assert func_str in str(session_register)
        assert func_str in repr(session_register)

    session_register.deregister(test_function)

    for func_str in [
        "esm_datastore.search",
        "DfFileCatalog.__getitem__",
        "DfFileCatalog.search",
    ]:
        assert func_str in str(session_register)
        assert func_str in repr(session_register)

    assert "test_function" not in session_register
