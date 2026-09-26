"""Предоплата в карточке/новом заказе, закупка пластика в «Ценах», прибыль (без запуска окна)."""
import db
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen
from app.screens.prices_screen import PricesScreen


def _texts(column):
    return [c.value for row in column.controls for c in getattr(row, "controls", []) if hasattr(c, "value")]


def _setup():
    db.set_setting("materials", {"PLA": 4})
    db.set_setting("purchase_prices", {"PLA": 1.5})
    db.set_setting("hour_rate", 50)
    db.set_setting("defect_percent", 0)


def test_new_order_saves_prepayment_and_cost(temp_db, monkeypatch):
    _setup()
    created = []
    screen = NewOrderScreen(on_created=created.append)
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.client_field.value = "Иван"
    screen.material_dd.value = "PLA"
    screen.weight_field.value = "100"
    screen.hours_field.value = "2"
    screen.prepayment_field.value = "200"
    screen._recalc(None)
    assert "Прибыль" in _texts(screen.profit_column)
    screen._on_save(None)
    order = db.get_order(created[0])
    assert order["prepayment"] == 200
    assert order["price"] == 500
    assert order["cost"] == 150  # только закупка: 100 г × 1500/кг


def test_order_detail_prepayment_updates_remaining(temp_db, monkeypatch):
    _setup()
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 1000})
    screen = OrderDetailScreen(order_id, on_back=lambda: None)
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.refresh()
    screen.prepayment_field.value = "400"
    screen._on_prepayment_blur(None)
    order = db.get_order(order_id)
    assert order["prepayment"] == 400 and not order["paid"]
    assert any("600" in (t or "") for t in _texts(screen.payment_summary))


def test_order_detail_full_prepayment_marks_paid(temp_db, monkeypatch):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 1000})
    screen = OrderDetailScreen(order_id, on_back=lambda: None)
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.refresh()
    screen.prepayment_field.value = "1000"
    screen._on_prepayment_blur(None)
    assert db.get_order(order_id)["paid"] == 1


def test_order_detail_rejects_non_numeric_prepayment(temp_db, monkeypatch):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 1000})
    screen = OrderDetailScreen(order_id, on_back=lambda: None)
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.refresh()
    screen.prepayment_field.value = "много"
    screen._on_prepayment_blur(None)
    assert screen.prepayment_field.error_text
    assert db.get_order(order_id)["prepayment"] == 0


def test_prices_screen_adds_plastic_with_purchase_and_recalcs_costs(temp_db, monkeypatch):
    db.set_setting("hour_rate", 0)
    order_id = db.add_order({"client": "К", "contact": "", "material": "TPU", "weight_g": 100, "qty": 1,
                              "cost": 0, "price": 900})
    screen = PricesScreen()
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.new_material_name.value = "TPU"
    screen.new_material_purchase.value = "2"
    screen.new_material_price.value = "7"
    screen._add_material(None)
    settings = db.get_settings()
    assert settings["materials"]["TPU"] == 7
    assert settings["purchase_prices"]["TPU"] == 2
    assert db.get_order(order_id)["cost"] == 200


def test_prices_screen_saves_payment_text(temp_db, monkeypatch):
    screen = PricesScreen()
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.refresh()
    screen.payment_field.value = "  89001234567 Иван банк: Сбер "
    screen._save_scalars(None)
    assert db.get_settings()["payment_text"] == "89001234567 Иван банк: Сбер"
