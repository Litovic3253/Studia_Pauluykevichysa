"""Точка входа Mochi Desktop — локальной панели управления заказами 3D-печати."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import flet as ft
from dotenv import load_dotenv

import db
from app import sheets_sync, theme
from app.excel_writer import export_to_excel
from app.live_sync import LiveSync
from app.screens.customers_screen import CustomersScreen
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen
from app.screens.orders_screen import OrdersScreen
from app.screens.prices_screen import PricesScreen
from app.screens.stats_screen import StatsScreen
from paths import DATA_DIR

load_dotenv(DATA_DIR / ".env")


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
        if self.page:
            self.update()

    def _back_to_list(self) -> None:
        self.detail_screen = None
        self.list_screen.refresh()
        self.controls = [self.list_screen]
        if self.page:
            self.update()

    def refresh(self, from_sync: bool = False) -> None:
        if self.detail_screen is not None:
            self.detail_screen.refresh(from_sync=from_sync)
        else:
            self.list_screen.refresh()


def main(page: ft.Page) -> None:
    page.title = "Mochi Desktop"
    page.window.width = 1200
    page.window.height = 800
    page.padding = 0
    db.init()

    page.theme = theme.LIGHT_THEME
    page.dark_theme = theme.DARK_THEME
    current_theme_mode = db.get_settings().get("theme_mode", "system")
    page.theme_mode = theme.flet_theme_mode(current_theme_mode)

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
    content = ft.Container(content=orders_section, expand=True, padding=theme.PAGE_PADDING)

    def on_nav_change(e: ft.ControlEvent) -> None:
        content.content = sections[nav_rail.selected_index]
        page.update()

    def toggle_theme(e: ft.ControlEvent) -> None:
        nonlocal current_theme_mode
        current_theme_mode = theme.next_theme_mode(current_theme_mode)
        db.set_setting("theme_mode", current_theme_mode)
        page.theme_mode = theme.flet_theme_mode(current_theme_mode)
        theme_button.icon = theme.THEME_ICONS[current_theme_mode]
        page.update()

    theme_button = ft.IconButton(
        icon=theme.THEME_ICONS.get(current_theme_mode, theme.THEME_ICONS["system"]),
        tooltip="Тема оформления",
        on_click=toggle_theme,
    )

    def on_export_file_selected(e: ft.FilePickerResultEvent) -> None:
        if not e.path:
            return
        try:
            saved_path = export_to_excel(e.path)
            page.open(ft.SnackBar(ft.Text(f"Экспортировано: {saved_path}")))
        except Exception as exc:  # noqa: BLE001 - любая ошибка записи файла должна дойти до пользователя
            page.open(ft.SnackBar(ft.Text(f"Ошибка экспорта: {exc}"), bgcolor=ft.Colors.RED))

    export_file_picker = ft.FilePicker(on_result=on_export_file_selected)
    page.overlay.append(export_file_picker)

    def on_export_click(e: ft.ControlEvent) -> None:
        export_file_picker.save_file(
            dialog_title="Сохранить экспорт как",
            file_name="mochi_export.xlsx",
            allowed_extensions=["xlsx"],
        )

    export_button = ft.IconButton(
        icon=ft.Icons.FILE_DOWNLOAD,
        tooltip="Экспорт в Excel",
        on_click=on_export_click,
    )

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        leading=ft.Column([theme_button, export_button], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
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
        orders_section.refresh(from_sync=True)
        customers_screen.refresh(from_sync=True)
        stats_screen.refresh()
        sheets_sync.sync_in_background()

    page.pubsub.subscribe(lambda _: on_db_changed())
    live_sync = LiveSync(on_change=lambda: page.pubsub.send_all("db_changed"), interval=3.0)
    live_sync.start()
    sheets_sync.sync_in_background()  # таблица актуальна сразу после запуска, а не только после первой правки
    page.on_disconnect = lambda e: live_sync.stop()

    page.add(ft.Row([nav_rail, ft.VerticalDivider(width=1), content], expand=True))


if __name__ == "__main__":
    ft.app(target=main)
