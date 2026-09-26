"""Длинные формы должны прокручиваться, иначе нижние кнопки (например, «Удалить заказ») уезжают за край окна."""
import db
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen


def test_order_detail_scrolls(temp_db):
    order_id = db.add_order({"client": "Иван", "contact": "", "cost": 0, "price": 0})
    assert OrderDetailScreen(order_id, on_back=lambda: None).scroll is not None


def test_new_order_scrolls(temp_db):
    assert NewOrderScreen(on_created=lambda i: None).scroll is not None


def _walk(control):
    yield control
    for attr in ("controls", "content"):
        child = getattr(control, attr, None)
        for c in (child if isinstance(child, list) else [child] if child is not None else []):
            yield from _walk(c)


def _expanded_inside_wrap(root) -> list:
    """Flutter не умеет Expanded внутри Wrap — вместо контрола рисует серую заглушку."""
    import flet as ft
    bad = []
    for c in _walk(root):
        if isinstance(c, ft.Row) and c.wrap:
            bad += [child for child in c.controls if getattr(child, "expand", None)]
    return bad


def test_no_expanded_controls_inside_wrapping_rows(temp_db, monkeypatch):
    from app.screens.new_order import NewOrderScreen
    from app.screens.order_detail import OrderDetailScreen
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0, "weight_g": 10})
    detail = OrderDetailScreen(order_id, on_back=lambda: None)
    monkeypatch.setattr(detail, "update", lambda: None)
    detail.refresh()
    for screen in (NewOrderScreen(on_created=lambda _: None), detail):
        assert _expanded_inside_wrap(screen) == []
