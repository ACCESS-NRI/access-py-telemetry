from typing import Callable, Any, Iterable
from .registry import TelemetryRegister
from functools import wraps
import httpx
import warnings
import asyncio
from pathlib import Path

from .api import SERVER_URL, ApiHandler


def ipy_register_func(
    func: Callable[..., Any],
    service: str,
    extra_fields: Iterable[dict[str, Any]] | None = None,
) -> Callable[..., Any]:
    """
    Decorator to register a function in the specified service and track usage
    using IPython events. This hides a lot of complexity which is more visible in
    the `register_func` decorator.

    Parameters
    ----------
    func : Callable
        The function to register.
    service : str
        The name of the telemetry register to use.
    extra fields : Iterable[dict[str, Any]], optional
        Extra fields to add to the telemetry record. These can also be added after
        the fact using the `add_extra_field` method.

    Returns
    -------
    Callable
        The function with the telemetry decorator.
    """

    api_handler = ApiHandler()

    extra_fields = extra_fields or []
    for field in extra_fields:
        api_handler.add_extra_field(service, field)

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        telemetry_register = TelemetryRegister(service)
        telemetry_register.register(func.__name__)
        return func(*args, **kwargs)

    return wrapper


def register_func(
    func: Callable[..., Any],
    service: str,
    extra_fields: Iterable[dict[str, Any]] | None = None,
) -> Callable[..., Any]:
    """
    Decorator to register a function in the specified service and track usage
    with async requests.

    Parameters
    ----------
    func : Callable
        The function to register.
    service : str
        The name of the telemetry register to use.
    extra fields : Iterable[dict[str, Any]], optional
        Extra fields to add to the telemetry record. These can also be added after
        the fact using the `add_extra_field` method.

    Returns
    -------
    Callable
        The function with the telemetry decorator.
    """
    api_handler = ApiHandler()

    extra_fields = extra_fields or []
    for field in extra_fields:
        api_handler.add_extra_field(service, field)

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        telemetry_data = api_handler._create_telemetry_record(
            service, func.__name__, args, kwargs
        )

        endpoint = Path(SERVER_URL) / api_handler.endpoints[service]

        async def send_telemetry(data: dict[str, Any]) -> None:
            headers = {"Content-Type": "application/json"}
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(endpoint, json=data, headers=headers)
                    response.raise_for_status()
                except httpx.RequestError as e:
                    warnings.warn(
                        f"Request failed: {e}", category=RuntimeWarning, stacklevel=2
                    )

        # Schedule the telemetry data to be sent in the background
        asyncio.create_task(send_telemetry(telemetry_data))

        # Register the function in the correspondng service register so we can
        # keep track of it
        TelemetryRegister(service).register(func.__name__)

        # Call the original function
        return func(*args, **kwargs)

    return wrapper
