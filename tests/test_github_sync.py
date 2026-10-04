"""Тесты для app/github_sync.py — вместо сети подставляется FakeGithub (см. github_fake.py)."""
import sqlite3
import time

import pytest

import db
from app import github_sync
from github_fake import add_order, use_pc


def _clients_in(db_bytes: bytes, tmp_path) -> list[str]:
    path = tmp_path / "remote_copy.db"
    path.write_bytes(db_bytes)
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT client FROM orders ORDER BY id")]
    finally:
        conn.close()


# ---------- настройка ----------

def test_is_configured_needs_repo_and_token(monkeypatch):
    monkeypatch.delenv("GITHUB_DATA_REPO", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    assert github_sync.is_configured() is False
    monkeypatch.setenv("GITHUB_DATA_REPO", "me/data")
    assert github_sync.is_configured() is True


@pytest.mark.parametrize("text", ["me/data", " https://github.com/me/data ", "https://github.com/me/data.git",
                                  "github.com/me/data/"])
def test_normalize_repo_accepts_links(text):
    assert github_sync.normalize_repo(text) == "me/data"


def test_normalize_repo_rejects_garbage():
    with pytest.raises(github_sync.GithubSyncError):
        github_sync.normalize_repo("просто текст")


def test_save_config_writes_env_file(github, tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_DATA_REPO")
    monkeypatch.delenv("GITHUB_TOKEN")

    github_sync.save_config("https://github.com/me/data", "new-token")

    assert github_sync.is_configured()
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "me/data" in env_text and "new-token" in env_text


def test_save_config_keeps_old_token_when_field_left_empty(github, tmp_path):
    github_sync.save_config("me/other", "")

    assert github_sync.current_repo() == "me/other"
    assert "test-token" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_save_config_refuses_public_repository(github, tmp_path):
    github.private = False

    with pytest.raises(github_sync.GithubSyncError, match="публичный"):
        github_sync.save_config("me/data", "new-token")

    assert not (tmp_path / ".env").exists()


# ---------- выгрузка ----------

def test_push_uploads_database_to_empty_repository(github, tmp_path):
    add_order("Геннадий")

    assert github_sync.push() == "uploaded"

    assert _clients_in(github.files["orders.db"], tmp_path) == ["Геннадий"]


def test_push_does_nothing_when_data_already_uploaded(github):
    add_order("Геннадий")
    github_sync.push()
    github.puts.clear()

    assert github_sync.push() == "unchanged"
    assert github.puts == []


def test_push_refuses_public_repository(github):
    github.private = False
    add_order("Геннадий")

    with pytest.raises(github_sync.GithubSyncError, match="публичный"):
        github_sync.push()

    assert github.files == {}


def test_push_uploads_attachments_and_signature_once(github, tmp_path):
    add_order("Геннадий")
    (tmp_path / "files_storage" / "1").mkdir(parents=True)
    (tmp_path / "files_storage" / "1" / "деталь.stl").write_bytes(b"solid model")
    (tmp_path / "signature.png").write_bytes(b"png-bytes")

    github_sync.push()

    assert github.files["files_storage/1/деталь.stl"] == b"solid model"
    assert github.files["signature.png"] == b"png-bytes"

    github.puts.clear()
    add_order("Александр")
    github_sync.push()
    assert github.puts == ["orders.db"]  # вложения не менялись — повторно не грузятся


def test_push_skips_files_over_size_limit(github, tmp_path, monkeypatch):
    monkeypatch.setattr(github_sync, "MAX_FILE_BYTES", 5)
    add_order("Геннадий")
    (tmp_path / "files_storage" / "1").mkdir(parents=True)
    (tmp_path / "files_storage" / "1" / "big.stl").write_bytes(b"0123456789")

    github_sync.push()

    assert "files_storage/1/big.stl" not in github.files
    assert "orders.db" in github.files


def test_push_refuses_to_overwrite_newer_remote_data(github, tmp_path, monkeypatch):
    use_pc(monkeypatch, tmp_path / "pc1")
    add_order("С первого ПК")
    github_sync.push()
    remote_before = github.files["orders.db"]

    use_pc(monkeypatch, tmp_path / "pc2")
    add_order("Со второго ПК")
    with pytest.raises(github_sync.ConflictError):
        github_sync.push()

    assert github.files["orders.db"] == remote_before


def test_push_force_overwrites_remote(github, tmp_path, monkeypatch):
    use_pc(monkeypatch, tmp_path / "pc1")
    add_order("С первого ПК")
    github_sync.push()

    use_pc(monkeypatch, tmp_path / "pc2")
    add_order("Со второго ПК")
    assert github_sync.push(force=True) == "uploaded"

    assert _clients_in(github.files["orders.db"], tmp_path) == ["Со второго ПК"]


# ---------- скачивание ----------

def test_pull_brings_orders_and_files_to_second_pc(github, tmp_path, monkeypatch):
    pc1, pc2 = tmp_path / "pc1", tmp_path / "pc2"
    use_pc(monkeypatch, pc1)
    add_order("Геннадий")
    (pc1 / "files_storage" / "1").mkdir(parents=True)
    (pc1 / "files_storage" / "1" / "деталь.stl").write_bytes(b"solid model")
    (pc1 / "signature.png").write_bytes(b"png-bytes")
    github_sync.push()

    use_pc(monkeypatch, pc2)
    assert github_sync.pull() == "downloaded"

    assert [o["client"] for o in db.list_orders_all()] == ["Геннадий"]
    assert (pc2 / "files_storage" / "1" / "деталь.stl").read_bytes() == b"solid model"
    assert (pc2 / "signature.png").read_bytes() == b"png-bytes"


def test_pull_keeps_backup_of_replaced_database(github, tmp_path, monkeypatch):
    pc1, pc2 = tmp_path / "pc1", tmp_path / "pc2"
    use_pc(monkeypatch, pc1)
    add_order("Новый с первого ПК")
    github_sync.push()

    use_pc(monkeypatch, pc2)
    add_order("Старый на втором ПК")
    github_sync.pull(force=True)

    backups = list(pc2.glob("orders.backup-*.db"))
    assert len(backups) == 1
    assert _clients_in(backups[0].read_bytes(), tmp_path) == ["Старый на втором ПК"]
    assert [o["client"] for o in db.list_orders_all()] == ["Новый с первого ПК"]


def test_pull_reports_unchanged_when_nothing_new(github):
    add_order("Геннадий")
    github_sync.push()

    assert github_sync.pull() == "unchanged"


def test_pull_does_not_revert_local_edits_when_remote_has_nothing_new(github):
    add_order("Геннадий")
    github_sync.push()
    add_order("Ещё не выгружен")

    assert github_sync.pull() == "unchanged"
    assert len(db.list_orders_all()) == 2


def test_pull_refuses_to_drop_unsent_local_changes(github, tmp_path, monkeypatch):
    pc1, pc2 = tmp_path / "pc1", tmp_path / "pc2"
    use_pc(monkeypatch, pc1)
    add_order("С первого ПК")
    github_sync.push()

    use_pc(monkeypatch, pc2)
    add_order("Не выгружен со второго ПК")
    with pytest.raises(github_sync.ConflictError):
        github_sync.pull()

    assert [o["client"] for o in db.list_orders_all()] == ["Не выгружен со второго ПК"]


def test_pull_fails_clearly_when_repository_is_empty(github):
    with pytest.raises(github_sync.GithubSyncError, match="нет данных"):
        github_sync.pull()


def test_pull_rejects_broken_file_and_keeps_local_data(github, tmp_path):
    add_order("Геннадий")
    github.files["orders.db"] = b"this is not a database"

    with pytest.raises(github_sync.GithubSyncError):
        github_sync.pull(force=True)

    assert [o["client"] for o in db.list_orders_all()] == ["Геннадий"]


# ---------- состояние ----------

def test_status_tracks_who_is_ahead(github, tmp_path, monkeypatch):
    pc1, pc2 = tmp_path / "pc1", tmp_path / "pc2"
    use_pc(monkeypatch, pc1)
    assert github_sync.status() == "remote_empty"
    add_order("Первый")
    assert github_sync.status() == "local_newer"
    github_sync.push()
    assert github_sync.status() == "in_sync"

    use_pc(monkeypatch, pc2)
    assert github_sync.status() == "remote_newer"  # пустая база на новом ПК — просто скачать
    github_sync.pull()
    assert github_sync.status() == "in_sync"
    add_order("Второй")
    assert github_sync.status() == "local_newer"
    github_sync.push()

    use_pc(monkeypatch, pc1)
    assert github_sync.status() == "remote_newer"
    add_order("Третий, пока второй ПК выгружал")
    assert github_sync.status() == "conflict"


def test_two_pcs_exchange_orders(github, tmp_path, monkeypatch):
    pc1, pc2 = tmp_path / "pc1", tmp_path / "pc2"
    use_pc(monkeypatch, pc1)
    add_order("Первый")
    github_sync.push()

    use_pc(monkeypatch, pc2)
    github_sync.pull()
    add_order("Второй")
    github_sync.push()

    use_pc(monkeypatch, pc1)
    github_sync.pull()
    assert [o["client"] for o in db.list_orders_all()] == ["Первый", "Второй"]


# ---------- фоновая выгрузка ----------

def test_push_in_background_does_nothing_when_not_configured(github, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN")
    called = []
    monkeypatch.setattr(github_sync, "push", lambda: called.append(True))

    github_sync.push_in_background()
    time.sleep(0.2)

    assert called == []


def test_push_in_background_reports_result(github):
    add_order("Геннадий")
    results = []

    github_sync.push_in_background(on_done=results.append)
    deadline = time.time() + 5
    while time.time() < deadline and not results:
        time.sleep(0.05)

    assert results == ["uploaded"]
    assert "orders.db" in github.files
