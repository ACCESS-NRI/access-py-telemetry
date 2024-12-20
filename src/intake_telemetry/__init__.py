"""Top-level package for intake-telemetry."""

from IPython import get_ipython

from .intake_telemetry import capture_datastore_searches


__author__ = """Charles Turner"""
__email__ = "charles.turner@anu.edu.au"
__version__ = "0.1.0"


def load_ipython_extension(ipython):
    ipython.events.register("pre_run_cell", capture_datastore_searches)


# Register the extension
ip = get_ipython()
if ip:
    load_ipython_extension(ip)
