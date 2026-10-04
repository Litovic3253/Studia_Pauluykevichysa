"""Общие pytest-фикстуры."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

import db


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Подменяет db.DB_PATH на временный файл и инициализирует схему."""
    db_path = tmp_path / "test_orders.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    from app import client_pdf
    monkeypatch.setattr(client_pdf, "PDF_DIR", tmp_path / "pdf")  # не сорить PDF-ками в папке проекта
    monkeypatch.setattr(client_pdf, "SIGNATURE", tmp_path / "нет-подписи.png")  # без подписи владельца
    db.init()
    yield db_path


@pytest.fixture()
def github(tmp_path, monkeypatch, temp_db):
    """Настроенная синхронизация с GitHub, где вместо сети — репозиторий в памяти."""
    from app import github_sync
    from github_fake import FakeGithub

    fake = FakeGithub()
    monkeypatch.setattr(github_sync, "_request", fake.request)
    monkeypatch.setattr(github_sync, "_BASE_DIR", tmp_path)
    monkeypatch.setattr(github_sync, "_private_checked", set())
    monkeypatch.setenv("GITHUB_DATA_REPO", "me/data")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    return fake
