"""Точка входа «Студии Паулюкевичуса» — локальной панели управления заказами 3D-печати."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Шрифты и иконка: из исходников — <проект>/assets, в собранном .exe — распакованная папка PyInstaller.
APP_NAME = "Студия Паулюкевичуса"
ASSETS_DIR = Path(getattr(sys, "_MEIPASS", ROOT)) / "assets"

import flet as ft
from dotenv import load_dotenv

import db
from app import sheets_sync, theme
from app.excel_writer import export_to_excel
from app.live_sync import LiveSync
from app.report_dialog import ReportDialog
from app.sidebar import Action, Destination, Sidebar
from app.screens.customers_screen import CustomersScreen
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen
from app.screens.orders_screen import OrdersScreen
from app.screens.plastics_screen import PlasticsScreen
from app.screens.prices_screen import PricesScreen
from app.screens.spools_screen import SpoolsScreen
from app.screens.stats_screen import StatsScreen
from paths import DATA_DIR

load_dotenv(DATA_DIR / ".env")


class OrdersSection(ft.Column):
    """Заказы: список, при клике на заказ показывает его карточку вместо списка."""

    def __init__(self, on_new_order=None):
        super().__init__(expand=True)
        self.list_screen = OrdersScreen(on_open_order=self._open_order, on_new_order=on_new_order)
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
    page.title = APP_NAME
    page.window.width = 1280
    page.window.height = 820
    page.window.min_width = 520
    page.window.min_height = 480
    page.padding = 0
    db.init()

    page.fonts = theme.FONTS
    # Русский язык для стандартных окон Flutter: календарь с понедельника, названия месяцев.
    page.locale_configuration = ft.LocaleConfiguration(
        supported_locales=[ft.Locale("ru", "RU")], current_locale=ft.Locale("ru", "RU"))
    page.theme = theme.LIGHT_THEME
    page.dark_theme = theme.DARK_THEME
    current_theme_mode = db.get_settings().get("theme_mode", "system")
    page.theme_mode = theme.flet_theme_mode(current_theme_mode)

    def go_to_new_order() -> None:
        nav_rail.selected_index = 1
        on_nav_change(None)

    def open_order_from_anywhere(order_id: int) -> None:
        nav_rail.selected_index = 0
        switcher.content = orders_section
        page.update()
        orders_section._open_order(order_id)

    orders_section = OrdersSection(on_new_order=go_to_new_order)
    customers_screen = CustomersScreen(on_open_order=open_order_from_anywhere)
    prices_screen = PricesScreen()
    stats_screen = StatsScreen()
    new_order_screen = NewOrderScreen(on_created=open_order_from_anywhere)
    spools_screen = SpoolsScreen()

    def add_spool_of(plastic: str) -> None:
        nav_rail.selected_index = sections.index(spools_screen)
        on_nav_change(None)
        spools_screen.preselect(plastic)

    plastics_screen = PlasticsScreen(on_add_spool=add_spool_of)

    sections = [orders_section, new_order_screen, customers_screen, plastics_screen, spools_screen,
                prices_screen, stats_screen]
    # Плавная смена экранов: новый проявляется и чуть «подрастает», как виджеты на Motion.
    switcher = ft.AnimatedSwitcher(
        orders_section, transition=ft.AnimatedSwitcherTransition.FADE, duration=260, reverse_duration=140,
        switch_in_curve=ft.AnimationCurve.EASE_OUT_CUBIC, switch_out_curve=ft.AnimationCurve.EASE_IN,
        expand=True,
    )
    content = ft.Container(content=switcher, expand=True, alignment=ft.alignment.top_center,
                           padding=ft.padding.symmetric(horizontal=theme.PAGE_PADDING, vertical=20))

    def on_nav_change(e: ft.ControlEvent | None) -> None:
        section = sections[nav_rail.selected_index]
        if section is orders_section and orders_section.detail_screen is not None and e is not None:
            orders_section._back_to_list()  # клик по «Заказы» в меню — всегда к списку
        if section is not new_order_screen and hasattr(section, "refresh"):
            section.refresh()
        switcher.content = section
        page.update()

    def toggle_theme(e: ft.ControlEvent) -> None:
        nonlocal current_theme_mode
        current_theme_mode = theme.next_theme_mode(current_theme_mode)
        db.set_setting("theme_mode", current_theme_mode)
        page.theme_mode = theme.flet_theme_mode(current_theme_mode)
        apply_layout()

    def on_export_file_selected(e: ft.FilePickerResultEvent) -> None:
        if not e.path:
            return
        try:
            saved_path = export_to_excel(e.path)
            page.open(ft.SnackBar(ft.Text(f"Экспортировано: {saved_path}")))
        except Exception as exc:  # noqa: BLE001 - любая ошибка записи файла должна дойти до пользователя
            page.open(ft.SnackBar(ft.Text(f"Ошибка экспорта: {exc}"), bgcolor=theme.ERR))

    export_file_picker = ft.FilePicker(on_result=on_export_file_selected)
    page.overlay.append(export_file_picker)

    def on_export_click(e: ft.ControlEvent) -> None:
        export_file_picker.save_file(
            dialog_title="Сохранить экспорт как",
            file_name="Студия_все_данные.xlsx",
            allowed_extensions=["xlsx"],
        )

    def show_message(text: str, error: bool = False) -> None:
        page.open(ft.SnackBar(ft.Text(text), bgcolor=theme.ERR if error else None))

    report_dialog = ReportDialog(page, on_saved=lambda path: show_message(f"Смета сохранена: {path}"),
                                 on_error=lambda msg: show_message(f"Не удалось сохранить смету: {msg}", True))

    theme_labels = {"system": "Тема: как в системе", "light": "Тема: светлая", "dark": "Тема: тёмная"}

    def sidebar_actions() -> list[Action]:
        """Тема, смета и экспорт внизу меню."""
        return [
            Action(theme.THEME_ICONS.get(current_theme_mode, theme.THEME_ICONS["system"]),
                   theme_labels.get(current_theme_mode, theme_labels["system"]), toggle_theme),
            Action(ft.Icons.REQUEST_QUOTE_OUTLINED, "Смета за период", lambda e: report_dialog.open()),
            Action(ft.Icons.FILE_DOWNLOAD_OUTLINED, "Экспорт всех данных", on_export_click),
        ]

    def sidebar_leading(extended: bool) -> ft.Control:
        logo = ft.Container(ft.Icon(ft.Icons.VIEW_IN_AR, color=ft.Colors.ON_PRIMARY, size=20),
                            bgcolor=ft.Colors.PRIMARY, border_radius=12, padding=9, width=40, height=40)
        if not extended:
            return ft.Container(logo, alignment=ft.alignment.center, padding=ft.padding.only(bottom=12))
        return ft.Container(
            ft.Row([logo, ft.Column([ft.Text("Студия", size=16, font_family=theme.FONT_FAMILY_MEDIUM),
                                     ft.Text("Паулюкевичуса", size=12, font_family=theme.FONT_FAMILY_MEDIUM),
                                     ft.Text("заказы 3D-печати", size=10, color=ft.Colors.ON_SURFACE_VARIANT)],
                                    spacing=0, tight=True)], spacing=12),
            padding=ft.padding.only(left=4, bottom=16),
        )

    nav_rail = Sidebar([
        Destination(ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG, "Заказы"),
        Destination(ft.Icons.ADD_BOX_OUTLINED, ft.Icons.ADD_BOX, "Новый заказ"),
        Destination(ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE, "Клиенты"),
        Destination(ft.Icons.SCIENCE_OUTLINED, ft.Icons.SCIENCE, "Информация о пластике"),
        Destination(ft.Icons.CALCULATE_OUTLINED, ft.Icons.CALCULATE, "Калькулятор пластика"),
        Destination(ft.Icons.SELL_OUTLINED, ft.Icons.SELL, "Цены"),
        Destination(ft.Icons.INSIGHTS_OUTLINED, ft.Icons.INSIGHTS, "Статистика"),
    ], on_change=on_nav_change)

    def apply_layout(e=None) -> None:
        """Подстраивает меню, отступы и «Клиентов» под текущую ширину окна."""
        width = page.width or page.window.width or 1280
        extended = width >= theme.WIDE_WIDTH
        compact = width < theme.COMPACT_WIDTH
        nav_rail.set_layout(extended, sidebar_leading(extended), sidebar_actions())
        rail_width = nav_rail.width
        side = 12 if compact else theme.content_padding(width - rail_width)
        content.padding = ft.padding.symmetric(horizontal=side, vertical=12 if compact else 20)
        customers_screen.set_compact(compact)
        page.update()

    page.on_resized = apply_layout

    def on_db_changed() -> None:
        orders_section.refresh(from_sync=True)
        customers_screen.refresh(from_sync=True)
        stats_screen.refresh()
        plastics_screen.refresh()
        spools_screen.refresh()
        sheets_sync.sync_in_background()

    page.pubsub.subscribe(lambda _: on_db_changed())
    live_sync = LiveSync(on_change=lambda: page.pubsub.send_all("db_changed"), interval=3.0)
    live_sync.start()
    sheets_sync.sync_in_background()  # таблица актуальна сразу после запуска, а не только после первой правки
    page.on_disconnect = lambda e: live_sync.stop()

    # STRETCH — меню во всю высоту окна (иначе Row центрирует его по вертикали).
    page.add(ft.Row([nav_rail, ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT), content],
                    expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH))
    apply_layout()


if __name__ == "__main__":
    ft.app(target=main, assets_dir=str(ASSETS_DIR))
