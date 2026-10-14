"""Электроника в заказе: компоненты, новые колонки, себестоимость с компонентами."""
import sqlite3

import db


def _order(**extra) -> int:
    return db.add_order({"client": "К", "contact": "", "cost": 0, "price": 1000, **extra})


def test_new_order_defaults_to_print_only(temp_db):
    o = db.get_order(_order())
    assert o["has_print"] == 1 and o["has_electronics"] == 0
    assert o["soldering_price"] == 0 and o["firmware_price"] == 0 and o["components_markup"] == 0


def test_components_markup_setting_default(temp_db):
    assert db.get_settings()["components_markup"] == 20


def test_set_components_replaces_and_skips_blank_names(temp_db):
    oid = _order(has_electronics=1)
    db.set_components(oid, [{"name": "ESP32", "qty": 2, "unit_cost": 450}, {"name": "  ", "qty": 1, "unit_cost": 9}])
    db.set_components(oid, [{"name": " Лента WS2812 ", "qty": 1.5, "unit_cost": 300}])
    rows = db.list_components(oid)
    assert [(r["name"], r["qty"], r["unit_cost"]) for r in rows] == [("Лента WS2812", 1.5, 300)]


def test_component_catalog_keeps_latest_price(temp_db):
    a, b = _order(), _order()
    db.set_components(a, [{"name": "ESP32", "qty": 1, "unit_cost": 450}, {"name": "Экран", "qty": 1, "unit_cost": 700}])
    db.set_components(b, [{"name": "ESP32", "qty": 1, "unit_cost": 500}])
    assert db.component_catalog() == {"ESP32": 500, "Экран": 700}


def test_components_by_order_groups_rows(temp_db):
    a = _order()
    db.set_components(a, [{"name": "ESP32", "qty": 1, "unit_cost": 450}, {"name": "Провод", "qty": 3, "unit_cost": 10}])
    grouped = db.components_by_order()
    assert [r["name"] for r in grouped[a]] == ["ESP32", "Провод"]


def test_expense_adds_components_and_skips_plastic_without_print(temp_db):
    s = {**db.get_settings(), "purchase_prices": {"PLA": 2}}
    assert db.expense("PLA", 100, 1, 1, s, components_purchase=900)["total"] == 1100
    off = db.expense("PLA", 100, 1, 1, s, components_purchase=900, has_print=False)
    assert off["plastic"] == 0 and off["total"] == 900


def test_recalc_costs_keeps_components(temp_db):
    db.set_setting("purchase_prices", {"PLA": 2})
    oid = _order(material="PLA", weight_g=100, qty=1, has_electronics=1)
    db.set_components(oid, [{"name": "ESP32", "qty": 2, "unit_cost": 450}])
    db.recalc_costs()
    assert db.get_order(oid)["cost"] == 200 + 900
    db.update_order(oid, has_electronics=0)
    db.recalc_costs()
    assert db.get_order(oid)["cost"] == 200


def test_renumber_and_delete_carry_components(temp_db, tmp_path):
    oid = _order()
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 450}])
    db.renumber_order(oid, 50, storage_dir=tmp_path)
    assert [r["name"] for r in db.list_components(50)] == ["ESP32"]
    db.delete_order(50)
    assert db.list_components(50) == []


def test_delete_customer_with_orders_removes_components(temp_db):
    oid = _order()
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 450}])
    db.delete_customer(db.get_order(oid)["customer_id"], delete_orders=True)
    assert db.list_components(oid) == []


def test_fingerprint_changes_on_components(temp_db):
    oid = _order()
    before = db.change_fingerprint()
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 450}])
    assert db.change_fingerprint() != before


def test_search_finds_order_by_component(temp_db):
    oid = _order()
    db.set_components(oid, [{"name": "ESP32-WROOM", "qty": 1, "unit_cost": 450}])
    assert [o["id"] for o in db.search_orders("WROOM")] == [oid]


def test_stats_grams_skip_orders_without_print(temp_db):
    _order(material="PLA", weight_g=100, qty=1)
    _order(material="PLA", weight_g=999, qty=1, has_print=0, has_electronics=1)
    s = db.stats()
    assert s["grams"] == 100 and s["materials"] == [("PLA", 100)]


def test_old_database_migrates_without_changing_prices(temp_db):
    """База старой версии: колонок электроники нет — init() добавляет их, цены и себестоимость те же."""
    oid = _order(material="PLA", weight_g=100, qty=1, cost=150, price=777)
    with sqlite3.connect(temp_db) as c:
        c.execute("DROP TABLE order_components")
        for col in ("has_print", "has_electronics", "soldering_price", "firmware_price", "components_markup"):
            c.execute(f"ALTER TABLE orders DROP COLUMN {col}")
    db.init()
    o = db.get_order(oid)
    assert (o["has_print"], o["has_electronics"], o["price"], o["cost"]) == (1, 0, 777, 150)
    assert db.list_components(oid) == []
