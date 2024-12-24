"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any, Type, TypeVar, Iterator, Callable
import pydantic
import yaml

T = TypeVar("T", bound="TelemetryRegister")

with open("registries.yaml", "r") as f:
    REGISTRIES = yaml.safe_load(f)

REGISTRIES = {registry: registry.get("items") for registry in REGISTRIES}


REGISTRIES = {
    "catalog": {
        "esm_datastore.search",
        "DfFileCatalog.search",
        "DfFileCatalog.__getitem__",
    }
}


class RegisterWarning(UserWarning):
    """
    Custom warning class for the TelemetryRegister class.
    """

    pass


class TelemetryRegister:
    """
    Singleton class to register functions for telemetry. Like the session handler,
    this class is going to be a singleton so that we can register functions to it
    from anywhere and have them persist across all telemetry calls.

    This doesn't actually work - we are going to need one registry per service, so
    we can't use a singleton here. We'll need to refactor this later.
    """

    # Set of registered functions for now - we can add more later or dynamically
    # using the register method.

    _instances: dict[str, "TelemetryRegister"] = {}

    def __new__(cls: Type[T], service: str) -> T:
        if cls._instances.get(service) is None:
            cls._instances[service] = super().__new__(cls)
        return cls._instances[service]  # type: ignore

    def __init__(self, service: str) -> None:
        if hasattr(self, "_initialized"):
            return None
        self._initialized = True
        self.service = service
        self.registry = REGISTRIES.get(service, set())

    def __str__(self) -> str:
        return str(list(self.registry))

    def __repr__(self) -> str:
        return f"TelemetryRegister({self.service})"

    def __contains__(self, function_name: str) -> bool:
        return function_name in self.registry

    def __iter__(self) -> Iterator[str]:
        return iter(self.registry)

    @pydantic.validate_call
    def register(self, *func_names: str) -> None:
        """
        Register functions to the telemetry register.


        Parameters
        ----------
        functions : Sequence[str]
            The name of the function to register. Can also be a list of function names.

        Returns
        -------
        None
        """

        for func in func_names:
            self.registry.add(func)
        return None

    @pydantic.validate_call
    def deregister(self, *func_names: str) -> None:
        """
        Deregister a function from the telemetry register.

        Parameters
        ----------
        function_name : str
            The name of the function to deregister. Can also be a list of function names.

        Returns
        -------
        None
        """
        for func in func_names:
            self.registry.remove(func)
        return None


def access_telemetry_register(
    func: Callable[..., Any], service: str
) -> Callable[..., Any]:
    """
    Decorator to register a function in the specified service

    Parameters
    ----------
    func : Callable
        The function to register.
    register : TelemetryRegister
        The telemetry register to use.

    Returns
    -------
    Callable
        The function with the telemetry decorator.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        telemetry_register = TelemetryRegister(service)
        telemetry_register.register(func.__name__)
        return func(*args, **kwargs)

    return wrapper
