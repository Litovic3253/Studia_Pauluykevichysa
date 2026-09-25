"""Где приложение хранит данные: orders.db, files_storage/, .env, ключ Google.

При запуске из исходников — папка проекта (как и раньше). В собранном .exe —
папка, где лежит сам .exe: код PyInstaller распаковывает во временную папку,
которая удаляется после закрытия, поэтому хранить данные «рядом с кодом» там нельзя.
"""
import sys
from pathlib import Path


def data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


DATA_DIR = data_dir()
