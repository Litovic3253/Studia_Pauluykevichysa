"""Тесты редактирования имени/контакта в карточке клиента (без запуска окна)."""
import flet as ft

import db
from app.screens.customers_screen import CustomersScreen


def _walk(control):
    yield control
    for attr in ("content", "controls"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for c in child:
                yield from _walk(c)
        elif isinstance(child, ft.Control):
            yield from _walk(child)


def _open(screen, customer_id):
    screen.selected_customer_id = customer_id
    screen._render_detail(customer_id)


def test_editing_name_and_contact_saves_and_keeps_fields(temp_db):
    order_id = db.add_order({"client": "Иван", "contact": "@ivan", "cost": 0, "price": 0})
    cid = db.get_order(order_id)["customer_id"]
    screen = CustomersScreen()
    _open(screen, cid)
    name_field = screen._name_field

    name_field.value = "Иван Петров"
    screen._contact_field.value = "+7999"
    screen._save_identity(cid)

    assert db.get_customer(cid)["name"] == "Иван Петров"
    assert db.get_order(order_id)["client"] == "Иван Петров"
    assert db.get_order(order_id)["contact"] == "+7999"
    assert screen._name_field is name_field  # поле не пересоздано — фокус/ввод не теряются
    assert "Иван Петров" in [c.value for c in _walk(screen.detail_column) if isinstance(c, ft.Text)]


def test_empty_name_shows_error_and_is_not_saved(temp_db, monkeypatch):
    cid = db.find_or_create_customer("Иван", "")
    screen = CustomersScreen()
    _open(screen, cid)
    monkeypatch.setattr(screen, "update", lambda: None)

    screen._name_field.value = "  "
    screen._save_identity(cid)

    assert db.get_customer(cid)["name"] == "Иван"
    assert screen._name_field.error_text


def test_detail_card_has_delete_button(temp_db):
    cid = db.find_or_create_customer("Иван", "")
    screen = CustomersScreen()
    _open(screen, cid)
    labels = [c.text for c in _walk(screen.detail_column) if isinstance(c, ft.OutlinedButton)]
    assert "Удалить клиента" in labels


def test_confirm_delete_removes_customer_and_closes_card(temp_db, monkeypatch):
    order_id = db.add_order({"client": "Иван", "contact": "", "cost": 0, "price": 0})
    cid = db.get_order(order_id)["customer_id"]
    screen = CustomersScreen()
    _open(screen, cid)

    screen._delete_customer(cid, delete_orders=False)

    assert db.get_customer(cid) is None
    assert db.get_order(order_id) is not None
    assert screen.selected_customer_id is None
    assert screen.detail_card.visible is False


def test_customer_detail_scrolls(temp_db):
    screen = CustomersScreen()
    assert screen.detail_column.scroll is not None


def test_compact_mode_shows_list_or_detail_not_both(temp_db):
    cid = db.find_or_create_customer("Иван", "")
    screen = CustomersScreen()
    screen.set_compact(True)
    assert screen.list_panel.visible is True

    screen._open_customer(cid)
    assert screen.list_panel.visible is False
    assert screen.detail_card.visible is True

    screen._close_customer()
    assert screen.list_panel.visible is True
    assert screen.detail_card.visible is False


def test_wide_mode_shows_list_and_detail_together(temp_db):
    cid = db.find_or_create_customer("Иван", "")
    screen = CustomersScreen()
    screen._open_customer(cid)
    assert screen.list_panel.visible is True
    assert screen.detail_card.visible is True
    assert screen.placeholder.visible is False


def test_history_row_opens_order(temp_db):
    order_id = db.add_order({"client": "Иван", "contact": "", "cost": 0, "price": 0})
    cid = db.get_order(order_id)["customer_id"]
    opened = []
    screen = CustomersScreen(on_open_order=opened.append)
    screen._open_customer(cid)
    clickable = [c for c in _walk(screen.detail_column) if isinstance(c, ft.Container) and c.on_click]
    clickable[0].on_click(None)
    assert opened == [order_id]
