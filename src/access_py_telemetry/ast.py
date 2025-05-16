"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any
import ast
import re
from IPython.core.getipython import get_ipython
from IPython.core.interactiveshell import ExecutionInfo

from .api import ApiHandler
from .registry import TelemetryRegister
from .utils import REGISTRIES


api_handler = ApiHandler()

registries = {registry: TelemetryRegister(registry) for registry in REGISTRIES.keys()}


def strip_magic(code: str) -> str:
    """
    Parse the provided code into an AST (Abstract Syntax Tree).

    Parameters
    ----------

    code : str
        The code to parse.
    Returns
    -------
    str
        The code without IPython magic commands.

    """

    IPYTHON_MAGIC_PATTERN = r"^\s*[%!?]{1,2}|^.*\?{1,2}$"

    code = "\n".join(
        line for line in code.splitlines() if not re.match(IPYTHON_MAGIC_PATTERN, line)
    )

    return code


def capture_registered_calls(info: ExecutionInfo) -> None:
    """
    Use the AST module to parse the code that we are executing & send an API call
    if we detect specific function or method calls.

    Fail silently if we can't parse the code.

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

    code = strip_magic(code)

    try:
        tree = ast.parse(code)
    except (SyntaxError, IndentationError):
        return None

    user_namespace: dict[str, Any] = get_ipython().user_ns  # type: ignore

    try:
        visitor = CallListener(user_namespace, REGISTRIES, api_handler)
        visitor.visit(tree)
    except Exception:
        # Catch all exceptions to avoid breaking the execution
        # of the code being run.
        return None

    return None


class CallListener(ast.NodeVisitor):
    def __init__(
        self,
        user_namespace: dict[str, Any],
        registries: dict[str, set[str]],
        api_handler: ApiHandler,
    ):
        self.user_namespace = user_namespace
        self.registries = registries
        self._caught_calls: set[str] = set()  # Mostly for debugging
        self.api_handler = api_handler

    def _get_full_name(self, node: ast.AST) -> str | None:
        """Recursively get the full name of a function or method call."""
        if isinstance(node, ast.Attribute):
            return f"{self._get_full_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Name):
            return node.id
        return None

    def safe_eval(self, node: ast.AST) -> Any:
        """Try to evaluate a node, or return the unparsed node if that fails."""
        try:
            return ast.literal_eval(node)
        except (ValueError, SyntaxError):
            return ast.unparse(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Handle attribute access."""
        if full_name := self._get_full_name(node):
            self._process_api_call(full_name, [], {})

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Handle function and method calls."""

        # This seems weird but it reverses our order of operations, meaning we
        # catch chained function calls in the order they are called.
        self.generic_visit(node)

        # If we can't resolve a function name, just visit children and return
        if not (func_name := self._resolve_function_name(node)):
            return None

        args = [self.safe_eval(arg) for arg in node.args]
        kwargs = {
            kw.arg: self.safe_eval(kw.value)
            for kw in node.keywords
            if kw.arg is not None
        }

        self._process_api_call(func_name, args, kwargs)

    def _resolve_function_name(self, node: ast.Call) -> str | None:
        """Resolve a function name using various strategies."""
        if not (full_name := self._get_full_name(node.func)):
            return None

        if func_name := self._resolve_bare_function(full_name):
            return func_name

        if func_name := self._resolve_from_namespace(full_name):
            return func_name

        if func_name := self._resolve_inline_instantiation(node):
            return func_name

        # Finally check for chained calls
        if func_name := self._resolve_chained_call(node):
            return func_name

        return None

    def _resolve_bare_function(self, full_name: str) -> str | None:
        """Resolve a simple function name (e.g., 'func')."""
        if "." not in full_name:
            return full_name
        return None

    def _resolve_from_namespace(self, full_name: str) -> str | None:
        """Resolve function from user namespace (e.g., 'instance.method', 'module.func')."""
        parts = full_name.split(".")
        instance = self.user_namespace.get(parts[0])
        if instance is None:
            return None

        class_name = type(instance).__name__
        if class_name != "module":
            return f"{class_name}.{'.'.join(parts[1:])}"
        else:
            return f"{instance.__name__}.{'.'.join(parts[1:])}"

    def _resolve_inline_instantiation(self, node: ast.Call) -> str | None:
        """Resolve direct class instantiation and method call (e.g., 'MyClass().method')."""
        if not (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Name)
        ):
            return None

        class_name = node.func.value.func.id
        method_name = node.func.attr
        return f"{class_name}.{method_name}"

    def _resolve_chained_call(self, node: ast.Call) -> str | None:
        """Resolve chained method calls (e.g., 'obj.method1().method2()')."""
        if not (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Call)
            and not isinstance(node.func.value.func, ast.Name)
        ):
            return None

        inner_call = node.func.value
        inner_func_name = self._get_full_name(inner_call.func)
        if not inner_func_name:
            return None

        inner_parts = inner_func_name.split(".")
        inner_instance = self.user_namespace.get(inner_parts[0])
        if inner_instance is not None:
            class_name = type(inner_instance).__name__
        else:
            class_name = inner_func_name

        method_name = node.func.attr
        return f"{class_name}.{method_name}"

    def _process_api_call(
        self, func_name: str, args: list[Any], kwargs: dict[str, Any]
    ) -> None:
        """Process an API call for a matched function name."""
        for registry, registered_funcs in self.registries.items():
            if func_name in registered_funcs:
                self.api_handler.send_api_request(
                    registry,
                    func_name,
                    args,
                    kwargs,
                )
                self._caught_calls |= {func_name}

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Handle subscript operations."""
        func_name = None

        if full_name := self._get_full_name(node.value):  # Get the object being indexed
            parts = full_name.split(".")
            instance = self.user_namespace.get(parts[0])
            if instance is None:
                return None

            class_name = type(instance).__name__
            func_name = f"{class_name}.{'.'.join(parts[1:])}__getitem__"

        if isinstance(node.slice, ast.Name):
            args = self.user_namespace.get(node.slice.id, None)
        else:
            args = ast.unparse(node.slice)

        if func_name:
            self._process_api_call(func_name, [args], {})

        self.generic_visit(node)
