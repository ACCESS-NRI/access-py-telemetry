#!/usr/bin/env python

"""Tests for `intake_telemetry` package."""

from intake_telemetry.intake_telemetry import SessionID


def test_session_id():
    """
    Check that the SessionID class is a lazily evaluated singleton.
    """
    id1 = SessionID()
    id2 = SessionID()

    assert id1 is id2

    assert type(id1) is str

    assert len(id1) == 64

    assert id1 != SessionID.create_session_id()
