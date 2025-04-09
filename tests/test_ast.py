#!/usr/bin/env python
# type: ignore

"""Tests for the AST module"""

import ast
import sys
import pytest
from access_py_telemetry.ast import CallListener, strip_magic, capture_registered_calls
from unittest.mock import MagicMock


class MockInfo:
    def __init__(self, raw_cell=None):
        self.raw_cell = raw_cell


def test_ast_instance_method():
    mock_info = MockInfo()
    mock_info.raw_cell = """
class MyClass:
    def func(self):
        self.set_var = set()

    def uncaught_func(self, *args, **kwargs):
        pass

instance = MyClass()
mycall = instance.func()

instance.uncaught_func()
"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["MyClass.func"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "MyClass.func",
    }

    assert "MyClass.uncaught_func" not in visitor._caught_calls


def test_ast_bare_function():
    mock_info = MockInfo()
    mock_info.raw_cell = """
def registered_func():
    return None

def unregistered_func():
    return None

registered_func()
unregistered_func()

"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["registered_func"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "registered_func",
    }

    assert "uncaught_func" not in visitor._caught_calls


def test_ast_unparse_bare_function():
    mock_info = MockInfo()
    mock_info.raw_cell = """

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

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["registered_func", "registered_func2"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "registered_func",
        "registered_func2",
    }

    assert "uncaught_func" not in visitor._caught_calls


@pytest.mark.xfail
def test_ast_aliased_function():
    """
    This will require more sophisticated analysis to catch aliased functions. Maybe
    we can look at this eventually
    """
    mock_info = MockInfo()
    mock_info.raw_cell = """
def registered_func():
    return None

def unregistered_func():
    return None


reg_func = registered_func

reg_func()

unregistered_func()

"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["registered_func"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "registered_func",
    }

    assert "uncaught_func" not in visitor._caught_calls


@pytest.mark.xfail
def test_ast_instantiate_and_call():
    """
    Need to figure out how to catch the instantiation of a class and then call a method
    on it. Not needed yet
    """
    mock_info = MockInfo()
    mock_info.raw_cell = """
class MyClass:
    def func(self):
        self.set_var = set()


MyClass().func()

"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["MyClass.func"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "MyClass.func",
    }


@pytest.mark.xfail
def test_ast_class_method():
    """
    Class methods don't work with the CallListener yet
    """
    mock_info = MockInfo()
    mock_info.raw_cell = """
class MyClass:
    @classmethod
    def class_func(cls):
        self.set_var = set()

    def uncaught_func(self, *args, **kwargs):
        pass


MyClass.func(instance)

"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["MyClass.class_func"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "MyClass.class_func",
    }


def test_ast_indexing():
    mock_info = MockInfo()
    mock_info.raw_cell = """
class MyClass:
    def func(self):
        self.set_var = set()

    def __getitem__(self, key):
        return [1, 2, 3]

instance = MyClass()
mycall = instance['some_item']

l = [1, 2, 3]

l[0]

"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["MyClass.__getitem__", "list.__getitem__"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "MyClass.__getitem__",
        "list.__getitem__",
    }


def test_ast_nested_function():
    mock_info = MockInfo()
    mock_info.raw_cell = """
import os

os.path.join("some","paths")

"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["os.path.join"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "os.path.join",
    }


def test_ast_aliased_module():
    mock_info = MockInfo()
    mock_info.raw_cell = """
import os as operating_system

operating_system.path.join("some","paths")

"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["os.path.join"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "os.path.join",
    }


def test_import_catalog():
    mock_info = MockInfo()
    mock_info.raw_cell = """
import intake
intake.cat.access_nri

"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["intake.cat.access_nri"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "intake.cat.access_nri",
    }


def test_import_assign_catalog():
    mock_info = MockInfo()
    mock_info.raw_cell = """
import intake
cat = intake.cat.access_nri

"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["intake.cat.access_nri"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "intake.cat.access_nri",
    }


@pytest.mark.xfail
def test_import_catalog_traverse_imports():
    """
    This fails because the CallListener doesn't traverse the imports yet. We can
    do this using importlib and then parsing what importlib imports too I think,
    but let's save that for another day
    """
    mock_info = MockInfo()
    mock_info.raw_cell = """
import intake 
intake.cat.access_nri
"""

    f = sys._getframe()
    exec(mock_info.raw_cell, globals(), f.f_locals)
    mock_user_ns = f.f_locals

    mock_registry = {"mock": ["intake.catalog.Catalog.__init__"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "intake.cat.access_nri",
    }


def test_match_ipython_magic():
    """
    This test is to check that the IPython magic commands are not caught by the
    CallListener. This is important because we don't want to send telemetry for
    IPython magic commands.
    """
    mock_info = MockInfo()
    mock_info.raw_cell = r"""
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

    parsed_w_magic = strip_magic(mock_info.raw_cell)
    parsed_wo_magic = strip_magic(python_code)

    assert parsed_w_magic == parsed_wo_magic

    a = ast.dump(ast.parse(parsed_w_magic), annotate_fields=False)
    b = ast.dump(ast.parse(parsed_wo_magic), annotate_fields=False)
    assert a == b


def test_parse_invalid_code():
    mock_info = MockInfo()
    mock_info.raw_cell = """
class MyClass:
    def func(self):
        self.set_var = set()

    def uncaught_func(self, *args, **kwargs):
        pass

instance = MyClass()
mycall = instance.func()

    instance.uncaught_func()


"""

    capture_registered_calls(mock_info)

    mock_info = MockInfo()
    mock_info.raw_cell = """
class MyClass:
    def func(self):
        self.set_var = set()

    def uncaught_func(self, *args, **kwargs):
        pass

@instance = MyClass()
1mycall = instance.func()

    instance.uncaught_func()


"""

    capture_registered_calls(mock_info)
