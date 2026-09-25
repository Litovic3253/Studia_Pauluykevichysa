"""Автосинхронизация заказов/клиентов/цен в Google Таблицу через служебный аккаунт."""
import logging
import os
import threading
from pathlib import Path
from typing import Callable

from app.export import build_all_sheets
from paths import DATA_DIR

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
# Папка данных (там же лежит .env) — относительный путь к ключу считается от неё,
# а не от текущей рабочей папки.
_BASE_DIR = DATA_DIR

_state_lock = threading.Lock()
_pending = False
_running = False


class SheetsSyncError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(os.getenv("GOOGLE_SHEET_ID", "").strip()) and bool(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    )


def _key_path() -> Path | None:
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else _BASE_DIR / path


def _build_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    key_path = _key_path()
    if key_path is None or not key_path.exists():
        raise SheetsSyncError(f"Файл служебного аккаунта не найден: {str(key_path or '')!r}")
    creds = Credentials.from_service_account_file(str(key_path), scopes=_SCOPES)
    return build("sheets", "v4", credentials=creds)


def _ensure_sheets_exist(service, sheet_id: str, sheet_names: list[str]) -> None:
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in spreadsheet.get("sheets", [])}
    missing = [name for name in sheet_names if name not in existing]
    if missing:
        requests = [{"addSheet": {"properties": {"title": name}}} for name in missing]
        service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()


def sync_now() -> None:
    """Синхронно перезаписывает все три листа в Google Таблице. Бросает SheetsSyncError при любом сбое."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if not sheet_id:
        raise SheetsSyncError("GOOGLE_SHEET_ID не задан в .env")
    try:
        service = _build_service()
        sheets = build_all_sheets()
        _ensure_sheets_exist(service, sheet_id, list(sheets.keys()))
        for sheet_name, rows in sheets.items():
            service.spreadsheets().values().clear(spreadsheetId=sheet_id, range=sheet_name).execute()
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=f"{sheet_name}!A1",
                valueInputOption="RAW", body={"values": rows},
            ).execute()
    except SheetsSyncError:
        raise
    except Exception as exc:  # noqa: BLE001 - любая ошибка сети/API оборачивается в единый тип
        raise SheetsSyncError(str(exc)) from exc


def sync_in_background(on_error: Callable[[Exception], None] | None = None) -> None:
    """Запускает sync_now() в отдельном потоке, если синхронизация настроена; иначе ничего не делает.

    Одновременно идёт не больше одной синхронизации: вызовы во время работы только
    помечают данные «грязными», и по окончании выполняется ровно один повтор —
    иначе параллельные clear/update могли бы перемешаться и оставить в листе старые строки.
    """
    global _pending, _running
    if not is_configured():
        return
    with _state_lock:
        _pending = True
        if _running:
            return
        _running = True

    def _run() -> None:
        global _pending, _running
        while True:
            with _state_lock:
                if not _pending:
                    _running = False
                    return
                _pending = False
            try:
                sync_now()
            except Exception as exc:  # noqa: BLE001 - поток не должен умереть с _running=True
                logging.warning("Синхронизация с Google Таблицами не удалась: %s", exc)
                if on_error:
                    on_error(exc)

    threading.Thread(target=_run, daemon=True).start()
