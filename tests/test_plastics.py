"""Справочник пластиков (app/plastics.py) и учёт катушек (db)."""
import pytest

import db
from app import plastics


def test_all_sixteen_plastics_are_embedded():
    assert len(plastics.PLASTICS) == 16
    names = plastics.names()
    assert "PLA Basic" in names and "PA6-CF" in names


def test_level_maps_words_to_scale():
    assert plastics.level("Низкая") == 1
    assert plastics.level("Средняя") == 2
    assert plastics.level("Средняя/высокая") == 2.5
    assert plastics.level("Высокая") == 3
    assert plastics.level("Очень высокая") == 4
    assert plastics.level("Экстремально высокая") == 5
    assert plastics.level("непонятно") == 0


def test_quick_choice_family_token_matches_family_but_not_composites():
    need = next(q for q in plastics.QUICK_CHOICE if q["need"].startswith("Клипсу"))
    matched = plastics.matching(need)
    assert "PLA Tough+" in matched
    assert "PETG Basic" in matched and "PETG HF" in matched
    assert "PETG-CF" not in matched


def test_spool_remaining_goes_down_with_usage(temp_db):
    sid = db.add_spool("PLA Basic", "белый", 1000)
    db.use_spool(sid, 250)
    db.use_spool(sid, 100.5)
    spool = db.get_spool(sid)
    assert spool["remaining_g"] == pytest.approx(649.5)


def test_stock_by_plastic_sums_active_spools(temp_db):
    a = db.add_spool("PLA Basic", "белый", 1000)
    db.add_spool("PLA Basic", "чёрный", 500)
    db.add_spool("PETG HF", "серый", 1000)
    db.use_spool(a, 300)
    stock = db.stock_by_plastic()
    assert stock["PLA Basic"] == {"remaining_g": 1200, "spools": 2}
    assert stock["PETG HF"]["remaining_g"] == 1000


def test_archived_spool_not_counted_in_stock(temp_db):
    sid = db.add_spool("ABS", "", 1000)
    db.archive_spool(sid)
    assert "ABS" not in db.stock_by_plastic()
    assert db.list_spools() == []
    assert len(db.list_spools(include_archived=True)) == 1


def test_use_spool_rejects_non_positive_grams(temp_db):
    sid = db.add_spool("ABS", "", 1000)
    with pytest.raises(ValueError):
        db.use_spool(sid, 0)


def test_order_can_be_written_off_only_once(temp_db):
    sid = db.add_spool("PLA Basic", "белый", 1000)
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    db.use_spool(sid, 200, order_id=order_id)
    with pytest.raises(ValueError):
        db.use_spool(sid, 200, order_id=order_id)
    usage = db.order_usage(order_id)
    assert usage["grams"] == 200 and usage["spool_id"] == sid


def test_undo_usage_returns_grams(temp_db):
    sid = db.add_spool("PLA Basic", "белый", 1000)
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    uid = db.use_spool(sid, 200, order_id=order_id)
    db.undo_usage(uid)
    assert db.get_spool(sid)["remaining_g"] == 1000
    assert db.order_usage(order_id) is None


def test_set_remaining_after_weighing(temp_db):
    sid = db.add_spool("PLA Basic", "белый", 1000)
    db.use_spool(sid, 100)
    db.set_spool_remaining(sid, 700)
    assert db.get_spool(sid)["remaining_g"] == 700
    assert db.list_usage()[0]["note"] == "сверка остатка"


def test_spool_totals(temp_db):
    a = db.add_spool("PLA Basic", "белый", 1000)
    db.add_spool("PETG HF", "", 750)
    db.use_spool(a, 250)
    assert db.spool_totals() == {"loaded_g": 1750, "used_g": 250, "remaining_g": 1500, "spools": 2}


def test_spools_change_fingerprint(temp_db):
    before = db.change_fingerprint()
    sid = db.add_spool("PLA Basic", "белый", 1000)
    mid = db.change_fingerprint()
    assert mid != before
    db.use_spool(sid, 10)
    assert db.change_fingerprint() != mid
