"""Main module."""

from typing import Any, TypeVar, Type
import ast
import hashlib
import datetime
import httpx
import asyncio
from IPython.core.getipython import get_ipython
from IPython.core.interactiveshell import ExecutionInfo
import warnings
import os

# TELEMETRY_SERVER_URL = "http://127.0.0.1:8000"
TELEMETRY_SERVER_URL = "https://tracking-services-d6c2fd311c12.herokuapp.com"

TELEMETRY_REGISTRED_FUNCTIONS = [
    "esm_datastore.search",
    "DfFileCatalog.search",
    "DfFileCatalog.__getitem__",
]

T = TypeVar("T", bound="SessionID")


class SessionID:
    """
    Singleton class to store and generate a unique session ID.

    This class ensures that only one instance of the session ID exists. The session
    ID is generated the first time it is accessed and is represented as a string.
    The session ID is created using the current user's login name and the current
    timestamp, hashed with SHA-256.

    Methods:
        __new__(cls, *args, **kwargs): Ensures only one instance of the class is created.
        __init__(self): Initializes the instance.
        __get__(self, obj: object, objtype: type | None = None) -> str: Generates and returns the session ID.
        create_session_id() -> str: Static method to create a unique session ID.
    """

    _instance = None

    def __new__(cls: Type[T]) -> T:
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "initialized"):
            return None
        self.initialized = True

    def __get__(self, obj: object, objtype: type | None = None) -> str:
        if not hasattr(self, "value"):
            self.value = SessionID.create_session_id()
        return self.value

    @staticmethod
    def create_session_id() -> str:
        login = os.getlogin()
        timestamp = datetime.datetime.now().isoformat()
        session_str = f"{login}_{timestamp}"
        session_id = hashlib.sha256((session_str).encode()).hexdigest()
        return session_id


def send_api_request(
    function_name: str,
    args: list[Any],
    kwargs: dict[str, Any | None],
    server_url: str = TELEMETRY_SERVER_URL,
) -> None:
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

    endpoint = f"{server_url}/intake/update"

    async def send_telemetry(data: dict[str, Any]) -> None:
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(endpoint, json=data, headers=headers)
                print("Telemetry Posted!")
                response.raise_for_status()
            except httpx.RequestError as e:
                warnings.warn(
                    f"Request failed: {e}", category=RuntimeWarning, stacklevel=2
                )
        return None

    # Check if there's an existing event loop, otherwise create a new one
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        loop.create_task(send_telemetry(telemetry_data))
    else:
        # breakpoint()
        # loop.create_task(send_telemetry(telemetry_data))
        loop.run_until_complete(send_telemetry(telemetry_data))
        warnings.warn(
            "Event loop not running, telemetry will block execution",
            category=RuntimeWarning,
        )
    return None


def capture_datastore_searches(info: ExecutionInfo) -> None:
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

    if code is None:
        return None

    # Remove lines that contain IPython magic commands
    code = "\n".join(
        line for line in code.splitlines() if not line.strip().startswith("%")
    )

    tree = ast.parse(code)
    user_namespace: dict[str, Any] = get_ipython().user_ns  # type: ignore

    # Temporary mapping for instances created in the same cell
    temp_variable_types = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):  # Variable assignment
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id
                    if isinstance(node.value, ast.Call):
                        if isinstance(node.value.func, ast.Name):
                            class_name = node.value.func.id
                            temp_variable_types[var_name] = class_name

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
                else:
                    class_name = temp_variable_types.get(instance_name, "Unknown")

                func_name = f"{class_name}.{method_name}"

            if func_name in TELEMETRY_REGISTRED_FUNCTIONS:
                args = [ast.dump(arg) for arg in node.args]
                kwargs = {
                    kw.arg: ast.literal_eval(kw.value)
                    for kw in node.keywords
                    if kw.arg is not None  # Redundant check to make mypy happy
                }
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
    return None
