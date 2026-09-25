"""Тесты редактирования имени/контакта в карточке клиента (без запуска окна)."""
import db
from app.screens.customers_screen import CustomersScreen


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
    assert screen.detail_column.controls[0].value == "Иван Петров"


def test_empty_name_shows_error_and_is_not_saved(temp_db, monkeypatch):
    cid = db.find_or_create_customer("Иван", "")
    screen = CustomersScreen()
    _open(screen, cid)
    monkeypatch.setattr(screen, "update", lambda: None)

    screen._name_field.value = "  "
    screen._save_identity(cid)

    assert db.get_customer(cid)["name"] == "Иван"
    assert screen._name_field.error_text
