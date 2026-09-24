"""Скачивание файлов из Telegram Bot API по file_id, с кэшем на диск."""
import os
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).resolve().parent / "files_cache"


class TelegramFileError(RuntimeError):
    pass


def _bot_token() -> str:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise TelegramFileError("BOT_TOKEN не задан в .env")
    return token


def _find_cached(file_id: str, cache_dir: Path) -> Path | None:
    matches = list(cache_dir.glob(f"{file_id}_*"))
    return matches[0] if matches else None


def download_file(file_id: str, *, cache_dir: Path = CACHE_DIR) -> Path:
    """Скачивает файл по file_id (или возвращает уже скачанную копию из кэша)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = _find_cached(file_id, cache_dir)
    if cached:
        return cached

    token = _bot_token()
    with httpx.Client(timeout=30) as client:
        info = client.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id})
        info.raise_for_status()
        payload = info.json()
        if not payload.get("ok"):
            raise TelegramFileError(f"Telegram API вернул ошибку: {payload}")
        file_path = payload["result"]["file_path"]

        dest = cache_dir / f"{file_id}_{Path(file_path).name}"
        download = client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
        download.raise_for_status()
        dest.write_bytes(download.content)
    return dest
