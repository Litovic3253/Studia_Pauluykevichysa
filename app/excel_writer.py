"""Запись заказов/клиентов/цен в .xlsx через openpyxl."""
from pathlib import Path

from openpyxl import Workbook

from app.export import build_all_sheets


def export_to_excel(path: str | Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)  # убираем дефолтный пустой лист "Sheet"
    for sheet_name, rows in build_all_sheets().items():
        ws = wb.create_sheet(title=sheet_name)
        for row in rows:
            ws.append(row)
    wb.save(path)
