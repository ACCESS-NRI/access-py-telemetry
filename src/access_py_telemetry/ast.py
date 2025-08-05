# mypy: disable-error-code=has-type
"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any
import libcst as cst
from ast import literal_eval, unparse
from libcst._exceptions import ParserSyntaxError
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


def extract_call_args_kwargs(
    node: cst.Call, user_ns: dict[str, Any]
) -> tuple[list[Any], dict[str, Any]]:
    """
    Take a cst Call Node and extract the args and kwargs, into a tuple of (args, kwargs)

    # TODO: This matcher is a mess
    - Add support for f-strings
    """
    args: list[str | dict[str, Any]] = []
    kwargs: dict[str, Any] = {}

    def _extract_dict_value(dict_node: cst.Dict) -> dict[str, str]:
        """Extract dictionary values from a cst.Dict node using pattern matching"""
        result = {}
        for element in dict_node.elements:
            match element:
                case cst.DictElement(
                    key=cst.SimpleString(value=key_val),
                    value=cst.SimpleString(value=val),
                ):
                    key = key_val.strip("'\"")
                    value = val.strip("'\"")
                    result[key] = value
                case cst.DictElement(
                    key=cst.SimpleString(value=key_val),
                    value=cst.Integer(value=val) | cst.Float(value=val),
                ):
                    key = key_val.strip("'\"")
                    result[key] = val
                case cst.DictElement(
                    key=cst.SimpleString(value=key_val), value=cst.Name(value=val)
                ):
                    key = key_val.strip("'\"")
                    value = user_ns.get(val, val)
                    result[key] = value
                case cst.DictElement(
                    key=cst.Name(value=key_val), value=cst.SimpleString(value=val)
                ):
                    key = user_ns.get(key_val, key_val)
                    value = val.strip("'\"")
                    result[key] = value
                case cst.DictElement(
                    key=cst.Name(value=key_val),
                    value=cst.Integer(value=val) | cst.Float(value=val),
                ):
                    key = user_ns.get(key_val, key_val)
                    result[key] = val
                case cst.DictElement(
                    key=cst.Name(value=key_val), value=cst.Name(value=val)
                ):
                    key = user_ns.get(key_val, key_val)
                    value = user_ns.get(val, val)
                    result[key] = value
                case _:
                    # Skip unsupported dict element types
                    continue
        return result

    for arg in node.args:
        match arg:
            case cst.Arg(
                value=cst.SimpleString(value=val)
                | cst.Integer(value=val)
                | cst.Float(value=val),
                keyword=None,
            ):
                args.append(val)
            case cst.Arg(
                value=cst.Name(value=val),
                keyword=None,
            ):
                if val := user_ns.get(val, None):
                    args.append(val)
            case cst.Arg(
                value=cst.Dict() as dict_node,
                keyword=None,
            ):
                # Dictionary as positional argument
                dict_value = _extract_dict_value(dict_node)
                args.append(dict_value)
            case cst.Arg(
                value=cst.SimpleString(value=val)
                | cst.Float(value=val)
                | cst.Integer(value=val),
                keyword=cst.Name(value=key),
            ):
                kwargs[key] = val
            case cst.Arg(
                value=cst.SimpleString(value=val)
                | cst.Float(value=val)
                | cst.Integer(value=val),
                keyword=cst.Name(value=key),
            ):
                kwargs[key] = val
            case cst.Arg(
                cst.Name(value=val),
                keyword=cst.Name(value=key),
            ):
                if val := user_ns.get(val, None):  # type: ignore[arg-type]
                    kwargs[key] = val
            case cst.Arg(
                value=cst.Dict() as dict_node,
                keyword=cst.Name(value=key),
            ):
                # Dictionary as keyword argument
                dict_value = _extract_dict_value(dict_node)
                kwargs[key] = dict_value
            case _:
                return args, kwargs

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

    def visit_Attribute(self, node: cst.Attribute) -> None:
        parent = self.get_metadata(cst.metadata.ParentNodeProvider, node)
        full_name = self._get_full_name(node)
        match full_name, parent:
            case str(), cst.Call():
                return None
            case str(), _:
                self._process_api_call(full_name, [], {})
            case _, _:
                pass
        return None

    def visit_Call(self, node: cst.Call) -> None:
        """
        Visit a call nodde, process it if it's a registered call
        """
        match node:
            case cst.Call(
                func=cst.Name(
                    value=full_name,
                )
            ):
                args, kwargs = extract_call_args_kwargs(node, self.user_namespace)
                self._process_api_call(full_name, args, kwargs)
            case cst.Call(
                func=cst.Attribute(
                    value=cst.Name(value=base_name),
                    attr=cst.Name(
                        value=attr_name,
                    ),
                )
            ):
                args, kwargs = extract_call_args_kwargs(node, self.user_namespace)
                full_name = f"{base_name}.{attr_name}"
                self._process_api_call(full_name, args, kwargs)
            case cst.Call(func=cst.Attribute() as attr_node):
                if full_name := self._get_full_name(attr_node):
                    # If we have a full name, we can process the call
                    args, kwargs = extract_call_args_kwargs(node, self.user_namespace)
                    self._process_api_call(full_name, args, kwargs)
            case _:
                return None

    def safe_eval(self, node: cst.CSTNode) -> Any:
        """Try to evaluate a node, or return the unparsed node if that fails."""
        if not hasattr(node, "value"):
            return unparse(node)  # type: ignore[arg-type]

        try:
            return literal_eval(node.value.value)
        except (ValueError, SyntaxError):
            return unparse(node.value.value)

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

    def _get_full_name(self, node: cst.CSTNode) -> str:
        """Recursively get the full name of a function or method call."""
        return _get_full_name(node)


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

    def _resolve_type(self, instance_name: str) -> str:
        """
        Resolve the type of an instance by its name.
        If the instance is a module, return its name.
        """
        instance = self.user_namespace.get(instance_name)
        if instance is None:
            return instance_name
        type_name = type(instance).__name__
        if type_name == "module":
            type_name = getattr(instance, "__name__", instance_name)
        return type_name

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        """
        When we leave an attribute node, if it's parent is a cst.Name (ie. the
        root of a chain of attribute accesses), we replace the value of the
        attribute with the type name of the instance.
        """

        match updated_node:
            case cst.Attribute(
                value=cst.Name(
                    value=instance_name,
                ),
                attr=cst.Name(value=_),
            ) if (type_name := self._resolve_type(instance_name)) not in [None, "type"]:
                return updated_node.with_changes(value=cst.Name(type_name))
            case cst.Attribute(
                value=cst.Call(
                    func=cst.Name(
                        value=_maybe_class_name,
                    ),
                )
            ) if (
                type(self.user_namespace.get(_maybe_class_name, None)) is type
            ):
                return updated_node.with_changes(value=cst.Name(_maybe_class_name))

            case _:
                return updated_node

    def leave_Subscript(
        self, original_node: cst.Subscript, updated_node: cst.Subscript
    ) -> cst.Call:
        """
        When we leave a subscript node, replace eg. `instance[key]` with `ClassName.__getitem__(key)`.
        This means we can !!get rid of !! the visist_Subscript method in CallListener!
        """
        match updated_node:
            case cst.Subscript(  # String index
                value=cst.Name(value=instance_name),
                slice=[
                    cst.SubscriptElement(
                        slice=cst.Index(value=cst.SimpleString(value=args))
                    )
                ],
            ) if (type_name := self._resolve_type(instance_name)) is not None:
                return cst.Call(
                    func=cst.Attribute(
                        value=cst.Name(type_name),
                        attr=cst.Name("__getitem__"),
                    ),
                    args=[
                        cst.Arg(value=cst.SimpleString(value=args)),
                    ],
                )
            case cst.Subscript(  # Integer index
                value=cst.Name(value=instance_name),
                slice=[
                    cst.SubscriptElement(slice=cst.Index(value=cst.Integer(value=args)))
                ],
            ) if (type_name := self._resolve_type(instance_name)) is not None:
                return cst.Call(
                    func=cst.Attribute(
                        value=cst.Name(type_name),
                        attr=cst.Name("__getitem__"),
                    ),
                    args=[
                        cst.Arg(value=cst.Integer(value=args)),
                    ],
                )
            case cst.Subscript(  # Variable index
                value=cst.Name(value=instance_name),
                slice=[
                    cst.SubscriptElement(slice=cst.Index(value=cst.Name(value=args)))
                ],
            ) if (type_name := self._resolve_type(instance_name)) is not None:
                res_args: int | float | str | object = self.user_namespace.get(
                    args, args
                )
                if isinstance(res_args, int):
                    mval: cst.BaseExpression = cst.Integer(value=f"{res_args}")
                elif isinstance(res_args, float):
                    mval = cst.Float(value=f"{res_args}")
                else:
                    mval = cst.SimpleString(value=f"'{res_args}'")
                return cst.Call(
                    func=cst.Attribute(
                        value=cst.Name(type_name),
                        attr=cst.Name("__getitem__"),
                    ),
                    args=[
                        cst.Arg(
                            value=mval
                        ),  # TODO: so we can put the right value in here
                    ],
                )
            case _:
                raise AssertionError(
                    "Subscript node does not match expected pattern. "
                    "This should not happen, please report this as a bug."
                )

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.Call | cst.Name:
        # Use matcher to identify the pattern: any_method(search_call(...))

        match updated_node:
            case cst.Call(
                func=cst.Name(
                    value=func_name,
                )
            ) if (instance := self.user_namespace.get(func_name, None)) is not None:
                func_name = (
                    instance.__name__
                )  # Dealias if we've renamed it something else
                return updated_node.with_changes(func=cst.Name(func_name))
            case cst.Call(
                func=cst.Attribute(
                    value=cst.Name(value=base_name),
                    attr=cst.Name(
                        value=attr_name,
                    ),
                )
            ):  # TODO: check that we return self here or don't do anything
                args, kwargs = extract_call_args_kwargs(
                    updated_node, self.user_namespace
                )
                full_name = f"{base_name}.{attr_name}"
                self._process_api_call(full_name, args, kwargs)
                # Then pop that attribute access out of the chain
                return cst.Name(
                    value=base_name,
                )
            case _:
                pass

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

    def _get_full_name(self, node: cst.CSTNode) -> str:
        """Recursively get the full name of a function or method call."""
        return _get_full_name(node)


def _get_full_name(node: cst.CSTNode) -> str:
    """Recursively get the full name of a function or method call."""
    match node:
        case cst.Attribute(
            value=base_name,
            attr=cst.Name(value=attr_name),
        ):
            # If the node is an attribute, we need to repeat to get the full name
            return f"{_get_full_name(base_name)}.{attr_name}"
        case cst.Name(value=name):
            # If the node is a name, we return the name
            assert isinstance(name, str), "Name node should have a string value"
            return name
        case _:
            raise AssertionError(
                "Node does not match expected pattern. "
                "This should not happen, please report this as a bug."
            )
