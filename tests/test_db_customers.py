"""Тесты для таблицы customers и автопривязки заказов к клиентам."""
import db


def test_find_or_create_customer_creates_new(temp_db):
    cid = db.find_or_create_customer("Иван Петров", "+79990000000")
    customer = db.get_customer(cid)
    assert customer["name"] == "Иван Петров"
    assert customer["contact"] == "+79990000000"


def test_find_or_create_customer_reuses_existing_case_insensitive(temp_db):
    cid1 = db.find_or_create_customer("Иван Петров", "+79990000000")
    cid2 = db.find_or_create_customer(" иван петров ", " +79990000000 ")
    assert cid1 == cid2


def test_add_order_links_customer_automatically(temp_db):
    order_id = db.add_order({
        "client": "Мария Сидорова", "contact": "@maria", "material": "PLA",
        "weight_g": 100, "print_hours": 2, "qty": 1, "cost": 500, "price": 600,
    })
    order = db.get_order(order_id)
    assert order["customer_id"] is not None
    customer = db.get_customer(order["customer_id"])
    assert customer["name"] == "Мария Сидорова"


def test_second_order_same_client_reuses_customer(temp_db):
    first = db.add_order({"client": "Пётр", "contact": "111", "cost": 0, "price": 0})
    second = db.add_order({"client": "Пётр", "contact": "111", "cost": 0, "price": 0})
    o1, o2 = db.get_order(first), db.get_order(second)
    assert o1["customer_id"] == o2["customer_id"]


def test_list_customers_aggregates_orders(temp_db):
    order_id = db.add_order({"client": "Клиент", "contact": "c1", "cost": 100, "price": 200})
    db.update_order(order_id, paid=1)
    rows = db.list_customers()
    assert len(rows) == 1
    assert rows[0]["orders_count"] == 1
    assert rows[0]["paid_total"] == 200
    assert rows[0]["debt_total"] == 0


def test_list_customers_search_filters_by_name(temp_db):
    db.add_order({"client": "Анна", "contact": "a", "cost": 0, "price": 0})
    db.add_order({"client": "Борис", "contact": "b", "cost": 0, "price": 0})
    rows = db.list_customers("анн")
    assert len(rows) == 1
    assert rows[0]["name"] == "Анна"


def test_update_customer_changes_notes(temp_db):
    cid = db.find_or_create_customer("Клиент", "c")
    db.update_customer(cid, notes="Постоянный клиент")
    assert db.get_customer(cid)["notes"] == "Постоянный клиент"


def test_migrate_customers_v1_groups_legacy_orders(temp_db):
    # Заказ, созданный «по-старому», без customer_id (имитирует БД до этой миграции).
    with db._conn() as c:
        c.execute(
            "INSERT INTO orders (created_at, client, contact, cost, price) VALUES (?, ?, ?, ?, ?)",
            ("2026-01-01T00:00:00", "Анна Легаси", "89990000000", 0, 0),
        )
        c.execute("DELETE FROM settings WHERE key = 'customers_v1'")
    db.init()  # повторный init должен смигрировать старый заказ
    rows = db.list_customers()
    assert any(r["name"] == "Анна Легаси" for r in rows)


def test_rename_customer_updates_customer_and_its_orders(temp_db):
    order_id = db.add_order({"client": "Иван", "contact": "@ivan", "cost": 0, "price": 0})
    other_id = db.add_order({"client": "Пётр", "contact": "", "cost": 0, "price": 0})
    cid = db.get_order(order_id)["customer_id"]

    db.rename_customer(cid, "Иван Петров", "+79990000000")

    customer = db.get_customer(cid)
    assert customer["name"] == "Иван Петров"
    assert customer["contact"] == "+79990000000"
    order = db.get_order(order_id)
    assert order["client"] == "Иван Петров"
    assert order["contact"] == "+79990000000"
    assert db.get_order(other_id)["client"] == "Пётр"


def test_rename_customer_rejects_empty_name(temp_db):
    cid = db.find_or_create_customer("Иван", "")
    try:
        db.rename_customer(cid, "   ", "")
        assert False, "пустое имя должно отклоняться"
    except ValueError:
        pass
    assert db.get_customer(cid)["name"] == "Иван"


def test_rename_customer_changes_fingerprint(temp_db):
    cid = db.find_or_create_customer("Иван", "")
    before = db.change_fingerprint()
    db.rename_customer(cid, "Иван П.", "")
    assert db.change_fingerprint() != before


def test_delete_customer_keeps_orders_unlinked_by_default(temp_db):
    order_id = db.add_order({"client": "Иван", "contact": "", "cost": 0, "price": 0})
    cid = db.get_order(order_id)["customer_id"]

    db.delete_customer(cid)

    assert db.get_customer(cid) is None
    order = db.get_order(order_id)
    assert order is not None
    assert order["customer_id"] is None
    assert order["client"] == "Иван"


def test_delete_customer_with_orders_removes_them_and_their_attachments(temp_db):
    order_id = db.add_order({"client": "Иван", "contact": "", "cost": 0, "price": 0})
    other_id = db.add_order({"client": "Пётр", "contact": "", "cost": 0, "price": 0})
    db.add_attachment(order_id, "local", local_path="C:/x.stl", filename="x.stl", file_type="document")
    cid = db.get_order(order_id)["customer_id"]

    db.delete_customer(cid, delete_orders=True)

    assert db.get_customer(cid) is None
    assert db.get_order(order_id) is None
    assert db.list_attachments(order_id) == []
    assert db.get_order(other_id) is not None
