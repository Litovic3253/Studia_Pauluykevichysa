"""Процент брака на экранах: новый заказ, карточка заказа, «Цены» (без запуска окна)."""
import db
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen
from app.screens.prices_screen import PricesScreen


def _prices(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 50)


def test_new_order_prefills_default_defect_and_saves_it(temp_db, monkeypatch):
    _prices(temp_db)
    db.set_setting("defect_percent", 10)
    created = []
    screen = NewOrderScreen(on_created=created.append)
    monkeypatch.setattr(screen, "update", lambda: None)
    assert screen.defect_field.value == "10"

    screen.client_field.value = "Иван"
    screen.material_dd.value = "PLA"
    screen.weight_field.value = "100"
    screen.hours_field.value = "2"
    screen._recalc(None)
    assert "Брак 10%" in screen.price_preview.value

    screen._on_save(None)

    order = db.get_order(created[0])
    assert order["defect_percent"] == 10
    assert order["price"] == 550  # печать 500 + брак 10%


def test_order_detail_changing_defect_recalculates_price(temp_db, monkeypatch):
    _prices(temp_db)
    order_id = db.add_order({"client": "К", "contact": "", "material": "PLA", "weight_g": 100,
                              "print_hours": 2, "qty": 1, "cost": 500, "price": 500})
    screen = OrderDetailScreen(order_id, on_back=lambda: None)
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.refresh()
    assert screen.defect_field.value == "0"

    screen.defect_field.value = "20"
    screen._on_price_fields_blur(None)

    order = db.get_order(order_id)
    assert order["defect_percent"] == 20
    assert order["price"] == 600
    assert "Брак 20%" in screen.price_text.value


def test_prices_screen_saves_default_defect(temp_db, monkeypatch):
    screen = PricesScreen()
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.defect_field.value = "12,5"
    screen._save_scalars(None)
    assert db.get_settings()["defect_percent"] == 12.5
