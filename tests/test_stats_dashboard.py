"""Дашборд «Статистика»: порядок виджетов, перестановка, сохранение, отрисовка (без окна)."""
import db
from app.screens import stats_screen
from app.screens.stats_screen import StatsScreen, load_order, move, shift


def test_move_puts_widget_in_targets_place():
    assert move(["a", "b", "c", "d"], "d", "b") == ["a", "d", "b", "c"]
    assert move(["a", "b", "c", "d"], "a", "c") == ["b", "c", "a", "d"]
    assert move(["a", "b"], "a", "a") == ["a", "b"]


def test_shift_moves_one_step_and_stops_at_edges():
    assert shift(["a", "b", "c"], "b", -1) == ["b", "a", "c"]
    assert shift(["a", "b", "c"], "b", 1) == ["a", "c", "b"]
    assert shift(["a", "b", "c"], "a", -1) == ["a", "b", "c"]


def test_load_order_drops_unknown_and_appends_new_widgets(temp_db):
    db.set_setting("stats_layout", ["profit", "ghost", "money"])
    order = load_order()
    assert order[:2] == ["profit", "money"]
    assert set(order) == set(stats_screen.WIDGETS)


def test_dashboard_renders_every_widget_and_saves_new_order(temp_db, monkeypatch):
    oid = db.add_order({"client": "К", "contact": "", "material": "PLA", "weight_g": 50, "qty": 2,
                         "cost": 100, "price": 1000, "deadline": "2020-01-01"})
    db.update_order(oid, prepayment=300)
    db.add_spool("PLA", "чёрный", 1000)
    screen = StatsScreen()
    monkeypatch.setattr(screen, "update", lambda: None)
    assert [slot.key for slot in screen.board.controls] == stats_screen.DEFAULT_ORDER

    screen._apply_order(move(screen.order, "stock", "activity"), landed="stock")
    assert db.get_settings()["stats_layout"][0] == "stock"
    assert screen.board.controls[0].key == "stock"
