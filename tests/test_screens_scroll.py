"""Длинные формы должны прокручиваться, иначе нижние кнопки (например, «Удалить заказ») уезжают за край окна."""
import db
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen


def test_order_detail_scrolls(temp_db):
    order_id = db.add_order({"client": "Иван", "contact": "", "cost": 0, "price": 0})
    assert OrderDetailScreen(order_id, on_back=lambda: None).scroll is not None


def test_new_order_scrolls(temp_db):
    assert NewOrderScreen(on_created=lambda i: None).scroll is not None
