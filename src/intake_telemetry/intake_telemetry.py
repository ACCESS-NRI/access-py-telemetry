"""Main module."""

import ast
import hashlib
import datetime
import httpx
import asyncio
from IPython import get_ipython
import warnings
import os

# TELEMETRY_SERVER_URL = "http://127.0.0.1:8000"
TELEMETRY_SERVER_URL = "https://intake-telemetry-bb870061f91a.herokuapp.com"

TELEMETRY_REGISTRED_FUNCTIONS = [
    "esm_datastore.search",
    "DfFileCatalog.search",
    "DfFileCatalog.__getitem__",
]


class SessionID:
    """
    Singleton class to store and generate a unique session ID.

    This class ensures that only one instance of the session ID exists. The session
    ID is generated the first time it is accessed and is represented as a string.
    The session ID is created using the current user's login name and the current
    timestamp, hashed with SHA-256.

    Methods:
        __new__(cls, *args, **kwargs): Ensures only one instance of the class is created.
        __init__(self): Initializes the instance and sets pandas options.
        __get__(self, obj: object, objtype: type | None = None) -> str: Generates and returns the session ID.
        create_session_id() -> str: Static method to create a unique session ID.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return None
        self.set_pd_options()
        self.initialized = True

    def __get__(self, obj: object, objtype: type | None = None) -> str:
        if not hasattr(self, "value"):
            self.value = create_session_id()
        return self.value

    @staticmethod
    def create_session_id() -> str:
        login = os.getlogin()
        timestamp = datetime.datetime.now().isoformat()
        session_str = f"{login}_{timestamp}"
        session_id = hashlib.sha256((session_str).encode()).hexdigest()
        return session_id


def send_api_request(function_name: str, args: list, kwargs: dict) -> None:
    """
    Send an API request with telemetry data.

    Parameters
    ----------
    function_name : str
        The name of the function being tracked.
    args : list
        The list of positional arguments passed to the function.
    kwargs : dict
        The dictionary of keyword arguments passed to the function.

    Returns
    -------
    None

    Warnings
    --------
    RuntimeWarning
        If the request fails.

    Notes
    -----
    SessionID() is a lazily evaluated singleton, so it looks like we are
    going to generate a new session ID every time we call this function, but we
    aren't. I've also modified __get__, so SessionID() evaluates to a string.
    """

    telemetry_data = {
        "name": os.getlogin(),
        "function": function_name,
        "args": args,
        "kwargs": kwargs,
        "session_id": SessionID(),
    }

    endpoint = f"{TELEMETRY_SERVER_URL}/intake/update"

    async def send_telemetry(data):
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(endpoint, json=data, headers=headers)
                response.raise_for_status()
            except httpx.RequestError as e:
                warnings.warn(
                    f"Request failed: {e}", category=RuntimeWarning, stacklevel=2
                )

    # Check if there's an existing event loop, otherwise create a new one
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        loop.create_task(send_telemetry(telemetry_data))
    else:
        breakpoint()
        loop.create_task(send_telemetry(telemetry_data))
        # loop.run_until_complete(send_telemetry(telemetry_data))
    return None


def capture_datastore_searches(info):
    """
    Use the AST module to parse the code that we are executing & send an API call
    if we detect specific function or method calls.

    Parameters
    ----------
    info : IPython.core.interactiveshell.ExecutionInfo
        An object containing information about the code being executed.

    Returns
    -------
    None
    """
    code = info.raw_cell

    # Remove lines that contain IPython magic commands
    code = "\n".join(
        line for line in code.splitlines() if not line.strip().startswith("%")
    )

    tree = ast.parse(code)
    user_namespace = get_ipython().user_ns

    for node in ast.walk(tree):
        func_name = None
        if isinstance(node, ast.Call):  # Calling a function or method
            if isinstance(node.func, ast.Name):  # It's a function call
                func_name = node.func.id

            elif isinstance(node.func, ast.Attribute) and isinstance(
                node.func.value, ast.Name
            ):  # It's a method call
                instance_name = node.func.value.id
                method_name = node.func.attr

                instance = user_namespace.get(instance_name)
                if instance is not None:
                    class_name = instance.__class__.__name__
                    func_name = f"{class_name}.{method_name}"

            if func_name in TELEMETRY_REGISTRED_FUNCTIONS:
                args = [ast.dump(arg) for arg in node.args]
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
                send_api_request(
                    func_name,
                    args,
                    kwargs,
                )
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            instance_name = node.value.id
            # Evaluate the instance to get its class name
            instance = user_namespace.get(instance_name)
            if instance is not None:
                class_name = instance.__class__.__name__
                index = ast.literal_eval(node.slice)
                func_name = f"{class_name}.__getitem__"

            if func_name in TELEMETRY_REGISTRED_FUNCTIONS:
                send_api_request(func_name, args=[index], kwargs={})


def create_session_id():
    """
    Generate a session ID by hashing the login name and the current timestamp.
    """

    login = os.getlogin()
    timestamp = datetime.datetime.now().isoformat()
    session_str = f"{login}_{timestamp}"
    session_id = hashlib.sha256((session_str).encode()).hexdigest()
    return session_id
