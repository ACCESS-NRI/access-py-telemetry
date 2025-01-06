try:
    from access_py_telemetry import capture_registered_calls
    from IPython import get_ipython  # type: ignore[attr-defined]

    get_ipython().events.register("shell_initialized", capture_registered_calls)  # type: ignore
    print("Intake telemetry extension loaded")
except ImportError as e:
    print("Intake telemetry extension not loaded")
    raise e
