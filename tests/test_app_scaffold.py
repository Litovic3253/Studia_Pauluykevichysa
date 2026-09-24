"""Проверяет, что пакет app/ собирается и импортируется корректно."""
import importlib


def test_app_main_module_imports_and_has_entrypoint():
    module = importlib.import_module("app.main")
    assert callable(module.main)
