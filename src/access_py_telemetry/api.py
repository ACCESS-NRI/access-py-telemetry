"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from functools import wraps
import sys
from typing import Any, Type, Iterable, Callable
import warnings
import platform
import uuid
import httpx
import asyncio
import pydantic
import re
import yaml
import multiprocessing
from pathlib import Path, PurePosixPath
import logging

from .utils import ENDPOINTS

logging.getLogger("httpx").setLevel(logging.WARNING)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

with open(Path(__file__).parent / "config.yaml", "r") as f:
    config = yaml.safe_load(f)

NRI_USER = True


class ProductionToggle:
    """
    Singleton class to hold info about whether the code is running in production
    or not.

    This class is a singleton so that the production status can be set once and
    accessed from anywhere in the code.

    Exposed functionality:
    - production: bool
        Whether the code is running in production or not. Setting this will also
        set the server URL to the production or staging URL.
    - debug: Callable
        A decorator that wraps a function in a try/except block. If the code is
        running in production, the function will be called normally. If the code
        is not running in production, the function will be called and any
        exceptions will be ignored. This is useful for debugging purposes.

    """

    _production = True
    _instance = None

    PRODUCTION_URL = "https://reporting.access-nri-store.cloud.edu.au/api/"
    STAGING_URL = "https://reporting-dev.access-nri-store.cloud.edu.au/api/"

    def __new__(cls: Type[Self]) -> Self:
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "initialized"):
            return None
        self.initialized = True

    @property
    def production(self) -> bool:
        return self._production

    @production.setter
    def production(self, prod: bool) -> None:
        """
        Set the production status.
        """
        if not isinstance(prod, bool):
            raise TypeError("Production status must be a boolean")
        if prod:
            ApiHandler().server_url = self.PRODUCTION_URL
        else:
            ApiHandler().server_url = self.STAGING_URL
        self._production = prod
        return None

    def debug(self) -> Callable[..., Any]:
        """
        Debugging decorator. Applying this to a function will wrap all telemetry
        calls in try/except blocks so that users never see any exceptions from
        the telemetry code.

        Notes
        -----
        We have to apply the branching logic *within* the decorator, because
        otherwise the logic gets applied at initialization time, and we can't
        change the production status after that.
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if self.production:
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            return func(*args, **kwargs)
                    except Exception:
                        return None
                else:
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def __str__(self) -> str:
        return f"ProductionToggle(production={self._production})"

    def __repr__(self) -> str:
        return f"ProductionToggle(production={self._production})"


TOGGLE = ProductionToggle()


class ApiHandler:
    """
    Singleton class to handle API requests. I'm only using a class here so we can save
    the extra_fields attribute.

    Singleton so that we can add extra fields elsewhere in the code and have them
    persist across all telemetry calls.

    To configure request timeouts and the multiprocessing context manually, configure
    the _request_timeout and _mproc_override class attributes as desired.
    """

    _instance = None
    endpoints = {service: endpoint for service, endpoint in ENDPOINTS.items()}
    headers: dict[str, dict[str, str]] = {service: {} for service in ENDPOINTS}
    _extra_fields: dict[str, dict[str, Any]] = {ep_name: {} for ep_name in ENDPOINTS}
    _pop_fields: dict[str, list[str]] = {}
    _request_timeout = None
    _mproc_override = None

    def __new__(cls: Type[Self], *args: Any, **kwargs: Any) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        server_url: str = "https://reporting.access-nri-store.cloud.edu.au",
    ) -> None:
        if hasattr(self, "_initialized"):
            return None
        self._initialized = True
        self._server_url = server_url

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

    @pydantic.validate_call
    def set_headers(
        self, service_names: str | Iterable[str] | None, headers: dict[str, str]
    ) -> None:
        """
        Add headers to the telemetry request for a given service or services, if
        specified.

        If service_names is None, the headers will be added to all services.
        """
        if isinstance(service_names, str):
            service_names = [service_names]

        for service_name in service_names or self.endpoints:
            if service_name not in self.endpoints:
                raise KeyError(f"Endpoint for '{service_name}' not found")
            self.headers[service_name] = headers
        return None

    @pydantic.validate_call
    def clear_headers(self, service_names: str | Iterable[str] | None = None) -> None:
        """
        Clear the headers for a given service or services, if specified.

        If service_names is None, the headers will be cleared for all services.
        """
        if isinstance(service_names, str):
            service_names = [service_names]

        for service_name in service_names or self.endpoints:
            if service_name not in self.endpoints:
                raise KeyError(f"Endpoint for '{service_name}' not found")
            self.headers[service_name] = {}
        return None

    @property
    def server_url(self) -> str:
        return self._server_url

    @server_url.setter
    def server_url(self, url: str) -> None:
        """
        Set the server URL for the telemetry API.
        """
        if NRI_USER and (
            "https://reporting-dev.access-nri-store.cloud.edu.au/" not in url
            and "https://reporting.access-nri-store.cloud.edu.au/" not in url
        ):
            warnings.warn(
                "Server URL not an ACCESS-NRI Reporting API URL",
                stacklevel=2,
                category=UserWarning,
            )
        if NRI_USER and not url.lower().endswith(("api", "api/")):
            warnings.warn(
                "Server URL does not end with 'api' or 'api/' - this is likely an error",
                stacklevel=2,
                category=UserWarning,
            )
        self._server_url = url
        return None

    @property
    def pop_fields(self) -> dict[str, list[str]]:
        return self._pop_fields

    @property
    def request_timeout(self) -> float | None:
        return self._request_timeout

    @request_timeout.setter
    def request_timeout(self, timeout: float | None) -> None:
        """
        Set the request timeout for the telemetry API.
        """
        if timeout is None:
            self._request_timeout = None
            return None
        if not isinstance(timeout, (int, float)):
            raise TypeError("Timeout must be a number")
        elif timeout <= 0 or not isinstance(timeout, (int, float)):
            raise ValueError("Timeout must be a positive number")

        self._request_timeout = timeout
        return None

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

    @TOGGLE.debug()
    def send_api_request(
        self,
        service_name: str,
        function_name: str,
        args: list[Any] | tuple[Any, ...],
        kwargs: dict[str, str | Any],
    ) -> None:
        """
        Send an API request with telemetry data.

        Parameters
        ----------
        service_name : str
            The name of the service to send the telemetry data to.
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

        endpoint = self._get_endpoints(service_name)

        telemetry_headers = self.headers.get(service_name, {})

        endpoint = _format_endpoint(self.server_url, endpoint)

        send_in_loop(
            endpoint,
            telemetry_data,
            telemetry_headers,
            self._request_timeout,
            self._mproc_override,
        )
        return None

    def _get_endpoints(self, service_name: str) -> str:
        """
        Get the endpoint for a given service name.
        """
        try:
            endpoint = self.endpoints[service_name]
        except KeyError as e:
            raise KeyError(
                f"Endpoint for '{service_name}' not found in {self.endpoints}"
            ) from e
        return endpoint

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
            # "name": getpass.getuser(), # Until we work out the privacy policy nightmare
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
    The session ID is created using using the UUID4 algorithm.

    Methods:
        __new__(cls, *args, **kwargs): Ensures only one instance of the class is created.
        __init__(self): Initializes the instance.
        __get__(self, obj: object, objtype: type | None = None) -> str: Generates and returns the session ID.
        create_session_id() -> str: Static method to create a unique session ID.
    """

    _instance = None

    def __new__(cls: type[Self]) -> Self:
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
        """
        Generate a unique session ID.
        """
        return str(uuid.uuid4())


async def send_telemetry(
    endpoint: str,
    data: dict[str, Any],
    headers: dict[str, str],
    warn: bool | None = None,
) -> None:
    """
    Asynchronously send telemetry data to the specified endpoint.

    Parameters
    ----------
    endpoint : str
        The URL to send the telemetry data to.
    data : dict
        The telemetry data to send.
    headers : dict
        The headers to send the telemetry data with.
    warn : bool, optional
        If True, a warning will be raised if the request fails. If False, no
        warning will be raised. If None, warn will default the value of
        ` not ProductionToggle().production`. It wil also enable some status info
        about the request being sent.

    Returns
    -------
    None

    Warnings
    --------
    RuntimeWarning
        If the request fails.
    """
    if warn is None:
        warn = not ProductionToggle().production

    headers = {
        "Content-Type": "application/json",
        **headers,
    }
    async with httpx.AsyncClient() as client:
        try:
            if warn:
                print(f"Posting telemetry to {endpoint}")
            response = await client.post(endpoint, json=data, headers=headers)
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if warn:
                warnings.warn(
                    f"Request failed: {e}", category=RuntimeWarning, stacklevel=2
                )
    return None


def send_in_loop(
    endpoint: str,
    telemetry_data: dict[str, Any],
    telemetry_headers: dict[str, str] | None = None,
    timeout: float | None = None,
    mproc_override: str | None = None,
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
    headers : dict, optional
        The headers to send the telemetry data with.
    timeout : float, optional
        The maximum time to wait for the coroutine to finish. If the coroutine takes
        longer than this time, a TimeoutError will be raised. If None, the coroutine
        will terminate after 60 seconds. Timeout will also revert to 60 seconds if
        set to 0.
    mproc_override : str, optional
        The multiprocessing context to use. If None, the context will be set to "fork"
        on Linux systems and "spawn" on Windows/ MacOS systems. If a context is specified,
        it will be used regardless of the system.

    Returns
    -------
    None

    """
    timeout = timeout or 60

    telemetry_headers = telemetry_headers or {}

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _run_in_proc(
            endpoint, telemetry_data, telemetry_headers, timeout, mproc_override
        )
    else:
        loop.create_task(send_telemetry(endpoint, telemetry_data, telemetry_headers))
        return None


def _run_event_loop(
    endpoint: str,
    telemetry_data: dict[str, Any],
    telemetry_headers: dict[str, str] | None = None,
    warn: bool | None = None,
) -> None:
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
    telemetry_headers : dict, optional
        The headers to send the telemetry data with.
    warn : bool, optional
        If True, a warning will be raised if the request fails. If False, no
        warning will be raised. If None, warn will default the value of
        ` not ProductionToggle().production`. It will also enable some status info
        about the request being sent.

    Returns
    -------
    None

    Notes
    -----
    We pass through warn here as otherwise ProductionToggle() will be initialized
    in the main process, and we want to avoid that.
    """
    if warn is None:
        warn = not ProductionToggle().production
    telemetry_headers = telemetry_headers or {}
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
        send_telemetry(endpoint, telemetry_data, telemetry_headers, warn)
    )


def _run_in_proc(
    endpoint: str,
    telemetry_data: dict[str, Any],
    telemetry_headers: dict[str, str] | None,
    timeout: float = 60,
    mproc_override: str | None = None,
) -> None:
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
    telemetry_headers : dict, optional
        The headers to send the telemetry data with.
    mproc_override : str, optional
        The multiprocessing context to use. If None, the context will be set to "fork"
        on Linux systems and "spawn" on Windows systems. If a context is specified, it
        will be used regardless of the system.

    Returns
    -------
    None

    """
    telemetry_headers = telemetry_headers or {}

    if not mproc_override:
        ctx_type = "fork" if platform.system().lower() == "linux" else "spawn"
    else:
        ctx_type = mproc_override

    # Mypy gets upset below because it doesn't know we wont use "fork" on Windows
    proc = multiprocessing.get_context(ctx_type).Process(  # type: ignore
        target=_run_event_loop,
        args=(endpoint, telemetry_data, telemetry_headers),
    )
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


def _format_endpoint(server_url: str, endpoint: str) -> str:
    """
    Concatenates the server URL and endpoint, ensuring that there is only one
    slash between them.
    """
    endpoint = str(PurePosixPath(server_url) / endpoint.lstrip("/"))
    return re.sub(r"^(https?:/)(.*?)(?<!/)\/?$", r"\1/\2/", endpoint)
