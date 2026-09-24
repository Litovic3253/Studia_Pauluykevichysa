"""Точка входа Mochi Desktop — админ-панели, использующей общую с ботом orders.db."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import flet as ft
from dotenv import load_dotenv

import db

load_dotenv(ROOT / ".env")


def main(page: ft.Page) -> None:
    page.title = "Mochi Desktop"
    page.window.width = 1100
    page.window.height = 750
    db.init()
    page.add(
        ft.Text("Mochi Desktop", size=24, weight=ft.FontWeight.BOLD),
        ft.Text("Приложение запущено, база данных готова."),
    )


if __name__ == "__main__":
    ft.app(target=main)
