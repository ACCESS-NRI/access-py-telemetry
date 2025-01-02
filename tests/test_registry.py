#!/usr/bin/env python

"""Tests for `access_ipy_telemetry` package."""

from access_ipy_telemetry.registry import TelemetryRegister
from pydantic import ValidationError
import pytest


def test_telemetry_register():
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

    assert set(session2) == {
        "esm_datastore.search",
        "DfFileCatalog.search",
    }

    with pytest.raises(ValidationError):
        session1.register(1.0)

    with pytest.raises(ValidationError):
        session1.deregister(1.0, 2.0, [3.0])

    session3 = TelemetryRegister("catalog")

    assert set(session3) == {
        "esm_datastore.search",
        "DfFileCatalog.search",
    }
