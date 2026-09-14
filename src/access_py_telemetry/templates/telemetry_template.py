# type: ignore

try:
    from IPython import get_ipython

    from access_py_telemetry import capture_registered_calls

    get_ipython().events.register("shell_initialized", capture_registered_calls)
    print("Intake telemetry extension loaded")
except ImportError as e:
    print("Intake telemetry extension not loaded")
    raise e
