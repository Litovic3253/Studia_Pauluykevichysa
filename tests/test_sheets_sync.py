"""Тесты для app/sheets_sync.py — Google API-клиент подменяется фейком."""
import db
from app import sheets_sync


class _FakeValues:
    def __init__(self, calls):
        self._calls = calls

    def clear(self, spreadsheetId, range):
        self._calls.append(("clear", range))
        return self

    def update(self, spreadsheetId, range, valueInputOption, body):
        self._calls.append(("update", range, body["values"]))
        return self

    def execute(self):
        return {}


class _FakeSpreadsheets:
    def __init__(self, calls, existing_sheet_titles):
        self._calls = calls
        self._existing = existing_sheet_titles

    def get(self, spreadsheetId):
        self._pending = "get"
        return self

    def batchUpdate(self, spreadsheetId, body):
        for req in body["requests"]:
            self._existing.append(req["addSheet"]["properties"]["title"])
        self._pending = "batchUpdate"
        return self

    def values(self):
        return _FakeValues(self._calls)

    def execute(self):
        if self._pending == "get":
            return {"sheets": [{"properties": {"title": t}} for t in self._existing]}
        return {}


class _FakeService:
    def __init__(self, existing_sheet_titles):
        self._calls = []
        self._existing = existing_sheet_titles

    def spreadsheets(self):
        return _FakeSpreadsheets(self._calls, self._existing)


def test_is_configured_false_when_env_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
    assert sheets_sync.is_configured() is False


def test_is_configured_true_when_both_env_set(monkeypatch, tmp_path):
    key_file = tmp_path / "key.json"
    key_file.write_text("{}")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "abc123")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(key_file))
    assert sheets_sync.is_configured() is True


def test_sync_now_updates_all_three_sheets(monkeypatch, temp_db):
    db.add_order({"client": "Тест", "contact": "", "cost": 0, "price": 0})
    monkeypatch.setenv("GOOGLE_SHEET_ID", "fake-id")
    fake_service = _FakeService(existing_sheet_titles=["Заказы", "Клиенты", "Цены"])
    monkeypatch.setattr(sheets_sync, "_build_service", lambda: fake_service)

    sheets_sync.sync_now()

    update_ranges = {call[1] for call in fake_service._calls if call[0] == "update"}
    assert update_ranges == {"Заказы!A1", "Клиенты!A1", "Цены!A1"}


def test_sync_now_creates_missing_sheets(monkeypatch, temp_db):
    monkeypatch.setenv("GOOGLE_SHEET_ID", "fake-id")
    fake_service = _FakeService(existing_sheet_titles=[])  # пустая таблица, ни одного листа
    monkeypatch.setattr(sheets_sync, "_build_service", lambda: fake_service)

    sheets_sync.sync_now()

    assert set(fake_service._existing) == {"Заказы", "Клиенты", "Цены"}


def test_sync_now_raises_sheets_sync_error_when_sheet_id_missing(monkeypatch, temp_db):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    try:
        sheets_sync.sync_now()
        assert False, "должно было бросить SheetsSyncError"
    except sheets_sync.SheetsSyncError:
        pass


def test_sync_in_background_does_nothing_when_not_configured(monkeypatch, temp_db):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
    called = []
    monkeypatch.setattr(sheets_sync, "sync_now", lambda: called.append(True))

    sheets_sync.sync_in_background()
    import time
    time.sleep(0.2)  # дать фоновому потоку шанс запуститься, если бы он был запущен

    assert called == []
