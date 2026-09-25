"""Регрессионные тесты текущего поведения db.py, до добавления customers/attachments."""
import db


def test_wal_mode_is_enabled(temp_db):
    with db._conn() as c:
        mode = c.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_add_and_get_order_roundtrip(temp_db):
    order_id = db.add_order({
        "client": "Иван", "contact": "@ivan", "material": "PLA",
        "weight_g": 50, "print_hours": 1.5, "qty": 2, "cost": 100, "price": 150,
    })
    order = db.get_order(order_id)
    assert order["client"] == "Иван"
    assert order["status"] == "new"
    assert order["paid"] == 0


def test_update_order_changes_fields(temp_db):
    order_id = db.add_order({"client": "Иван", "contact": "", "cost": 0, "price": 0})
    db.update_order(order_id, status="printing", paid=1)
    order = db.get_order(order_id)
    assert order["status"] == "printing"
    assert order["paid"] == 1


def test_list_orders_active_excludes_delivered(temp_db):
    active_id = db.add_order({"client": "A", "contact": "", "cost": 0, "price": 0})
    done_id = db.add_order({"client": "B", "contact": "", "cost": 0, "price": 0})
    db.update_order(done_id, status="delivered")
    active_ids = {o["id"] for o in db.list_orders("active")}
    assert active_id in active_ids
    assert done_id not in active_ids


def test_settings_roundtrip(temp_db):
    db.set_setting("hour_rate", 75)
    assert db.get_settings()["hour_rate"] == 75


def test_theme_mode_defaults_to_system(temp_db):
    assert db.get_settings()["theme_mode"] == "system"


def test_theme_mode_can_be_changed(temp_db):
    db.set_setting("theme_mode", "dark")
    assert db.get_settings()["theme_mode"] == "dark"


def test_list_orders_all_returns_every_order_unordered_by_limit(temp_db):
    for i in range(3):
        db.add_order({"client": f"Клиент {i}", "contact": "", "cost": 0, "price": 0})
    orders = db.list_orders_all()
    assert len(orders) == 3
    assert [o["id"] for o in orders] == sorted(o["id"] for o in orders)


def test_default_defect_percent_setting_is_10(temp_db):
    assert db.get_settings()["defect_percent"] == 10


def test_orders_without_defect_percent_default_to_zero(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    assert db.get_order(order_id)["defect_percent"] == 0


def test_init_migrates_old_orders_table_without_defect_column(temp_db):
    import sqlite3
    order_id = db.add_order({"client": "Старый", "contact": "", "cost": 0, "price": 500})
    conn = sqlite3.connect(temp_db)
    conn.execute("ALTER TABLE orders DROP COLUMN defect_percent")  # база до появления брака
    conn.commit()
    conn.close()

    db.init()

    order = db.get_order(order_id)
    assert order["defect_percent"] == 0
    assert order["price"] == 500
