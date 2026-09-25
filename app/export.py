"""Сборка данных заказов/клиентов/цен в виде простых строк — общий источник
для локального Excel-экспорта и синхронизации с Google Таблицами."""
from typing import Any

import db

ORDER_COLUMNS = [
    "ID", "Клиент", "Контакт", "Описание", "Материал", "Цвет", "Вес, г",
    "Часы печати", "Кол-во", "Срок", "Статус", "Оплачен", "Себестоимость",
    "Цена", "Заметки", "Создан",
]

CUSTOMER_COLUMNS = ["ID", "Имя", "Контакт", "Заметки", "Заказов", "Оплачено", "Долг", "Создан"]


def build_orders_sheet() -> list[list[Any]]:
    rows: list[list[Any]] = [ORDER_COLUMNS]
    for o in db.list_orders_all():
        rows.append([
            o["id"],
            o["client"],
            o["contact"] or "",
            o["description"] or "",
            o["material"] or "",
            o["color"] or "",
            o["weight_g"] or 0,
            o["print_hours"] or 0,
            o["qty"] or 1,
            o["deadline"] or "",
            db.STATUSES.get(o["status"], o["status"]),
            "Да" if o["paid"] else "Нет",
            o["cost"] or 0,
            o["price"] or 0,
            o["notes"] or "",
            o["created_at"],
        ])
    return rows


def build_customers_sheet() -> list[list[Any]]:
    rows: list[list[Any]] = [CUSTOMER_COLUMNS]
    for c in db.list_customers():
        rows.append([
            c["id"],
            c["name"],
            c["contact"] or "",
            c["notes"] or "",
            c["orders_count"],
            c["paid_total"],
            c["debt_total"],
            c["created_at"],
        ])
    return rows


def build_prices_sheet() -> list[list[Any]]:
    settings = db.get_settings()
    rows: list[list[Any]] = [["Материал", "Цена за кг"]]
    rows.extend([name, price] for name, price in settings["materials"].items())
    rows.append([])
    rows.append(["Параметр", "Значение"])
    rows.append(["Ставка часа печати", settings["hour_rate"]])
    rows.append(["Реверс-моделирование", settings["reverse_price"]])
    rows.append(["Валюта", settings["currency"]])
    return rows


def build_all_sheets() -> dict[str, list[list[Any]]]:
    return {
        "Заказы": build_orders_sheet(),
        "Клиенты": build_customers_sheet(),
        "Цены": build_prices_sheet(),
    }
