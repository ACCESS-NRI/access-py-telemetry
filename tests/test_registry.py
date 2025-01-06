#!/usr/bin/env python

"""Tests for `access_py_telemetry` package."""

from access_py_telemetry.registry import TelemetryRegister
from pydantic import ValidationError
import pytest


def test_telemetry_register_unique():
    """
    Check that the TelemetryRegister class is a singleton & that we can register
    and deregister functions as we would expect.
    """
    session1 = TelemetryRegister("catalog")
    session2 = TelemetryRegister("catalog")

    # assert session1 is session2

    assert set(session1) == {
        "esm_datastore.search",
        "DfFileCatalog.search",
        "DfFileCatalog.__getitem__",
    }

    session1.register("test_function")

    assert set(session2) == {
        "esm_datastore.search",
        "DfFileCatalog.search",
        "DfFileCatalog.__getitem__",
        "test_function",
    }

    session1.deregister("test_function", "DfFileCatalog.__getitem__")

    session3 = TelemetryRegister("catalog")

    assert set(session3) == {
        "esm_datastore.search",
        "DfFileCatalog.search",
    }

    assert set(session2) == {
        "esm_datastore.search",
        "DfFileCatalog.search",
    }

    from access_py_telemetry.registry import REGISTRIES

    session1.registry = REGISTRIES["catalog"]


def test_telemetry_register_validation():
    session_register = TelemetryRegister("catalog")

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

    from access_py_telemetry.registry import REGISTRIES

    session_register.registry = REGISTRIES["catalog"]
