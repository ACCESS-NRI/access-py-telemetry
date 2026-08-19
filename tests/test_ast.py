#!/usr/bin/env python
# type: ignore

"""Tests for the AST module (typed transition interpreter)."""

import libcst as cst
import pytest

from access_py_telemetry.ast import (
    Dotted,
    Node,
    capture_registered_calls,
    interpret,
    strip_magic,
)


class MockInfo:
    def __init__(self, raw_cell=None):
        self.raw_cell = raw_cell


def events_for(code, registry, ns=None):
    """Interpret ``code`` against a single-service ``registry`` and return events."""
    tree = cst.parse_module(code)
    return interpret(tree, {"mock": set(registry)}, ns or {})


def caught(code, registry, ns=None):
    """The set of registered names detected in ``code``."""
    return {event.name for event in events_for(code, registry, ns)}


def test_same_cell_instantiation():
    """
    The motivating case: an object is instantiated in the *same* cell as the
    method call. `pre_run_cell` fires before execution, so the namespace can't
    help — the type is resolved statically from the constructor. No namespace.
    """
    code = """
class MyClass:
    def func(self):
        self.set_var = set()

    def uncaught_func(self, *args, **kwargs):
        pass

instance = MyClass()
instance.func()
instance.uncaught_func()
"""
    assert caught(code, ["MyClass.func"]) == {"MyClass.func"}
    assert "MyClass.uncaught_func" not in caught(code, ["MyClass.func"])


def test_instance_method_from_namespace():
    """An object created in an earlier cell is typed via the namespace fallback."""
    code = "instance.func()\n"
    ns = {"instance": type("MyClass", (), {})()}
    assert caught(code, ["MyClass.func"], ns) == {"MyClass.func"}


def test_bare_function_args_kwargs():
    code = "registered_func(x, y=y, z=z)\n"
    ns = {"x": 1, "y": "a_str", "z": ["a", "list", 0, "random", ["values"]]}
    events = events_for(code, ["registered_func"], ns)
    assert len(events) == 1
    event = events[0]
    assert event.name == "registered_func"
    assert event.args == [1]
    assert event.kwargs == {"y": "a_str", "z": ["a", "list", 0, "random", ["values"]]}


def test_unparse_bare_function():
    code = """
import pandas as pd

def registered_func():
    return None

def registered_func2(x):
    return None

def unregistered_func():
    return None

registered_func()
unregistered_func()
registered_func2(pd.DataFrame())
"""
    assert caught(code, ["registered_func", "registered_func2"]) == {
        "registered_func",
        "registered_func2",
    }


def test_aliased_function():
    """A function rebound to a new name is dealiased through the binding env."""
    code = """
def registered_func():
    return None

reg_func = registered_func

reg_func()
"""
    assert caught(code, ["registered_func"]) == {"registered_func"}


def test_instantiate_and_call():
    code = "MyClass().func()\n"
    ns = {"MyClass": type("MyClass", (), {})}
    assert caught(code, ["MyClass.func"], ns) == {"MyClass.func"}


def test_instantiate_and_call_same_cell():
    code = """
class MyClass:
    def func(self):
        self.set_var = set()

MyClass().func()
"""
    assert caught(code, ["MyClass.func"]) == {"MyClass.func"}


def test_class_method():
    code = """
class MyClass:
    @classmethod
    def func(cls):
        cls.set_var = set()

MyClass.func()
"""
    assert caught(code, ["MyClass.func"]) == {"MyClass.func"}


def test_indexing():
    code = """
class MyClass:
    def __getitem__(self, key):
        return [1, 2, 3]

instance = MyClass()
mycall = instance['some_item']

l = [1, 2, 3]
l[0]
"""
    assert caught(code, ["MyClass.__getitem__", "list.__getitem__"]) == {
        "MyClass.__getitem__",
        "list.__getitem__",
    }


def test_nested_function():
    code = """
import os

os.path.join("some", "paths")
"""
    assert caught(code, ["os.path.join"]) == {"os.path.join"}


def test_aliased_module():
    code = """
import os as operating_system

operating_system.path.join("some", "paths")
"""
    assert caught(code, ["os.path.join"]) == {"os.path.join"}


@pytest.mark.parametrize(
    "raw_cell, expected",
    [
        (
            """
class MyClass:
    def __getitem__(self, key):
        return [1, 2, 3]

instance = MyClass()

search_str = 'some_item'

mycall = instance[search_str]
""",
            ("MyClass.__getitem__", ["'some_item'"], {}),
        ),
        (
            """
class MyClass:
    def __getitem__(self, key):
        return [1, 2, 3]

instance = MyClass()

mycall = instance['directly_used_string']
""",
            ("MyClass.__getitem__", ["'directly_used_string'"], {}),
        ),
        (
            """
l = [0, 1, 2, 3]

MAGIC_NUMBER = 1

l[MAGIC_NUMBER]
""",
            ("list.__getitem__", ["1"], {}),
        ),
    ],
)
def test_indexing_args(raw_cell, expected):
    """
    An index argument is recorded as its value (`'my_expt'`), whether written
    directly or held in a same-cell variable — never the variable identifier.
    """
    events = events_for(raw_cell, ["MyClass.__getitem__", "list.__getitem__"])
    assert len(events) == 1
    event = events[0]
    assert (event.name, event.args, event.kwargs) == expected


def test_import_catalog():
    code = """
import intake
intake.cat.access_nri
"""
    assert caught(code, ["intake.cat.access_nri"]) == {"intake.cat.access_nri"}


def test_import_assign_catalog():
    code = """
import intake
cat = intake.cat.access_nri
"""
    assert caught(code, ["intake.cat.access_nri"]) == {"intake.cat.access_nri"}


def test_import_assign_catalog_types_variable():
    """Assigning the generator result binds the variable's node type."""
    tree = cst.parse_module("import intake\ncat = intake.cat.access_nri\n")
    interp_events = interpret(tree, {"mock": {"intake.cat.access_nri"}}, {})
    assert len(interp_events) == 1


def test_index_return_self_and_chained_call():
    """
    A chained call whose first link is an index that returns self, then a method
    on the result. The __getitem__ defaults to returning self, so both are caught.
    """
    code = """
class MyClass:
    def __getitem__(self, key):
        return self

    def compute(self, *args, **kwargs):
        import random
        return random.random()

c = MyClass()
random_num = c['some_item'].compute()
"""
    assert caught(code, ["MyClass.__getitem__", "MyClass.compute"]) == {
        "MyClass.__getitem__",
        "MyClass.compute",
    }


def test_instantiate_index_and_chained_call():
    code = """
class MyClass:
    def __getitem__(self, key):
        return self

    def compute(self, *args, **kwargs):
        import random
        return random.random()

random_num = MyClass()['some_item'].compute()
"""
    assert caught(code, ["MyClass.__getitem__", "MyClass.compute"]) == {
        "MyClass.__getitem__",
        "MyClass.compute",
    }


def test_import_and_index_into_catalog():
    """intake.cat.access_nri['x'] catches the generator and the __getitem__ edge."""
    code = """
import intake
try:
    intake.cat.access_nri['some_item']
except Exception:
    pass
"""
    registry = ["intake.cat.access_nri", "DfFileCatalog.__getitem__"]
    assert caught(code, registry) == {
        "intake.cat.access_nri",
        "DfFileCatalog.__getitem__",
    }


def test_import_stringindex_and_search():
    code = """
import intake
try:
    intake.cat.access_nri['some_item'].search(file_id='xyz').to_dask()
except Exception:
    pass
"""
    registry = [
        "intake.cat.access_nri",
        "DfFileCatalog.__getitem__",
        "esm_datastore.search",
        "esm_datastore.to_dask",
    ]
    assert caught(code, registry) == set(registry)


def test_import_stringindex_save_and_search():
    code = """
import intake
try:
    datastore = intake.cat.access_nri["1deg_era5_iaf"]
    dataset = datastore.search(
        start_date='1960-01-01, 00:00:00'
    ).to_dask()
except Exception:
    pass
"""
    registry = [
        "intake.cat.access_nri",
        "DfFileCatalog.__getitem__",
        "esm_datastore.search",
        "esm_datastore.to_dask",
    ]
    assert caught(code, registry) == set(registry)


def test_import_varindex_and_search():
    code = """
import intake
source = 'some_item'
try:
    intake.cat.access_nri[source].search(file_id='xyz').to_dask()
except Exception:
    pass
"""
    registry = [
        "intake.cat.access_nri",
        "DfFileCatalog.__getitem__",
        "esm_datastore.search",
        "esm_datastore.to_dask",
    ]
    assert caught(code, registry) == set(registry)


def test_implicit_boolean_conversion():
    """`arr = np.array(...)` is untypeable statically, so `arr` falls back to the
    namespace, where its runtime type is `ndarray`."""
    code = """
arr = np.array([0, 2, 3])
arr.mean()
"""
    ns = {"np": type("np_module", (), {})(), "arr": type("ndarray", (), {})()}
    assert caught(code, ["ndarray.mean"], ns) == {"ndarray.mean"}


def test_chained_function_call():
    """
    The most 'real life' test: a chained call is caught with the calls recorded
    in the right order.
    """
    code = """
class esm_datastore:
    def search(self, **kwargs):
        return self

    def to_dask(self, **kwargs) -> None:
        return None

esm_ds = esm_datastore()

time = '2023-01-01'

ds = esm_ds.search(
    file_id='xyz'
).search(
    start_date=time
).to_dask(
    xarray_open_kwargs = {'chunks' : 'auto'}
)
"""
    registry = ["esm_datastore.search", "esm_datastore.to_dask"]
    events = events_for(code, registry)

    assert {e.name for e in events} == {
        "esm_datastore.search",
        "esm_datastore.to_dask",
    }
    ordered = [(e.name, e.args, e.kwargs) for e in events]
    assert ordered == [
        ("esm_datastore.search", [], {"file_id": "'xyz'"}),
        ("esm_datastore.search", [], {"start_date": "2023-01-01"}),
        ("esm_datastore.to_dask", [], {"xarray_open_kwargs": {"chunks": "auto"}}),
    ]


def test_match_ipython_magic():
    """IPython magic lines are stripped before parsing."""
    raw_cell = r"""
!ls
%%timeit
class MyClass:
    @classmethod
    def class_func(cls):
        self.set_var = set()

    def uncaught_func(self, *args, **kwargs):
        pass

MyClass.func(instance)

MyClass.func??

MyClass.func?
    """

    python_code = r"""
class MyClass:
    @classmethod
    def class_func(cls):
        self.set_var = set()

    def uncaught_func(self, *args, **kwargs):
        pass

MyClass.func(instance)


    """

    parsed_w_magic = strip_magic(raw_cell)
    parsed_wo_magic = strip_magic(python_code)

    assert parsed_w_magic == parsed_wo_magic

    tree_w_magic = cst.parse_module(parsed_w_magic)
    tree_wo_magic = cst.parse_module(parsed_wo_magic)
    assert tree_w_magic.deep_equals(tree_wo_magic)


def test_parse_invalid_code():
    """Invalid code must not raise out of the hook."""
    mock_info = MockInfo()
    mock_info.raw_cell = """
class MyClass:
    def func(self):
        self.set_var = set()

instance = MyClass()
mycall = instance.func()

    instance.uncaught_func()
"""
    capture_registered_calls(mock_info)

    mock_info = MockInfo()
    mock_info.raw_cell = """
@instance = MyClass()
1mycall = instance.func()
"""
    capture_registered_calls(mock_info)


def test_none_cell_is_noop():
    """A cell with no source is a no-op."""
    assert capture_registered_calls(MockInfo(raw_cell=None)) is None


def test_abstract_values_smoke():
    """The abstract value dataclasses are importable and comparable."""
    assert Node("esm_datastore") == Node("esm_datastore")
    assert Dotted("os.path") != Dotted("os")
