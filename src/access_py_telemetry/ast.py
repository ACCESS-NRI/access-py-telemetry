"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any
import libcst as cst
from ast import literal_eval, unparse
from libcst._exceptions import ParserSyntaxError
import libcst.matchers as m
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
        tree = cst.parse_module(code)
    except (ParserSyntaxError, IndentationError):
        return None

    user_namespace: dict[str, Any] = get_ipython().user_ns  # type: ignore

    try:
        reducer = ChainSimplifier(user_namespace, REGISTRIES, api_handler)
        reduced_tree = tree.visit(reducer)
        visitor = CallListener(user_namespace, REGISTRIES, api_handler)
        reduced_tree.visit(visitor)
        visitor._caught_calls = reducer._caught_calls
    except Exception:
        # Catch all exceptions to avoid breaking the execution
        # of the code being run.
        return None

    return None


def extract_call_args_kwargs(call_node: cst.Call) -> tuple[list[Any], dict[str, Any]]:
    """
    Take a cst Call Node and extract the args and kwargs, into a tuple of (args, kwargs)
    """
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    for arg in call_node.args:
        if arg.keyword is None:
            args.append(arg.value)
        else:
            key = str(arg.keyword.value)
            kwargs[key] = arg.value.value  # type: ignore[attr-defined]
            # ^ Arg.value.value looks stupid, but arg.value is a cst Node itself
            # For catalogs, it's usually a cst.SimpleString or something like that,
            # so we could probably literal eval it?

    return args, kwargs


def format_args(args: list[Any], kwargs: dict[str, Any]) -> str:
    """
    Format args and kwargs into a string representation
    """
    match args, kwargs:
        case ([], {}):
            return ""
        case ([], _):
            return ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        case _, {}:
            return ", ".join([str(arg) for arg in args])
        case _:
            args_str = ", ".join([str(arg) for arg in args])
            kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
            return f"{args_str}, {kwargs_str}"


class CallListener(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (cst.metadata.ParentNodeProvider,)

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

    def _get_full_name(self, node: cst.CSTNode) -> Any | None:
        """Recursively get the full name of a function or method call."""
        if isinstance(node, cst.Attribute):
            return f"{self._get_full_name(node.value)}.{node.attr.value}"
        elif isinstance(node, cst.Name):
            return node.value
        return None

    def safe_eval(self, node: cst.CSTNode) -> Any:
        """Try to evaluate a node, or return the unparsed node if that fails."""
        if not hasattr(node, "value"):
            return unparse(node)  # type: ignore[arg-type]

        try:
            return literal_eval(node.value.value)
        except (ValueError, SyntaxError):
            return unparse(node.value.value)

    def visit_Attribute(self, node: cst.Attribute) -> None:
        if full_name := self._get_full_name(node):
            self._process_api_call(full_name, [], {})

    def visit_Call(self, node: cst.Call) -> None:
        full_name = self._get_full_name(node.func)
        func_name = None
        if full_name:
            parts = full_name.split(".")
            if len(parts) == 1:
                # Regular function call
                func_name = f"{full_name}"
            else:
                # Check if the first part is in the user namespace
                instance = self.user_namespace.get(parts[0])
                if instance is None:
                    return None

        args, kwargs = extract_call_args_kwargs(node)
        if func_name:
            self._process_api_call(func_name, args, kwargs)

    def visit_Subscript(self, node: cst.Subscript) -> None:
        """Handle subscript operations."""
        full_name = self._get_full_name(node.value)  # Get the object being indexed
        func_name = None
        if full_name:
            parts = full_name.split(".")
            instance = self.user_namespace.get(parts[0])
            if instance is None:
                return None

            class_name = type(instance).__name__
            func_name = f"{class_name}.{'.'.join(parts[1:])}__getitem__"

        # This whole if/else chain is a complete mess
        if isinstance(node.slice, cst.Name):
            args = self.user_namespace.get(node.slice.value, None)
        elif isinstance(node.slice[0], cst.SubscriptElement):  # This is a mess
            try:
                args = literal_eval(node.slice[0].slice.value.value)  # type: ignore
            except Exception:
                args = self.user_namespace.get(node.slice[0].slice.value.value, None)  # type: ignore

        if func_name:
            self._process_api_call(func_name, [args], {})

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


class ChainSimplifier(cst.CSTTransformer):
    """
    Transform chained calls by removing intermediate method calls
    Example: ds.search(...).search(...).to_dataset_dict()
    becomes: ds.to_dataset_dict()
    """

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

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        """
        When we leave an attribute node, if it's parent is a cst.Name (ie. the
        root of a chain of attribute accesses), we replace the value of the
        attribute with the type name of the instance.
        """

        if isinstance(updated_node.value, cst.Name):
            instance_name = updated_node.value.value
            instance = self.user_namespace.get(instance_name)

            if instance is not None:
                type_name = type(instance).__name__
                if type_name == "module":
                    type_name = getattr(instance, "__name__", instance_name)

                # Replace the instance name with the type name
                return updated_node.with_changes(value=cst.Name(type_name))
        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        # Use matcher to identify the pattern: any_method(search_call(...))
        search_pattern = m.Call(
            func=m.Attribute(value=m.Call(func=m.Attribute(attr=m.Name("func"))))
        )

        if m.matches(updated_node, search_pattern):
            # Extract the method name and inner call

            inner_call = updated_node.func.value  # type: ignore[attr-defined]

            func_name = inner_call.func.attr.value

            args, kwargs = extract_call_args_kwargs(inner_call)

            self._process_api_call(func_name, args, kwargs)

            # Replace the value with the inner call's value
            # This effectively removes the search() call
            new_func = updated_node.func.with_changes(value=inner_call.func.value)
            return updated_node.with_changes(func=new_func)

        return updated_node

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
