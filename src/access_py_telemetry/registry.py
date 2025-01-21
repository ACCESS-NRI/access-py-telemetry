"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Type, TypeVar, Iterator, Callable, Any
import pydantic
import copy
from .utils import REGISTRIES

T = TypeVar("T", bound="TelemetryRegister")


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
        self.registry = copy.deepcopy(REGISTRIES.get(service, set()))

    def __str__(self) -> str:
        return str(list(self.registry))

    def __repr__(self) -> str:
        """
        I'm going to cheat and just print out the registry for now.
        """
        return self.__str__()

    def __contains__(self, function_name: str) -> bool:
        return function_name in self.registry

    def __iter__(self) -> Iterator[str]:
        return iter(self.registry)

    @pydantic.validate_call
    def register(self, *func_names: str | Callable[..., Any]) -> None:
        """
        Register functions to the telemetry register.


        Parameters
        ----------
        func_names : Sequence[str | Callable]
            The name of the function to register. Can also be a list of function names.
            If you pass a function, it will register the function by name, using
            the __name__ attribute.


        Returns
        -------
        None
        """

        for func in func_names:
            if isinstance(func, str):
                self.registry.add(func)
            else:
                self.registry.add(func.__name__)
        return None

    @pydantic.validate_call
    def deregister(self, *func_names: str | Callable[..., Any]) -> None:
        """
        Deregister a function from the telemetry register.

        Parameters
        ----------
        function_name : str
            The name of the function to deregister. Can also be a list of function names.
            If you pass a function, it will deregister the function by name, using
            the __name__ attribute.

        Returns
        -------
        None
        """
        for func in func_names:
            if isinstance(func, str):
                self.registry.remove(func)
            else:
                self.registry.remove(func.__name__)
        return None
