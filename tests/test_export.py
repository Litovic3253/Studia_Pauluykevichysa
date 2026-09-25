"""Тесты для app/export.py — сборка строк для Excel/Google Таблиц."""
import db
from app import export


def test_build_orders_sheet_has_header_row_and_one_data_row(temp_db):
    order_id = db.add_order({
        "client": "Иван", "contact": "@ivan", "material": "PLA",
        "weight_g": 100, "print_hours": 2, "qty": 1, "cost": 400, "price": 600,
    })
    db.update_order(order_id, paid=1)

    rows = export.build_orders_sheet()

    assert rows[0][0] == "ID"
    assert len(rows) == 2
    data_row = rows[1]
    assert data_row[0] == order_id
    assert data_row[1] == "Иван"
    assert data_row[2] == "@ivan"


def test_build_orders_sheet_shows_paid_status_in_russian(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    db.update_order(order_id, paid=1)
    rows = export.build_orders_sheet()
    header = rows[0]
    paid_col = header.index("Оплачен")
    assert rows[1][paid_col] == "Да"


def test_build_customers_sheet_includes_aggregates(temp_db):
    order_id = db.add_order({"client": "Мария", "contact": "@maria", "cost": 100, "price": 200})
    db.update_order(order_id, paid=1)

    rows = export.build_customers_sheet()

    assert rows[0][0] == "ID"
    assert len(rows) == 2
    header = rows[0]
    data_row = rows[1]
    assert data_row[header.index("Имя")] == "Мария"
    assert data_row[header.index("Заказов")] == 1
    assert data_row[header.index("Оплачено")] == 200


def test_build_prices_sheet_has_materials_and_rates_sections(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 55)

    rows = export.build_prices_sheet()

    assert rows[0] == ["Материал", "Цена за кг"]
    assert ["PLA", 4000] in rows
    assert ["Параметр", "Значение"] in rows
    assert ["Ставка часа печати", 55] in rows


def test_build_all_sheets_returns_all_three_named_sheets(temp_db):
    sheets = export.build_all_sheets()
    assert set(sheets.keys()) == {"Заказы", "Клиенты", "Цены"}
    for rows in sheets.values():
        assert len(rows) >= 1  # хотя бы заголовок
