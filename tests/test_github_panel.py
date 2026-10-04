"""Тесты кнопок и окон синхронизации с GitHub (app/github_panel.py)."""
import time

import flet as ft
import pytest

import db
from app import github_sync
from app.github_panel import GithubPanel
from github_fake import add_order, use_pc


class _FakePage:
    def __init__(self):
        self.opened = []

    def open(self, control):
        self.opened.append(control)

    def close(self, control):
        if control in self.opened:
            self.opened.remove(control)

    def update(self, *controls):
        pass


@pytest.fixture()
def panel(github, monkeypatch):
    # Окна не смонтированы на настоящую страницу — их update() в тестах ничего не делает.
    monkeypatch.setattr(ft.AlertDialog, "update", lambda self: None)
    page = _FakePage()
    downloaded = []
    result = GithubPanel(page, on_downloaded=lambda: downloaded.append(True))
    result._spawn = lambda work: work()  # без потоков — результат сразу после вызова
    result.downloaded = downloaded
    return result


def _messages(page) -> list[str]:
    return [c.content.value for c in page.opened if isinstance(c, ft.SnackBar)]


def _remote_gets_newer_data(tmp_path, monkeypatch):
    """Другой компьютер выгружает свои данные поверх, после чего возвращаемся на этот."""
    here_dir, here_db = github_sync._BASE_DIR, db.DB_PATH
    use_pc(monkeypatch, tmp_path / "other-pc")
    add_order("С другого ПК")
    github_sync.push(force=True)
    monkeypatch.setattr(github_sync, "_BASE_DIR", here_dir)
    monkeypatch.setattr(db, "DB_PATH", here_db)


def test_upload_opens_settings_when_not_configured(panel, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN")

    panel.upload()

    assert panel.page.opened == [panel.settings_dialog]


def test_upload_reports_success(panel, github):
    add_order("Геннадий")

    panel.upload()

    assert "orders.db" in github.files
    assert any("выгружены" in m for m in _messages(panel.page))


def test_upload_reports_network_error(panel, github):
    github.offline = True

    panel.upload()

    assert any("Нет связи" in m for m in _messages(panel.page))


def test_download_replaces_data_and_refreshes_screens(panel, github, tmp_path, monkeypatch):
    _remote_gets_newer_data(tmp_path, monkeypatch)

    panel.download()

    assert [o["client"] for o in db.list_orders_all()] == ["С другого ПК"]
    assert panel.downloaded == [True]


def test_conflict_asks_which_version_to_keep(panel, github, tmp_path, monkeypatch):
    add_order("Здешний")
    _remote_gets_newer_data(tmp_path, monkeypatch)

    panel.upload()
    panel.upload()  # повторная попытка не открывает второе окно

    assert panel.page.opened.count(panel.conflict_dialog) == 1
    assert [o["client"] for o in db.list_orders_all()] == ["Здешний"]


def test_conflict_choice_download_takes_remote_version(panel, github, tmp_path, monkeypatch):
    add_order("Здешний")
    _remote_gets_newer_data(tmp_path, monkeypatch)
    panel.upload()

    panel.resolve_conflict("download")

    assert panel.conflict_dialog not in panel.page.opened
    assert [o["client"] for o in db.list_orders_all()] == ["С другого ПК"]
    assert panel.downloaded == [True]


def test_conflict_choice_upload_keeps_local_version(panel, github, tmp_path, monkeypatch):
    add_order("Здешний")
    _remote_gets_newer_data(tmp_path, monkeypatch)
    panel.upload()

    panel.resolve_conflict("upload")

    assert [o["client"] for o in db.list_orders_all()] == ["Здешний"]
    assert github_sync.status() == "in_sync"


def test_start_check_offers_download_when_github_is_newer(panel, github, tmp_path, monkeypatch):
    _remote_gets_newer_data(tmp_path, monkeypatch)

    panel.check_on_start()

    offers = [c for c in panel.page.opened if isinstance(c, ft.SnackBar) and c.action]
    assert len(offers) == 1
    assert db.list_orders_all() == []  # само ничего не скачивает — только предлагает


def test_start_check_is_silent_without_internet(panel, github):
    github.offline = True

    panel.check_on_start()

    assert panel.page.opened == []


def test_auto_upload_sends_new_order(panel, github):
    add_order("Геннадий")

    panel.auto_upload()
    deadline = time.time() + 5
    while time.time() < deadline and "orders.db" not in github.files:
        time.sleep(0.05)

    assert "orders.db" in github.files
    assert _messages(panel.page) == []  # фоновая выгрузка не отвлекает сообщениями


def test_auto_upload_reports_lost_connection_only_once(panel, github):
    github.offline = True

    for _ in range(2):
        add_order("Без интернета")
        panel.auto_upload()
        deadline = time.time() + 5
        while time.time() < deadline and not _messages(panel.page):
            time.sleep(0.05)
        time.sleep(0.2)

    assert len(_messages(panel.page)) == 1


def test_settings_reject_public_repository(panel, github):
    github.private = False
    panel.open_settings()
    panel.repo_field.value = "me/public"
    panel.token_field.value = "token"

    panel.save_settings()

    assert panel.settings_dialog in panel.page.opened
    assert "публичный" in panel.error_text.value
    assert github_sync.current_repo() == "me/data"


def test_settings_save_connects_repository(panel, github, monkeypatch):
    monkeypatch.delenv("GITHUB_DATA_REPO")
    monkeypatch.delenv("GITHUB_TOKEN")
    panel.open_settings()
    panel.repo_field.value = "https://github.com/me/data"
    panel.token_field.value = "token"

    panel.save_settings()

    assert panel.settings_dialog not in panel.page.opened
    assert github_sync.is_configured()
