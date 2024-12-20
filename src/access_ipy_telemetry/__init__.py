"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0

Top-level package for access-ipy-telemetry.
"""

from IPython.core.getipython import get_ipython
from IPython.core.interactiveshell import InteractiveShell

from .access_ipy_telemetry import capture_datastore_searches


def load_ipython_extension(ipython: InteractiveShell) -> None:
    """
    Load the IPython extension and register it to run before cells.
    """
    ipython.events.register("pre_run_cell", capture_datastore_searches)  # type: ignore
    return None


# Register the extension
ip = get_ipython()  # type: ignore
if ip:
    load_ipython_extension(ip)
