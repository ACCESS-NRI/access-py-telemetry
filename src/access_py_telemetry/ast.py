"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any
import ast
from IPython.core.getipython import get_ipython
from IPython.core.interactiveshell import ExecutionInfo

from .api import ApiHandler
from .registry import TelemetryRegister
from .utils import REGISTRIES


api_handler = ApiHandler()

registries = {registry: TelemetryRegister(registry) for registry in REGISTRIES.keys()}


def capture_registered_calls(info: ExecutionInfo) -> None:
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
        func_name = ""
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

            for registry, registered_funcs in registries.items():
                if func_name in registered_funcs:
                    args = [ast.dump(arg) for arg in node.args]
                    kwargs = {
                        kw.arg: ast.literal_eval(kw.value)
                        for kw in node.keywords
                        if kw.arg is not None  # Redundant check to make mypy happy
                    }
                    api_handler.send_api_request(
                        registry,
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

            for registry, registered_funcs in registries.items():
                if func_name in registry:
                    api_handler.send_api_request(
                        registry, func_name, args=[index], kwargs={}
                    )
    return None
