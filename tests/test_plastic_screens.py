"""Экраны пластика и списание из заказа (без запуска окна)."""
import db
from app.screens.order_detail import OrderDetailScreen
from app.screens.plastics_screen import PlasticsScreen
from app.screens.spools_screen import SpoolsScreen


def test_plastics_quick_choice_puts_in_stock_first(temp_db):
    db.add_spool("PETG HF", "серый", 1000)
    screen = PlasticsScreen()
    need = next(q for q in screen_quick() if q["need"].startswith("Функциональный кронштейн"))
    screen.need = need
    names = [p["name"] for p in screen.visible_plastics(db.stock_by_plastic())]
    assert names[0] == "PETG HF"
    assert set(names) == {"PETG Basic", "PETG HF"}


def test_plastics_only_in_stock_filter(temp_db):
    db.add_spool("ABS", "", 1000)
    screen = PlasticsScreen()
    screen.only_in_stock = True
    assert [p["name"] for p in screen.visible_plastics(db.stock_by_plastic())] == ["ABS"]


def test_spools_screen_add_spool(temp_db):
    screen = SpoolsScreen()
    screen.plastic_dd.value = "PLA Basic"
    screen.color_field.value = "белый"
    screen.weight_field.value = "1000"
    screen._on_add(None)
    assert db.stock_by_plastic()["PLA Basic"]["remaining_g"] == 1000


def test_order_write_off_prefers_matching_family_and_blocks_second(temp_db):
    petg = db.add_spool("PETG HF", "", 1000)
    pla = db.add_spool("PLA Basic", "белый", 1000)
    order_id = db.add_order({"client": "К", "contact": "", "material": "PLA", "weight_g": 120, "qty": 2,
                              "cost": 0, "price": 0})
    screen = OrderDetailScreen(order_id, on_back=lambda: None)
    assert [s["id"] for s in screen.spools_for_order()] == [pla, petg]

    screen.write_off(pla, 240)
    screen.write_off(pla, 240)  # повтор не проходит

    assert db.get_spool(pla)["remaining_g"] == 760
    assert db.order_usage(order_id)["grams"] == 240


def screen_quick():
    from app import plastics
    return plastics.QUICK_CHOICE
