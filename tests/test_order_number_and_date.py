"""Редактирование номера заказа и даты создания."""
import pytest

import db


def _order(**extra) -> int:
    return db.add_order({"client": "К", "contact": "", "cost": 0, "price": 1000, **extra})


def test_renumber_moves_order_and_links(temp_db, tmp_path):
    storage = tmp_path / "files_storage"
    oid = _order()
    (storage / str(oid)).mkdir(parents=True)
    (storage / str(oid) / "model.stl").write_text("solid")
    db.add_attachment(oid, "local", local_path=str(storage / str(oid) / "model.stl"), filename="model.stl",
                      file_type="document")
    spool = db.add_spool("PLA", "белый", 1000)
    db.use_spool(spool, 50, order_id=oid)

    db.renumber_order(oid, 25, storage_dir=storage)

    assert db.get_order(oid) is None
    assert db.get_order(25)["client"] == "К"
    att = db.list_attachments(25)[0]
    assert att["local_path"] == str(storage / "25" / "model.stl")
    assert (storage / "25" / "model.stl").read_text() == "solid"
    assert not (storage / str(oid)).exists()
    assert db.order_usage(25)["grams"] == 50


def test_renumber_rejects_taken_or_invalid_number(temp_db, tmp_path):
    first, second = _order(), _order()
    with pytest.raises(ValueError, match="занят"):
        db.renumber_order(first, second, storage_dir=tmp_path)
    with pytest.raises(ValueError):
        db.renumber_order(first, 0, storage_dir=tmp_path)
    assert db.get_order(first) and db.get_order(second)


def test_new_orders_continue_after_largest_number(temp_db, tmp_path):
    oid = _order()
    db.renumber_order(oid, 100, storage_dir=tmp_path)
    assert _order() == 101


def test_renumber_to_smaller_free_number(temp_db, tmp_path):
    ids = [_order() for _ in range(3)]
    db.delete_order(ids[0])
    db.renumber_order(ids[2], ids[0], storage_dir=tmp_path)
    assert db.get_order(ids[0]) and not db.get_order(ids[2])
    assert _order() == ids[2] + 1  # счётчик не откатывается назад


def test_set_order_created_keeps_time(temp_db):
    oid = _order()
    time_part = db.get_order(oid)["created_at"][10:]
    db.set_order_created(oid, "2026-01-15")
    assert db.get_order(oid)["created_at"] == "2026-01-15" + time_part


class _FakePage:
    def __init__(self):
        self.opened = []

    def open(self, control):
        self.opened.append(control)

    def close(self, control):
        self.opened.remove(control)


def _open_edit_dialog(monkeypatch, order_id, tmp_path):
    from app.screens import order_detail
    monkeypatch.setattr(order_detail, "LOCAL_STORAGE", tmp_path)
    screen = order_detail.OrderDetailScreen(order_id, on_back=lambda: None)
    monkeypatch.setattr(screen, "update", lambda: None)
    page = _FakePage()
    monkeypatch.setattr(type(screen), "page", property(lambda self: page))
    screen.refresh()
    screen._on_edit_number_date(None)
    dialog = page.opened[-1]
    monkeypatch.setattr(dialog, "update", lambda: None)
    number_field, date_field = dialog.content.content.controls
    save = dialog.actions[-1].on_click
    return screen, page, dialog, number_field, date_field, save


def test_edit_dialog_changes_number_and_date(temp_db, monkeypatch, tmp_path):
    oid = _order()
    screen, page, dialog, number_field, date_field, save = _open_edit_dialog(monkeypatch, oid, tmp_path)
    number_field.value = "42"
    date_field.value = "01.03.2026"
    save(None)
    assert dialog not in page.opened
    assert screen.order_id == 42
    assert db.get_order(42)["created_at"].startswith("2026-03-01")


def test_edit_dialog_shows_error_for_taken_number(temp_db, monkeypatch, tmp_path):
    oid, other = _order(), _order()
    screen, page, dialog, number_field, date_field, save = _open_edit_dialog(monkeypatch, oid, tmp_path)
    number_field.value = str(other)
    save(None)
    assert dialog in page.opened and "занят" in number_field.error_text
    assert screen.order_id == oid


def test_created_date_without_year_is_in_the_past():
    from datetime import date, timedelta

    from app.screens.order_detail import _parse_created_date
    yesterday = date.today() - timedelta(days=1)
    assert _parse_created_date(yesterday.strftime("%d.%m")) == yesterday.isoformat()
    assert _parse_created_date("сегодня") == date.today().isoformat()
    assert _parse_created_date("ерунда") is None
