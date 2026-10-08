import importlib
import sys


def test_python_is_is_the_pinned_minor_version():
    assert sys.version_info[:2] == (3, 13)


def test_app_package_is_importable():
    assert importlib.import_module("app").__name__ == "app"
