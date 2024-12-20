try:
    from access_ipy_telemetry import capture_datastore_searches
    from IPython import get_ipython

    get_ipython().events.register("shell_initialized", capture_datastore_searches)
    print("Intake telemetry extension loaded")
except ImportError as e:
    print("Intake telemetry extension not loaded")
    raise e
