"""Тесты для таблицы attachments и миграции старого поля orders.file_id."""
import db


def test_add_and_list_attachment_local(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    att_id = db.add_attachment(
        order_id, "local", local_path="app/files_storage/1/model.stl",
        filename="model.stl", file_type="document",
    )
    attachments = db.list_attachments(order_id)
    assert len(attachments) == 1
    assert attachments[0]["id"] == att_id
    assert attachments[0]["source"] == "local"
    assert attachments[0]["filename"] == "model.stl"


def test_add_and_list_attachment_telegram(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    db.add_attachment(order_id, "telegram", file_id="ABC123", file_type="photo")
    attachments = db.list_attachments(order_id)
    assert attachments[0]["source"] == "telegram"
    assert attachments[0]["file_id"] == "ABC123"


def test_delete_attachment_removes_it(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    att_id = db.add_attachment(order_id, "local", local_path="x", filename="x", file_type="document")
    db.delete_attachment(att_id)
    assert db.list_attachments(order_id) == []


def test_get_attachment_returns_row(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    att_id = db.add_attachment(order_id, "local", local_path="x", filename="x", file_type="document")
    assert db.get_attachment(att_id)["id"] == att_id


def test_migrate_attachments_v1_moves_legacy_file_id(temp_db):
    order_id = db.add_order({
        "client": "К", "contact": "", "cost": 0, "price": 0,
        "file_id": "LEGACY_FILE", "file_type": "photo",
    })
    with db._conn() as c:
        c.execute("DELETE FROM settings WHERE key = 'attachments_v1'")
    db.init()  # повторный init должен смигрировать file_id в attachments
    attachments = db.list_attachments(order_id)
    assert len(attachments) == 1
    assert attachments[0]["source"] == "telegram"
    assert attachments[0]["file_id"] == "LEGACY_FILE"


def test_change_fingerprint_changes_on_new_order(temp_db):
    before = db.change_fingerprint()
    db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    after = db.change_fingerprint()
    assert before != after


def test_change_fingerprint_changes_on_new_attachment(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    before = db.change_fingerprint()
    db.add_attachment(order_id, "local", local_path="x", filename="x", file_type="document")
    after = db.change_fingerprint()
    assert before != after


def test_change_fingerprint_changes_on_order_update(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    before = db.change_fingerprint()
    db.update_order(order_id, status="printing", paid=1)
    after = db.change_fingerprint()
    assert before != after
