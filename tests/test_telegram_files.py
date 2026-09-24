"""Тесты для скачивания файлов из Telegram Bot API (сеть замокана)."""
import httpx
import pytest

from app import telegram_files as tf


class _FakeResponse:
    def __init__(self, json_data=None, content=b""):
        self._json = json_data
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None):
        if "getFile" in url:
            return _FakeResponse(json_data={"ok": True, "result": {"file_path": "documents/model.stl"}})
        return _FakeResponse(content=b"STL-DATA")


def test_download_file_saves_and_returns_path(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "fake-token")
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    dest = tf.download_file("FILEID123", cache_dir=tmp_path)

    assert dest.exists()
    assert dest.read_bytes() == b"STL-DATA"


def test_download_file_uses_cache_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "fake-token")
    cached = tmp_path / "FILEID123_model.stl"
    cached.write_bytes(b"cached")

    def _boom(*a, **k):
        raise AssertionError("не должен обращаться к сети, если файл уже в кэше")

    monkeypatch.setattr(httpx, "Client", _boom)

    dest = tf.download_file("FILEID123", cache_dir=tmp_path)
    assert dest.read_bytes() == b"cached"


def test_download_file_without_token_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    with pytest.raises(tf.TelegramFileError):
        tf.download_file("FILEID123", cache_dir=tmp_path)
