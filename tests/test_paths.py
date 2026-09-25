"""Тесты для paths.py — где приложение хранит данные (исходники vs собранный .exe)."""
import sys
from pathlib import Path

import paths

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_data_dir_is_project_root_when_running_from_source(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert paths.data_dir() == PROJECT_ROOT


def test_data_dir_is_next_to_exe_when_frozen(monkeypatch, tmp_path):
    exe = tmp_path / "Mochi Desktop" / "Mochi Desktop.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert paths.data_dir() == exe.parent


def test_all_data_locations_use_data_dir():
    import db
    from app import sheets_sync
    from app.screens import new_order, order_detail

    assert db.DB_PATH == paths.DATA_DIR / "orders.db" or db.DB_PATH.name == "test_orders.db"
    assert new_order.LOCAL_STORAGE == paths.DATA_DIR / "files_storage"
    assert order_detail.LOCAL_STORAGE == paths.DATA_DIR / "files_storage"
    assert sheets_sync._BASE_DIR == paths.DATA_DIR


def test_attachment_path_falls_back_to_data_dir_after_moving_computers(monkeypatch, tmp_path):
    from app.screens import order_detail

    moved = tmp_path / "files_storage" / "7" / "model.stl"
    moved.parent.mkdir(parents=True)
    moved.write_text("stl")
    monkeypatch.setattr(order_detail, "LOCAL_STORAGE", tmp_path / "files_storage")
    attachment = {"order_id": 7, "filename": "model.stl",
                  "local_path": r"C:\Users\old-pc\TGbot\app\files_storage\7\model.stl"}

    assert order_detail.resolve_attachment_path(attachment) == moved


def test_attachment_path_keeps_existing_absolute_path(tmp_path):
    from app.screens import order_detail

    existing = tmp_path / "model.stl"
    existing.write_text("stl")
    attachment = {"order_id": 7, "filename": "model.stl", "local_path": str(existing)}

    assert order_detail.resolve_attachment_path(attachment) == existing
