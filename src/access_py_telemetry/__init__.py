"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0

Top-level package for access-ipy-telemetry.
"""

import warnings
from IPython.core.getipython import get_ipython
from IPython.core.interactiveshell import InteractiveShell

from . import _version
from .ast import capture_registered_calls
from .api import SessionID  # noqa
from .registry import RegisterWarning
from .utils import ENDPOINTS, REGISTRIES


# Make sure that our registries & endpoints match up
if not set(REGISTRIES.keys()) == set(ENDPOINTS.keys()):
    warnings.warn(
        "Mismatch between registries and endpoints - some telemetry calls may not be recorded.",
        category=RegisterWarning,
    )


def load_ipython_extension(ipython: InteractiveShell) -> None:
    """
    Load the IPython extension and register it to run before cells.
    """
    ipython.events.register("pre_run_cell", capture_registered_calls)  # type: ignore
    return None


# Register the extension
ip = get_ipython()  # type: ignore
if ip:
    load_ipython_extension(ip)


__version__ = _version.get_versions()["version"]  # type: ignore
