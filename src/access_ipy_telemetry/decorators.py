from typing import Callable, Any
from .registry import TelemetryRegister


def register_func(func: Callable[..., Any], service: str) -> Callable[..., Any]:
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
