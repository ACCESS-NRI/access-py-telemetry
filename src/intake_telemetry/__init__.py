"""Top-level package for intake-telemetry."""

from IPython.core.getipython import get_ipython
from IPython.core.interactiveshell import InteractiveShell

from .intake_telemetry import capture_datastore_searches


__author__ = """Charles Turner"""
__email__ = "charles.turner@anu.edu.au"
__version__ = "0.1.0"


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
