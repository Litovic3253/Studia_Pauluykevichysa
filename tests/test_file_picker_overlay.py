"""Регрессия: FilePicker не должен накапливаться в page.overlay при повторном монтировании экрана."""
import db
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen


class _FakePage:
    def __init__(self):
        self.overlay = []

    def update(self, *controls) -> None:
        pass


def test_order_detail_remount_does_not_duplicate_file_picker(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    screen = OrderDetailScreen(order_id=order_id, on_back=lambda: None)
    page = _FakePage()
    screen.page = page

    screen.did_mount()
    screen.did_mount()  # повторное монтирование без предварительного unmount

    assert page.overlay.count(screen.file_picker) == 1


def test_order_detail_will_unmount_removes_file_picker(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    screen = OrderDetailScreen(order_id=order_id, on_back=lambda: None)
    page = _FakePage()
    screen.page = page
    screen.did_mount()

    screen.will_unmount()

    assert screen.file_picker not in page.overlay


def test_new_order_repeated_tab_visits_do_not_duplicate_file_picker(temp_db):
    screen = NewOrderScreen(on_created=lambda order_id: None)
    page = _FakePage()
    screen.page = page

    screen.did_mount()
    screen.did_mount()
    screen.did_mount()  # имитация трёх заходов на вкладку «Новый заказ»

    assert page.overlay.count(screen.file_picker) == 1
