"""Цена заказа с электроникой: компоненты с наценкой, пайка, прошивка; брак — только от печати."""
import db
import pricing


def _setup():
    db.set_setting("materials", {"PLA": 4})
    db.set_setting("purchase_prices", {"PLA": 2})
    db.set_setting("hour_rate", 50)


PARTS = [{"name": "ESP32", "qty": 2, "unit_cost": 450}, {"name": "Экран", "qty": 1, "unit_cost": 100}]


def test_old_calls_unchanged(temp_db):
    _setup()
    p = pricing.calc_price("PLA", 100, 2, 1)
    assert p["price"] == 500 and p["cost"] == 200 and p["components_cost"] == 0


def test_print_plus_electronics(temp_db):
    _setup()
    p = pricing.calc_price("PLA", 100, 2, 1, defect_percent=10, has_electronics=True, components=PARTS,
                           markup=20, soldering=500, firmware=1500)
    assert p["components_purchase"] == 1000
    assert p["components_cost"] == 1200
    assert p["defect_cost"] == 50  # 10% только от печати (400 + 100)
    assert p["price"] == 550 + 1200 + 500 + 1500
    assert p["cost"] == 200 + 1000
    assert p["profit"] == p["price"] - 1200


def test_qty_multiplies_only_print(temp_db):
    _setup()
    p = pricing.calc_price("PLA", 100, 0, 3, has_electronics=True, components=PARTS, soldering=500)
    assert p["material_cost"] == 1200 and p["components_purchase"] == 1000 and p["soldering_cost"] == 500


def test_disabled_parts_are_ignored(temp_db):
    _setup()
    only_el = pricing.calc_price("PLA", 100, 2, 1, has_print=False, has_electronics=True, components=PARTS)
    assert only_el["material_cost"] == 0 and only_el["time_cost"] == 0 and only_el["price"] == 1000
    assert only_el["cost"] == 1000
    only_print = pricing.calc_price("PLA", 100, 2, 1, components=PARTS, soldering=500)
    assert only_print["components_cost"] == 0 and only_print["soldering_cost"] == 0 and only_print["price"] == 500


def test_calc_order_reads_components_from_db(temp_db):
    _setup()
    oid = db.add_order({"client": "К", "contact": "", "material": "PLA", "weight_g": 100, "print_hours": 2,
                        "qty": 1, "cost": 0, "price": 0, "has_electronics": 1, "components_markup": 20,
                        "soldering_price": 500, "firmware_price": 1500})
    db.set_components(oid, PARTS)
    pricing.recalc_order_price(oid)
    o = db.get_order(oid)
    assert o["price"] == 500 + 1200 + 500 + 1500 and o["cost"] == 1200
