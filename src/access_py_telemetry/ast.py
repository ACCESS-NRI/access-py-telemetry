# mypy: disable-error-code=has-type
"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0

Detect registered function / method calls in an IPython cell and emit telemetry.

The registry (``config.yaml``) is written in *type-qualified* names
(``esm_datastore.search``, ``DfFileCatalog.__getitem__``) but user source uses
*variables* (``esm_ds.search(...)``). We bridge that gap with a small
**typed transition interpreter**: the abstract domain is our own telemetry node
types (the class-name strings in the registry), registered calls are edges that
emit a :class:`TelemetryEvent` and yield a successor node type, and a binding
environment carries types through assignments. A registered method's successor
defaults to *self*; only type-*changing* edges and the module/factory
*generators* are declared in ``config.yaml`` (see ``utils.GENERATORS`` /
``utils.TYPE_OVERRIDES``).

The interpreter is a pure function of ``(source, registries, user_ns)`` returning
an ordered ``list[TelemetryEvent]``; dispatch to the API is a separate step. The
live namespace is consulted only as a *fallback* when a receiver's type cannot be
resolved from the cell's own source, which is what lets us type objects created in
the same cell (the ``pre_run_cell`` hook fires before the cell has executed).
"""

import ast as _pyast
import re
from collections import ChainMap
from dataclasses import dataclass, field
from typing import Any, Sequence, Union

import libcst as cst
from IPython.core.getipython import get_ipython
from IPython.core.interactiveshell import ExecutionInfo
from libcst._exceptions import ParserSyntaxError

from .api import ApiHandler
from .utils import GENERATORS, REGISTRIES, TYPE_OVERRIDES

api_handler = ApiHandler()


# --------------------------------------------------------------------------- #
# Abstract values — what an expression evaluates to during interpretation.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Node:
    """A modelled *instance* of node type ``type_name`` (a class-name string)."""

    type_name: str


@dataclass(frozen=True)
class ClassRef:
    """A reference to a class ``name``; calling it yields ``Node(name)``."""

    name: str


@dataclass(frozen=True)
class Dotted:
    """A module / attribute dotted path, or a bare callable name (``os.path``)."""

    path: str


class _Unknown:
    """The absorbing ⊤: an un-typeable value. Emits nothing, absorbs every edge."""

    def __repr__(self) -> str:  # pragma: no cover
        return "UNKNOWN"


UNKNOWN = _Unknown()

AbstractValue = Union[Node, ClassRef, Dotted, _Unknown]


@dataclass
class TelemetryEvent:
    """One detected registered call: the qualified name plus its verbatim args."""

    name: str
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)


def strip_magic(code: str) -> str:
    """
    Remove IPython magic commands from a cell so it parses as plain Python.

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
    Parse the executing cell, detect registered calls, and dispatch telemetry.

    Fails silently (routing the raw code to the ``failed-telemetry`` endpoint) if
    we can't parse or interpret the code, so telemetry never breaks a user's cell.

    Parameters
    ----------
    info : IPython.core.interactiveshell.ExecutionInfo
        An object containing information about the code being executed.

    Returns
    -------
    None
    """
    code: str | None = info.raw_cell

    if code is None:
        return None

    code = strip_magic(code)

    try:
        tree = cst.parse_module(code)
    except (ParserSyntaxError, IndentationError):
        api_handler.send_failure_api_request(
            "intake/failed-telemetry", code, "intake/failed-telemetry"
        )
        return None

    try:
        user_namespace: dict[str, Any] = get_ipython().user_ns  # type: ignore
        events = interpret(tree, REGISTRIES, user_namespace)
        _dispatch(events, REGISTRIES)
    except Exception:
        # Catch all exceptions to avoid breaking the execution of the code being
        # run, then post the raw code to the `failed-telemetry` endpoint.
        api_handler.send_failure_api_request(
            "intake/failed-telemetry", tree.code, "intake/failed-telemetry"
        )

    return None


def interpret(
    tree: cst.Module,
    registries: dict[str, set[str]],
    user_ns: dict[str, Any],
) -> list[TelemetryEvent]:
    """
    Interpret a parsed cell into an ordered list of telemetry events.

    A pure function of its inputs: no I/O, no namespace mutation. This is the unit
    the tests drive directly (``source -> events``).

    Parameters
    ----------
    tree : libcst.Module
        The parsed cell.
    registries : dict[str, set[str]]
        Service name -> set of registered qualified names.
    user_ns : dict[str, Any]
        The live namespace, consulted only as a type/value fallback.

    Returns
    -------
    list[TelemetryEvent]
        The detected registered calls, in source (evaluation) order.
    """
    return _Interpreter(registries, user_ns).run(tree)


def _dispatch(events: list[TelemetryEvent], registries: dict[str, set[str]]) -> None:
    """Send each event to every service whose registry contains its name."""
    for event in events:
        for service, registered in registries.items():
            if event.name in registered:
                api_handler.send_api_request(
                    service, event.name, event.args, event.kwargs
                )


class _Interpreter:
    """Forward, evaluation-order walk that resolves receiver types and emits events."""

    def __init__(
        self, registries: dict[str, set[str]], user_ns: dict[str, Any]
    ) -> None:
        self.registered: set[str] = (
            set().union(*registries.values()) if registries else set()
        )
        self.user_ns = user_ns
        # Same-cell literal bindings, layered over the live namespace for arg
        # resolution (extract_call_args_kwargs looks names up in this mapping).
        self._literals: dict[str, Any] = {}
        self.value_env: ChainMap[str, Any] = ChainMap(self._literals, user_ns)
        # Concrete source-derived type bindings. A name absent here falls back to
        # its runtime type in the namespace (see ``_resolve_name``).
        self.type_env: dict[str, AbstractValue] = {}
        self.events: list[TelemetryEvent] = []

    # -- entry ------------------------------------------------------------- #
    def run(self, tree: cst.Module) -> list[TelemetryEvent]:
        self._walk(tree.body)
        return self.events

    # -- statement walk ---------------------------------------------------- #
    def _walk(self, body: Sequence[cst.CSTNode]) -> None:
        for stmt in body:
            self._statement(stmt)

    def _statement(self, stmt: cst.CSTNode) -> None:
        match stmt:
            case cst.SimpleStatementLine(body=small):
                for small_stmt in small:
                    self._small_statement(small_stmt)
            case cst.ClassDef(name=cst.Name(value=name), body=cst.IndentedBlock() as b):
                self.type_env[name] = ClassRef(name)
                self._walk(b.body)
            case cst.FunctionDef(
                name=cst.Name(value=name), body=cst.IndentedBlock() as b
            ):
                # A bare callable ref: calling it emits by its (literal) name.
                self.type_env[name] = Dotted(name)
                self._walk(b.body)
            case cst.If(body=cst.IndentedBlock() as b, orelse=orelse):
                self._walk(b.body)
                self._orelse(orelse)
            case cst.For(body=cst.IndentedBlock() as b, orelse=orelse):
                self._walk(b.body)
                self._orelse(orelse)
            case cst.While(body=cst.IndentedBlock() as b, orelse=orelse):
                self._walk(b.body)
                self._orelse(orelse)
            case cst.With(body=cst.IndentedBlock() as b):
                self._walk(b.body)
            case cst.Try() as node:
                self._walk(node.body.body)
                for handler in node.handlers:
                    self._walk(handler.body.body)
                self._orelse(node.orelse)
                if node.finalbody is not None and isinstance(
                    node.finalbody.body, cst.IndentedBlock
                ):
                    self._walk(node.finalbody.body.body)
            case _:
                pass

    def _orelse(self, orelse: cst.CSTNode | None) -> None:
        match orelse:
            case cst.Else(body=cst.IndentedBlock() as b):
                self._walk(b.body)
            case cst.If():
                self._statement(orelse)
            case cst.Try():
                self._statement(orelse)
            case _:
                pass

    def _small_statement(self, stmt: cst.CSTNode) -> None:
        match stmt:
            case cst.Import(names=names):
                for alias in names:
                    self._bind_import(alias)
            case cst.ImportFrom(names=names) if not isinstance(names, cst.ImportStar):
                for alias in names:
                    self._bind_import_from(alias)
            case cst.Assign(targets=targets, value=value):
                resolved = self._eval(value)
                self._capture_literal(targets, value)
                for target in targets:
                    self._bind_target(target.target, resolved)
            case cst.AnnAssign(target=target, value=value) if value is not None:
                resolved = self._eval(value)
                self._bind_target(target, resolved)
            case cst.Expr(value=value):
                self._eval(value)
            case cst.Return(value=value) if value is not None:
                self._eval(value)
            case _:
                pass

    # -- bindings ---------------------------------------------------------- #
    def _bind_import(self, alias: cst.ImportAlias) -> None:
        module = _dotted_name(alias.name)
        if module is None:
            return
        if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
            self.type_env[alias.asname.name.value] = Dotted(module)
        else:
            # `import a.b.c` binds the top-level name `a`.
            self.type_env[module.split(".")[0]] = Dotted(module.split(".")[0])

    def _bind_import_from(self, alias: cst.ImportAlias) -> None:
        name = _dotted_name(alias.name)
        if name is None:
            return
        if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
            self.type_env[alias.asname.name.value] = Dotted(name)
        else:
            self.type_env[name] = Dotted(name)

    def _bind_target(self, target: cst.CSTNode, value: AbstractValue) -> None:
        if not isinstance(target, cst.Name):
            return
        if isinstance(value, _Unknown):
            # Don't clobber a namespace-derived type with an un-typeable RHS; drop
            # the source binding so `_resolve_name` falls back to the namespace.
            self.type_env.pop(target.value, None)
        else:
            self.type_env[target.value] = value

    def _capture_literal(
        self, targets: Sequence[cst.AssignTarget], value: cst.BaseExpression
    ) -> None:
        """Record a same-cell literal binding for later arg resolution."""
        literal = _literal_value(value)
        if literal is _NO_LITERAL:
            return
        for target in targets:
            if isinstance(target.target, cst.Name):
                self._literals[target.target.value] = literal

    # -- expression evaluation -------------------------------------------- #
    def _eval(self, node: cst.BaseExpression) -> AbstractValue:
        match node:
            case cst.Name(value=name):
                return self._resolve_name(name)
            case cst.Attribute(value=base, attr=cst.Name(value=attr)):
                return self._attribute(self._eval(base), attr, emit=True)
            case cst.Call():
                return self._call(node)
            case cst.Subscript():
                return self._subscript(node)
            case cst.List():
                return Node("list")
            case cst.Tuple():
                return Node("tuple")
            case cst.Dict():
                return Node("dict")
            case cst.Set():
                return Node("set")
            case _:
                return UNKNOWN

    def _resolve_name(self, name: str) -> AbstractValue:
        if name in self.type_env:
            return self.type_env[name]
        if name in self.user_ns:
            return _abstract_from_obj(self.user_ns[name])
        return UNKNOWN

    def _attribute(
        self, base: AbstractValue, attr: str, *, emit: bool
    ) -> AbstractValue:
        """Attribute access ``base.attr``. Emits (when ``emit``) if registered."""
        match base:
            case Node(type_name=tname) | ClassRef(name=tname):
                qualname = f"{tname}.{attr}"
                if emit:
                    self._maybe_emit(qualname, [], {})
                return self._method_successor(tname, attr)
            case Dotted(path=path):
                newpath = f"{path}.{attr}"
                if emit:
                    self._maybe_emit(newpath, [], {})
                if newpath in GENERATORS:
                    return Node(GENERATORS[newpath])
                return Dotted(newpath)
            case _:
                return UNKNOWN

    def _call(self, node: cst.Call) -> AbstractValue:
        # Evaluate arguments first, for side-effect emits from nested calls.
        for arg in node.args:
            self._eval(arg.value)

        match node.func:
            case cst.Attribute(value=base, attr=cst.Name(value=attr)):
                receiver = self._eval(base)
                return self._call_method(receiver, attr, node)
            case cst.Name(value=name):
                return self._call_name(name, node)
            case _:
                self._eval(node.func)
                return UNKNOWN

    def _call_name(self, name: str, node: cst.Call) -> AbstractValue:
        callee = self._resolve_name(name)
        match callee:
            case ClassRef(name=cls):
                # Constructor: `MyClass(...)` -> Node("MyClass").
                self._maybe_emit_call(cls, node)
                return Node(cls)
            case Dotted(path=path):
                self._maybe_emit_call(path, node)
                if path in GENERATORS:
                    return Node(GENERATORS[path])
                return UNKNOWN
            case _:
                # Fall back to the literal name (matches bare-function detection).
                self._maybe_emit_call(name, node)
                if name in GENERATORS:
                    return Node(GENERATORS[name])
                return UNKNOWN

    def _call_method(
        self, receiver: AbstractValue, attr: str, node: cst.Call
    ) -> AbstractValue:
        match receiver:
            case Node(type_name=tname) | ClassRef(name=tname):
                self._maybe_emit_call(f"{tname}.{attr}", node)
                return self._method_successor(tname, attr)
            case Dotted(path=path):
                self._maybe_emit_call(f"{path}.{attr}", node)
                return UNKNOWN
            case _:
                return UNKNOWN

    def _subscript(self, node: cst.Subscript) -> AbstractValue:
        base = self._eval(node.value)
        tname: str | None = None
        match base:
            case Node(type_name=name) | ClassRef(name=name):
                tname = name
            case _:
                tname = None
        if tname is None:
            return UNKNOWN

        args = self._subscript_args(node)
        self._maybe_emit(f"{tname}.__getitem__", args, {})
        return self._method_successor(tname, "__getitem__")

    # -- transition table -------------------------------------------------- #
    def _method_successor(self, type_name: str, method: str) -> AbstractValue:
        """Successor node type of ``type_name.method`` (default: self)."""
        override = TYPE_OVERRIDES.get(type_name, {}).get(method)
        if override is not None:
            return Node(override)
        if f"{type_name}.{method}" in self.registered:
            return Node(type_name)  # default: returns self
        return UNKNOWN

    # -- emission ---------------------------------------------------------- #
    def _maybe_emit(
        self, qualname: str, args: list[Any], kwargs: dict[str, Any]
    ) -> None:
        if qualname in self.registered:
            self.events.append(TelemetryEvent(qualname, args, kwargs))

    def _maybe_emit_call(self, qualname: str, node: cst.Call) -> None:
        if qualname in self.registered:
            args, kwargs = extract_call_args_kwargs(node, self.value_env)
            self.events.append(TelemetryEvent(qualname, args, kwargs))

    def _subscript_args(self, node: cst.Subscript) -> list[Any]:
        if len(node.slice) != 1:
            return []
        index = node.slice[0].slice
        if not isinstance(index, cst.Index):
            return []
        match index.value:
            case (
                cst.SimpleString(value=val)
                | cst.Integer(value=val)
                | cst.Float(value=val)
            ):
                return [val]
            case cst.Name(value=name):
                resolved = self.value_env.get(name, _NO_LITERAL)
                if resolved is _NO_LITERAL:
                    return []
                if isinstance(resolved, int) and not isinstance(resolved, bool):
                    return [f"{resolved}"]
                return [f"'{resolved}'"]
            case _:
                return []


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _abstract_from_obj(obj: Any) -> AbstractValue:
    """Type a live namespace object into an abstract value."""
    import types

    if isinstance(obj, types.ModuleType):
        return Dotted(getattr(obj, "__name__", ""))
    if isinstance(obj, type):
        return ClassRef(obj.__name__)
    return Node(type(obj).__name__)


def _dotted_name(node: cst.CSTNode) -> str | None:
    """Flatten an import name (``Name`` / dotted ``Attribute``) into ``a.b.c``."""
    match node:
        case cst.Name(value=str() as name):
            return name
        case cst.Attribute(value=base, attr=cst.Name(value=attr)):
            base_name = _dotted_name(base)
            return f"{base_name}.{attr}" if base_name is not None else None
        case _:
            return None


class _NoLiteral:
    pass


_NO_LITERAL = _NoLiteral()


def _literal_value(node: cst.BaseExpression) -> Any:
    """Best-effort Python value of a literal expression, else ``_NO_LITERAL``."""
    match node:
        case cst.SimpleString(value=val):
            try:
                return _pyast.literal_eval(val)
            except (ValueError, SyntaxError):  # pragma: no cover
                return _NO_LITERAL
        case cst.Integer(value=val):
            return int(val)
        case cst.Float(value=val):
            return float(val)
        case _:
            return _NO_LITERAL


def extract_call_args_kwargs(
    node: cst.Call, user_ns: Any
) -> tuple[list[Any], dict[str, Any]]:  # pragma: no cover
    """
    Take a cst Call Node and extract the args and kwargs, into a tuple of (args, kwargs)

    # TODO: This matcher is a mess, and lacks test coverage.
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
                if resolved_val := user_ns.get(val, None):
                    args.append(resolved_val)
            case cst.Arg(
                value=cst.Dict() as dict_node,
                keyword=None,
            ):
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
                cst.Name(value=val),
                keyword=cst.Name(value=key),
            ):
                if resolved_val := user_ns.get(val, None):
                    kwargs[key] = resolved_val
            case cst.Arg(
                value=cst.Dict() as dict_node,
                keyword=cst.Name(value=key),
            ):
                dict_value = _extract_dict_value(dict_node)
                kwargs[key] = dict_value
            case _:
                return args, kwargs

    return args, kwargs
