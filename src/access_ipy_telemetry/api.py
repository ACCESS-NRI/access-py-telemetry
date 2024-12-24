"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any, Type, TypeVar
import warnings
import os
import datetime
import hashlib
import httpx
import asyncio
import pydantic
import yaml

S = TypeVar("S", bound="SessionID")
H = TypeVar("H", bound="ApiHandler")

with open("registries.yaml", "r") as f:
    REGISTRIES = yaml.safe_load(f)

ENDPOINTS = {registry: registry.get("endpoint") for registry in REGISTRIES}


class ApiHandler:
    """
    Singleton class to handle API requests. I'm only using a class here so we can save
    the extra_fields attribute.

    Singleton so that we can add extra fields elsewhere in the code and have them
    persist across all telemetry calls.
    """

    _instance = None

    def __new__(cls: Type[H]) -> H:
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
    ) -> None:
        if hasattr(self, "initialized"):
            return None
        self._server_url = "https://tracking-services-d6c2fd311c12.herokuapp.com"
        self.endpoints = ENDPOINTS
        self._extra_fields: dict[str, dict[str, Any]] = {
            ep_name: {} for ep_name in self.endpoints.keys()
        }

    @property
    def extra_fields(self) -> dict[str, Any]:
        return self._extra_fields

    @extra_fields.setter
    @pydantic.validate_call
    def extra_fields(self, fields: dict[str, dict[str, Any]]) -> None:
        self._extra_fields = fields
        return None

    @pydantic.validate_call
    def add_extra_field(self, service_name: str, field: dict[str, Any]) -> None:
        """
        Add an extra field to the telemetry data. Only works for endpoints that
        are already defined.
        """
        if service_name not in self.endpoints:
            raise KeyError(f"Endpoint '{service_name}' not found")
        self._extra_fields[service_name] = field
        return None

    @property
    def server_url(self) -> str:
        return self._server_url

    @server_url.setter
    def server_url(self, url: str) -> None:
        self._server_url = url
        return None

    def send_api_request(
        self,
        service_name: str,
        function_name: str,
        args: list[Any],
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
        extra_fields : dict, optional
            Additional fields to include in the telemetry data, by default None.
            Useful for including additional context information - for example, catalog
            version if using this with the ACCESS-NRI Intake Catalog.

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
            **self.extra_fields[service_name],
        }

        self._last_post = telemetry_data

        try:
            endpoint = self.endpoints[service_name]
        except KeyError as e:
            raise KeyError(
                f"Endpoint for '{service_name}' not found in {self.endpoints}"
            ) from e

        endpoint = f"{self.server_url}{endpoint}"

        async def send_telemetry(data: dict[str, Any]) -> None:
            headers = {"Content-Type": "application/json"}
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        service_name, json=data, headers=headers
                    )
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
        login = os.getlogin()
        timestamp = datetime.datetime.now().isoformat()
        session_str = f"{login}_{timestamp}"
        session_id = hashlib.sha256((session_str).encode()).hexdigest()
        return session_id
