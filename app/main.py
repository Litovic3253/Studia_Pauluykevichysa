"""Точка входа Mochi Desktop — админ-панели, использующей общую с ботом orders.db."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import flet as ft
from dotenv import load_dotenv

import db
from app.live_sync import LiveSync
from app.screens.customers_screen import CustomersScreen
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen
from app.screens.orders_screen import OrdersScreen
from app.screens.prices_screen import PricesScreen
from app.screens.stats_screen import StatsScreen

load_dotenv(ROOT / ".env")


class OrdersSection(ft.Column):
    """Заказы: список, при клике на заказ показывает его карточку вместо списка."""

    def __init__(self):
        super().__init__(expand=True)
        self.list_screen = OrdersScreen(on_open_order=self._open_order)
        self.detail_screen: OrderDetailScreen | None = None
        self.controls = [self.list_screen]

    def _open_order(self, order_id: int) -> None:
        self.detail_screen = OrderDetailScreen(order_id=order_id, on_back=self._back_to_list)
        self.controls = [self.detail_screen]
        self.update()

    def _back_to_list(self) -> None:
        self.detail_screen = None
        self.list_screen.refresh()
        self.controls = [self.list_screen]
        self.update()

    def refresh(self) -> None:
        if self.detail_screen is not None:
            self.detail_screen.refresh()
        else:
            self.list_screen.refresh()


def main(page: ft.Page) -> None:
    page.title = "Mochi Desktop"
    page.window.width = 1200
    page.window.height = 800
    db.init()

    orders_section = OrdersSection()
    customers_screen = CustomersScreen()
    prices_screen = PricesScreen()
    stats_screen = StatsScreen()

    def go_to_orders_after_create(order_id: int) -> None:
        content.content = orders_section
        nav_rail.selected_index = 0
        page.update()
        orders_section._open_order(order_id)

    new_order_screen = NewOrderScreen(on_created=go_to_orders_after_create)

    sections = [orders_section, new_order_screen, customers_screen, prices_screen, stats_screen]
    content = ft.Container(content=orders_section, expand=True)

    def on_nav_change(e: ft.ControlEvent) -> None:
        content.content = sections[nav_rail.selected_index]
        page.update()

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.LIST_ALT, label="Заказы"),
            ft.NavigationRailDestination(icon=ft.Icons.ADD_BOX, label="Новый заказ"),
            ft.NavigationRailDestination(icon=ft.Icons.PEOPLE, label="Клиенты"),
            ft.NavigationRailDestination(icon=ft.Icons.SELL, label="Цены"),
            ft.NavigationRailDestination(icon=ft.Icons.BAR_CHART, label="Статистика"),
        ],
        on_change=on_nav_change,
    )

    def on_db_changed() -> None:
        orders_section.refresh()
        customers_screen.refresh()
        prices_screen.refresh()
        stats_screen.refresh()

    page.pubsub.subscribe(lambda _: on_db_changed())
    live_sync = LiveSync(on_change=lambda: page.pubsub.send_all("db_changed"), interval=3.0)
    live_sync.start()
    page.on_disconnect = lambda e: live_sync.stop()

    page.add(ft.Row([nav_rail, ft.VerticalDivider(width=1), content], expand=True))


if __name__ == "__main__":
    ft.app(target=main)
