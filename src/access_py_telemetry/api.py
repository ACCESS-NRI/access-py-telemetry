"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any, Type, TypeVar, Iterable
import warnings
import getpass
import datetime
import hashlib
import httpx
import asyncio
import pydantic
import yaml
import multiprocessing
from pathlib import Path
from multiprocessing import Process

try:
    multiprocessing.set_start_method("spawn")
except RuntimeError:
    """
    Since this is a side effect on module import, we can't guarantee that it will
    always be called before the first Process is created, or that the start method
    isn't already set. In this case, we just ignore the error - the processes should
    still work fine.
    """
from .utils import ENDPOINTS, REGISTRIES

S = TypeVar("S", bound="SessionID")
H = TypeVar("H", bound="ApiHandler")

with open(Path(__file__).parent / "config.yaml", "r") as f:
    config = yaml.safe_load(f)

SERVER_URL = "https://tracking-services-d6c2fd311c12.herokuapp.com"


class ApiHandler:
    """
    Singleton class to handle API requests. I'm only using a class here so we can save
    the extra_fields attribute.

    Singleton so that we can add extra fields elsewhere in the code and have them
    persist across all telemetry calls.
    """

    _instance = None
    _server_url = SERVER_URL[:]
    endpoints = {service: endpoint for service, endpoint in ENDPOINTS.items()}
    registries = {service for service in REGISTRIES}
    _extra_fields: dict[str, dict[str, Any]] = {ep_name: {} for ep_name in ENDPOINTS}
    _pop_fields: dict[str, list[str]] = {}

    def __new__(cls: Type[H]) -> H:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
    ) -> None:
        if hasattr(self, "_initialized"):
            return None
        self._initialized = True

    @property
    def extra_fields(self) -> dict[str, Any]:
        return self._extra_fields

    @pydantic.validate_call
    def add_extra_fields(self, service_name: str, fields: dict[str, Any]) -> None:
        """
        Add an extra field to the telemetry data. Only works for services that
        already have an endpoint defined.
        """
        if service_name not in self.endpoints:
            raise KeyError(f"Endpoint for '{service_name}' not found")
        self._extra_fields[service_name] = fields
        return None

    @property
    def server_url(self) -> str:
        return self._server_url

    @server_url.setter
    def server_url(self, url: str) -> None:
        """
        Set the server URL for the telemetry API.
        """
        self._server_url = url
        return None

    @property
    def pop_fields(self) -> dict[str, list[str]]:
        return self._pop_fields

    @pydantic.validate_call
    def remove_fields(self, service: str, fields: str | Iterable[str]) -> None:
        """
        Set the fields to remove from the telemetry data for a given service. Useful for excluding default
        fields that are not needed for a particular telemetry call: eg, removing
        Session tracking if a CLI is being used.

        Note: This does not use a set union, so you must specify all fields you want to remove in one call.
        # TODO: Maybe make this easier to use?
        """
        if isinstance(fields, str):
            fields = [fields]
        self._pop_fields[service] = list(fields)

    def send_api_request(
        self,
        service_name: str,
        function_name: str,
        args: list[Any] | tuple[Any, ...],
        kwargs: dict[str, Any | None],
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

        """

        telemetry_data = self._create_telemetry_record(
            service_name, function_name, args, kwargs
        )

        try:
            endpoint = self.endpoints[service_name]
        except KeyError as e:
            raise KeyError(
                f"Endpoint for '{service_name}' not found in {self.endpoints}"
            ) from e

        endpoint = f"{self.server_url}{endpoint}"

        send_in_loop(endpoint, telemetry_data)
        return None

    def _create_telemetry_record(
        self,
        service_name: str,
        function_name: str,
        args: list[Any] | tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create and return a telemetry record, cache it as an instance attribute.

        Notes
        -----
        SessionID() is a lazily evaluated singleton, so it looks like we are
        going to generate a new session ID every time we call this function, but we
        aren't. I've also modified __get__, so SessionID() evaluates to a string.
        """
        telemetry_data = {
            "name": getpass.getuser(),
            "function": function_name,
            "args": args,
            "kwargs": kwargs,
            "session_id": SessionID(),
            **self.extra_fields.get(service_name, {}),
        }

        for field in self.pop_fields.get(service_name, []):
            telemetry_data.pop(field)

        self._last_record = telemetry_data
        return telemetry_data


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

    def __new__(cls: Type[S]) -> S:
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
        login = getpass.getuser()
        timestamp = datetime.datetime.now().isoformat()
        session_str = f"{login}_{timestamp}"
        session_id = hashlib.sha256((session_str).encode()).hexdigest()
        return session_id


async def send_telemetry(endpoint: str, data: dict[str, Any]) -> None:
    """
    Asynchronously send telemetry data to the specified endpoint.

    Parameters
    ----------
    endpoint : str
        The URL to send the telemetry data to.
    data : dict

    Returns
    -------
    None

    Warnings
    --------
    RuntimeWarning
        If the request fails.
    """
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        try:
            print(f"Posting telemetry to {endpoint}")
            response = await client.post(endpoint, json=data, headers=headers)
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            warnings.warn(f"Request failed: {e}", category=RuntimeWarning, stacklevel=2)
    return None


def send_in_loop(
    endpoint: str, telemetry_data: dict[str, Any], timeout: float | None = None
) -> None:
    """
    Wraps the send_telemetry function in an event loop. This function will:
    - Check if an event loop is already running
    - If an event loop is running, send the telemetry data in the background
    - If an event loop is not running, create a new event loop in a separate process
        and send the telemetry data in the background using that loop.

    Parameters
    ----------
    endpoint : str
        The URL to send the telemetry data to.
    telemetry_data : dict
        The telemetry data to send.
    timeout : float, optional
        The maximum time to wait for the coroutine to finish. If the coroutine takes
        longer than this time, a TimeoutError will be raised. If None, the coroutine
        will terminate after 60 seconds.

    Returns
    -------
    None

    """
    timeout = timeout or 60

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _run_in_proc(endpoint, telemetry_data, timeout)
    else:
        loop.create_task(send_telemetry(endpoint, telemetry_data))
        return None


def _run_event_loop(endpoint: str, telemetry_data: dict[str, Any]) -> None:
    """
    Handles the creation and running of an event loop for sending telemetry data.
    This function is intended to be run in a separate process, and will:
    - Create a new event loop
    - Send the telemetry data
    - Run the event loop until the telemetry data is sent

    Parameters
    ----------
    endpoint : str
        The URL to send the telemetry data to.
    telemetry_data : dict
        The telemetry data to send.

    Returns
    -------
    None
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(send_telemetry(endpoint, telemetry_data))


def _run_in_proc(endpoint: str, telemetry_data: dict[str, Any], timeout: float) -> None:
    """
    Handles the creation and running of a separate process for sending telemetry data.
    This function will:
    - Create a new process and run the _run_event_loop function in that process
    - Wait for the process to finish
    - If the process takes longer than the specified timeout, terminate the process
        and raise a warning

    Parameters
    ----------
    endpoint : str
        The URL to send the telemetry data to.
    telemetry_data : dict
        The telemetry data to send.
    timeout : float
        The maximum time to wait for the process to finish.

    Returns
    -------
    None

    """
    proc = Process(target=_run_event_loop, args=(endpoint, telemetry_data))
    proc.start()
    proc.join(timeout)
    if proc.is_alive():
        proc.terminate()
        warnings.warn(
            f"Telemetry data not sent within {timeout} seconds",
            category=RuntimeWarning,
            stacklevel=2,
        )
    return None
