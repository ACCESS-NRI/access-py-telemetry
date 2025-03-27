#!/usr/bin/env python
# type: ignore

"""Tests for the AST module"""

import ast
import pytest
from access_py_telemetry.ast import CallListener
from unittest.mock import MagicMock


class MockInfo:
    def __init__(self, raw_cell=None):
        self.raw_cell = raw_cell


# def test_capture_registered_calls():
#     mock_info = MockInfo()
#     mock_info.raw_cell = """
# intake.open_esm_datastore("dud_filename")
# esm_datastore.search(name='xyz')
#     """

#     capture_registered_calls(mock_info)


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

    class MyClass:
        def func(self):
            self.set_var = set()

        def uncaught_func(self, *args, **kwargs):
            pass

    mock_user_ns = {
        "instance": MyClass(),
    }

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

    def registered_func():
        return None

    def unregistered_func():
        return None

    mock_user_ns = {
        "registered_func": registered_func,
        "unregistered_func": unregistered_func,
    }

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

    def registered_func():
        return None

    def unregistered_func():
        return None

    mock_user_ns = {
        "registered_func": registered_func,
        "unregistered_func": unregistered_func,
        "reg_func": registered_func,
    }

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

    class MyClass:
        def func(self):
            self.set_var = set()

    mock_user_ns = {
        "MyClass": MyClass,
        "instance": MyClass(),
    }

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

    class MyClass:
        def func(self):
            self.set_var = set()

    class SecondClass:
        def other_func(self):
            self.other_var = 1

    class ClassFunc:
        @classmethod
        def class_func(cls):
            cls.class_var = 1

    def my_bare_func():
        return None

    mock_user_ns = {
        "MyClass": MyClass,
    }

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

"""

    class MyClass:
        def func(self):
            self.set_var = set()

        def __getitem__(self, key):
            return [1, 2, 3]

    mock_user_ns = {
        "MyClass": MyClass,
        "instance": MyClass(),
    }

    mock_registry = {"mock": ["MyClass.__getitem__"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "MyClass.__getitem__",
    }


def test_ast_nested_function():
    mock_info = MockInfo()
    mock_info.raw_cell = """
import os

os.path.join("some","paths")

"""

    import os

    mock_user_ns = {
        "os": os,
    }

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

    import os as operating_system

    mock_user_ns = {
        "operating_system": operating_system,
    }

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

    import intake

    mock_user_ns = {
        "intake": intake,
        "intake.cat.access_nri": intake.cat.access_nri,
    }

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

    import intake

    mock_user_ns = {
        "intake": intake,
        "intake.cat.access_nri": intake.cat.access_nri,
    }

    mock_registry = {"mock": ["intake.catalog.Catalog.__init__"]}

    mock_api_handler = MagicMock()

    tree = ast.parse(mock_info.raw_cell)

    visitor = CallListener(mock_user_ns, mock_registry, mock_api_handler)

    visitor.visit(tree)

    assert visitor._caught_calls == {
        "intake.cat.access_nri",
    }
