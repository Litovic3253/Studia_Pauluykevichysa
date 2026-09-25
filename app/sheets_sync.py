"""Автосинхронизация заказов/клиентов/цен в Google Таблицу через служебный аккаунт."""
import logging
import os
import threading
from pathlib import Path
from typing import Callable

from app.export import build_all_sheets

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsSyncError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(os.getenv("GOOGLE_SHEET_ID", "").strip()) and bool(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    )


def _build_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not key_path or not Path(key_path).exists():
        raise SheetsSyncError(f"Файл служебного аккаунта не найден: {key_path!r}")
    creds = Credentials.from_service_account_file(key_path, scopes=_SCOPES)
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
    """Запускает sync_now() в отдельном потоке, если синхронизация настроена; иначе ничего не делает."""
    if not is_configured():
        return

    def _run() -> None:
        try:
            sync_now()
        except SheetsSyncError as exc:
            logging.warning("Синхронизация с Google Таблицами не удалась: %s", exc)
            if on_error:
                on_error(exc)

    threading.Thread(target=_run, daemon=True).start()
