# UI Redesign and Theming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle all six Mochi Desktop screens into a card-based, minimalist layout (soft rounded corners, generous spacing, Yandex.Mail/Disk-inspired) and add a persisted light/dark/system theme toggle.

**Architecture:** A single new `app/theme.py` module is the one source of truth for colors, spacing, and a `card()` layout helper; every screen imports it instead of hardcoding pixel values. A new `theme_mode` setting (stored via the existing `db.py` settings table, same mechanism as `currency`/`hour_rate`) drives `page.theme_mode`, toggled by a button in `app/main.py`. No business logic, database schema, or screen public interfaces (constructor signatures, `.refresh()` signatures) change — this is a pure presentation-layer pass over already-working, already-reviewed code.

**Tech Stack:** Python, Flet (Material 3), pytest.

**Spec:** `docs/superpowers/specs/2026-09-24-ui-redesign-theming.md`

## Global Constraints

- Every screen's layout code must use `app/theme.py`'s `SPACING`, `PAGE_PADDING`, `CARD_RADIUS`, and `card()` helper — no new hardcoded spacing/radius magic numbers.
- No screen's constructor signature, `.refresh()` signature, or event-handler method names may change — `app/main.py` and the existing test suite depend on them exactly as they are today.
- No business logic changes: every `db.*`/`pricing.*` call, every handler's actual read/write behavior, stays byte-for-byte identical — only how controls are grouped/wrapped for display changes.
- Accent color is `#3D5AFE` (soft blue, Yandex.Disk-like), `use_material3=True`, applied via `color_scheme_seed` — not a hand-built `ColorScheme`.
- Theme preference persists via `db.get_settings()["theme_mode"]` / `db.set_setting("theme_mode", ...)`, values are exactly the strings `"system"`, `"light"`, `"dark"` — the same settings mechanism already used for `currency`, `hour_rate`, etc., no new table/column.
- No automated tests for Flet screen layouts (established convention in this codebase — verified manually per task); `app/theme.py`'s pure functions (`card()`, `next_theme_mode()`) and the new `db.py` setting DO get unit tests.

---

## File Structure

**Create:**
- `app/theme.py` — theme objects (`LIGHT_THEME`, `DARK_THEME`), layout constants (`SPACING`, `PAGE_PADDING`, `CARD_RADIUS`, `BUTTON_RADIUS`), `card()` container helper, theme-mode cycling (`next_theme_mode()`, `FLET_THEME_MODES`, `THEME_ICONS`).
- `tests/test_theme.py` — unit tests for `card()` and `next_theme_mode()`.

**Modify:**
- `db.py` — add `"theme_mode": "system"` to `DEFAULT_SETTINGS`.
- `tests/test_db_baseline.py` — add theme-mode default/round-trip tests.
- `app/main.py` — apply `page.theme`/`page.dark_theme`/`page.theme_mode` from the persisted setting, add a theme-toggle button to the `NavigationRail`, wrap `content` in themed padding.
- `app/screens/orders_screen.py`, `app/screens/order_detail.py`, `app/screens/new_order.py`, `app/screens/customers_screen.py`, `app/screens/prices_screen.py` — regroup existing controls into `theme.card(...)`-wrapped sections; no handler/logic changes.
- `app/screens/stats_screen.py` — rewritten to a KPI-card row (revenue/profit/debt/order count) plus a details card, replacing the flat text list.

---

### Task 1: `app/theme.py` — theme module and layout helpers

**Files:**
- Create: `app/theme.py`
- Test: `tests/test_theme.py`

**Interfaces:**
- Produces: `theme.LIGHT_THEME: ft.Theme`, `theme.DARK_THEME: ft.Theme`, `theme.SPACING: int`, `theme.PAGE_PADDING: int`, `theme.CARD_RADIUS: int`, `theme.BUTTON_RADIUS: int`, `theme.card(content: ft.Control, **container_kwargs) -> ft.Container`, `theme.THEME_MODE_CYCLE: list[str]`, `theme.next_theme_mode(current: str) -> str`, `theme.FLET_THEME_MODES: dict[str, ft.ThemeMode]`, `theme.THEME_ICONS: dict[str, str]`. Relied on by every later task in this plan.

- [ ] **Step 1: Write the failing test**

Create `tests/test_theme.py`:

```python
"""Тесты для app/theme.py — чистые функции, без side effects."""
import flet as ft

from app import theme


def test_card_wraps_content_in_rounded_container():
    inner = ft.Text("hello")
    result = theme.card(inner)
    assert isinstance(result, ft.Container)
    assert result.content is inner
    assert result.border_radius == theme.CARD_RADIUS


def test_card_allows_overriding_defaults():
    inner = ft.Text("hi")
    result = theme.card(inner, padding=0, width=160)
    assert result.padding == 0
    assert result.width == 160


def test_next_theme_mode_cycles_system_light_dark():
    assert theme.next_theme_mode("system") == "light"
    assert theme.next_theme_mode("light") == "dark"
    assert theme.next_theme_mode("dark") == "system"


def test_next_theme_mode_unknown_value_falls_back_to_system():
    assert theme.next_theme_mode("bogus") == "system"


def test_flet_theme_modes_cover_every_cycle_value():
    for mode in theme.THEME_MODE_CYCLE:
        assert mode in theme.FLET_THEME_MODES
        assert mode in theme.THEME_ICONS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_theme.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.theme'`

- [ ] **Step 3: Implement `app/theme.py`**

```python
"""Единый визуальный язык приложения: тема Material 3 и карточная вёрстка."""
import flet as ft

ACCENT_COLOR = "#3D5AFE"

CARD_RADIUS = 16
BUTTON_RADIUS = 12
SPACING = 16
PAGE_PADDING = 24

LIGHT_THEME = ft.Theme(color_scheme_seed=ACCENT_COLOR, use_material3=True)
DARK_THEME = ft.Theme(color_scheme_seed=ACCENT_COLOR, use_material3=True)

THEME_MODE_CYCLE = ["system", "light", "dark"]

FLET_THEME_MODES = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}

THEME_ICONS = {
    "system": ft.Icons.BRIGHTNESS_AUTO,
    "light": ft.Icons.LIGHT_MODE,
    "dark": ft.Icons.DARK_MODE,
}


def next_theme_mode(current: str) -> str:
    """Следующее значение в цикле система → светлая → тёмная → снова система."""
    try:
        idx = THEME_MODE_CYCLE.index(current)
    except ValueError:
        idx = -1
    return THEME_MODE_CYCLE[(idx + 1) % len(THEME_MODE_CYCLE)]


def card(content: ft.Control, **container_kwargs) -> ft.Container:
    """Единая обёртка «карточка»: скруглённые углы, поверхностный фон темы,
    внутренний отступ — используется всеми экранами вместо голого Column/Row."""
    defaults = dict(
        content=content,
        padding=SPACING,
        border_radius=CARD_RADIUS,
        bgcolor=ft.Colors.SURFACE,
        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
    )
    defaults.update(container_kwargs)
    return ft.Container(**defaults)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_theme.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/theme.py tests/test_theme.py
git commit -m "feat: add theme module with card layout helper and theme-mode cycling"
```

---

### Task 2: `theme_mode` setting in `db.py`

**Files:**
- Modify: `db.py:21-30` (the `DEFAULT_SETTINGS` dict)
- Test: `tests/test_db_baseline.py`

**Interfaces:**
- Produces: `db.get_settings()["theme_mode"]` defaults to `"system"` on a fresh DB; `db.set_setting("theme_mode", ...)` persists it. Relied on by Task 3.

- [ ] **Step 1: Write the failing test**

In `tests/test_db_baseline.py`, add:

```python
def test_theme_mode_defaults_to_system(temp_db):
    assert db.get_settings()["theme_mode"] == "system"


def test_theme_mode_can_be_changed(temp_db):
    db.set_setting("theme_mode", "dark")
    assert db.get_settings()["theme_mode"] == "dark"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_baseline.py -k theme_mode -v`
Expected: FAIL with `KeyError: 'theme_mode'`

- [ ] **Step 3: Add the default setting**

In `db.py`, find:

```python
DEFAULT_SETTINGS = {
    # цена материала, ₽ за кг (уже итоговая цена для клиента)
    "materials": {"PLA": 4000, "PETG": 6000, "ABS": 10000},
    "hour_rate": 50,        # ₽ за час печати
    "reverse_price": 1000,  # ₽ за реверс-моделирование, если нет STL у заказчика
    "currency": "₽",
    "owners": [],        # telegram id владельцев (если ADMIN_IDS не задан в .env)
    "reminder_hour": 9,  # во сколько присылать сводку по дедлайнам
    "last_reminder": "",
}
```

Replace with:

```python
DEFAULT_SETTINGS = {
    # цена материала, ₽ за кг (уже итоговая цена для клиента)
    "materials": {"PLA": 4000, "PETG": 6000, "ABS": 10000},
    "hour_rate": 50,        # ₽ за час печати
    "reverse_price": 1000,  # ₽ за реверс-моделирование, если нет STL у заказчика
    "currency": "₽",
    "owners": [],        # telegram id владельцев (если ADMIN_IDS не задан в .env)
    "reminder_hour": 9,  # во сколько присылать сводку по дедлайнам
    "last_reminder": "",
    "theme_mode": "system",  # "system" | "light" | "dark" — тема приложения
}
```

No migration function is needed: `init()` already loops over `DEFAULT_SETTINGS.items()` doing `INSERT OR IGNORE INTO settings`, so this new key is automatically backfilled for existing databases the next time `db.init()` runs — the same mechanism `reminder_hour`/`last_reminder` already rely on.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_baseline.py -v`
Expected: PASS (all tests including the 2 new ones)

Run full suite: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db_baseline.py
git commit -m "feat: add theme_mode setting, defaulting to system"
```

---

### Task 3: Apply theme and add toggle button in `app/main.py`

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `theme.LIGHT_THEME`, `theme.DARK_THEME`, `theme.FLET_THEME_MODES`, `theme.THEME_ICONS`, `theme.next_theme_mode`, `theme.PAGE_PADDING` (Task 1); `db.get_settings()["theme_mode"]` / `db.set_setting("theme_mode", ...)` (Task 2).
- Produces: nothing new for later tasks — this is `main()`'s own wiring, screens don't depend on it.

- [ ] **Step 1: Update `app/main.py`**

Find:

```python
import db
from app.live_sync import LiveSync
from app.screens.customers_screen import CustomersScreen
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen
from app.screens.orders_screen import OrdersScreen
from app.screens.prices_screen import PricesScreen
from app.screens.stats_screen import StatsScreen
```

Replace with:

```python
import db
from app import theme
from app.live_sync import LiveSync
from app.screens.customers_screen import CustomersScreen
from app.screens.new_order import NewOrderScreen
from app.screens.order_detail import OrderDetailScreen
from app.screens.orders_screen import OrdersScreen
from app.screens.prices_screen import PricesScreen
from app.screens.stats_screen import StatsScreen
```

Find:

```python
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
```

Replace with:

```python
def main(page: ft.Page) -> None:
    page.title = "Mochi Desktop"
    page.window.width = 1200
    page.window.height = 800
    page.padding = 0
    db.init()

    page.theme = theme.LIGHT_THEME
    page.dark_theme = theme.DARK_THEME
    current_theme_mode = db.get_settings().get("theme_mode", "system")
    page.theme_mode = theme.FLET_THEME_MODES[current_theme_mode]

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
        page.theme_mode = theme.FLET_THEME_MODES[current_theme_mode]
        theme_button.icon = theme.THEME_ICONS[current_theme_mode]
        page.update()

    theme_button = ft.IconButton(
        icon=theme.THEME_ICONS[current_theme_mode],
        tooltip="Тема оформления",
        on_click=toggle_theme,
    )

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        leading=theme_button,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.LIST_ALT, label="Заказы"),
            ft.NavigationRailDestination(icon=ft.Icons.ADD_BOX, label="Новый заказ"),
            ft.NavigationRailDestination(icon=ft.Icons.PEOPLE, label="Клиенты"),
            ft.NavigationRailDestination(icon=ft.Icons.SELL, label="Цены"),
            ft.NavigationRailDestination(icon=ft.Icons.BAR_CHART, label="Статистика"),
        ],
        on_change=on_nav_change,
    )
```

The rest of `main()` (`on_db_changed`, `page.pubsub.subscribe(...)`, `live_sync = LiveSync(...)`, `page.add(...)`) is unchanged.

- [ ] **Step 2: Run full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS (all tests, including Tasks 1-2's new ones)

- [ ] **Step 3: Manually verify**

Run: `.venv\Scripts\python.exe app\main.py`

Verify: the window opens with the accent-colored theme applied; the top of the navigation rail shows a theme icon button; clicking it cycles the whole app's theme (system → light → dark → system) and the icon changes to match; close and reopen the app — the theme you left it on is still applied (persisted via `db.set_setting`).

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: apply theme and add persisted theme toggle to navigation rail"
```

---

### Task 4: Restyle the orders list screen

**Files:**
- Modify: `app/screens/orders_screen.py`

**Interfaces:**
- Consumes: `theme.card`, `theme.SPACING` (Task 1). No change to `OrdersScreen(on_open_order)` constructor or `.refresh()` — Task 14's shell in `main.py` already wires this and must keep working unmodified.

- [ ] **Step 1: Restyle `app/screens/orders_screen.py`**

Find:

```python
import flet as ft

import db
import pricing

FILTERS = [("active", "Активные"), ("unpaid", "Неоплаченные"), ("done", "Завершённые"), ("all", "Все")]


class OrdersScreen(ft.Column):
    def __init__(self, on_open_order: Callable[[int], None]):
        super().__init__(expand=True, spacing=10)
        self.on_open_order = on_open_order
        self.kind = "active"
        self.search_text = ""

        self.tabs = ft.Tabs(
            selected_index=0,
            tabs=[ft.Tab(text=label) for _, label in FILTERS],
            on_change=self._on_filter_change,
        )
        self.search_field = ft.TextField(
            label="Поиск по клиенту / контакту / описанию",
            on_change=self._on_search_change,
        )
        self.list_view = ft.ListView(expand=True, spacing=6)

        self.controls = [self.tabs, self.search_field, self.list_view]
        self._render()
```

Replace with:

```python
import flet as ft

import db
import pricing
from app import theme

FILTERS = [("active", "Активные"), ("unpaid", "Неоплаченные"), ("done", "Завершённые"), ("all", "Все")]


class OrdersScreen(ft.Column):
    def __init__(self, on_open_order: Callable[[int], None]):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.on_open_order = on_open_order
        self.kind = "active"
        self.search_text = ""

        self.tabs = ft.Tabs(
            selected_index=0,
            tabs=[ft.Tab(text=label) for _, label in FILTERS],
            on_change=self._on_filter_change,
        )
        self.search_field = ft.TextField(
            label="Поиск по клиенту / контакту / описанию",
            on_change=self._on_search_change,
        )
        self.list_view = ft.ListView(expand=True, spacing=theme.SPACING)

        self.controls = [
            theme.card(ft.Column([self.tabs, self.search_field], spacing=theme.SPACING)),
            self.list_view,
        ]
        self._render()
```

Find:

```python
        return ft.ListTile(
            title=ft.Text(f"#{o['id']} {o['client']}"),
            subtitle=ft.Text(subtitle),
            on_click=lambda e, oid=o["id"]: self.on_open_order(oid),
        )
```

Replace with:

```python
        return theme.card(
            ft.ListTile(
                title=ft.Text(f"#{o['id']} {o['client']}"),
                subtitle=ft.Text(subtitle),
                on_click=lambda e, oid=o["id"]: self.on_open_order(oid),
            ),
            padding=0,
        )
```

(`padding=0` avoids double padding, since `ft.ListTile` already reserves its own internal padding.)

- [ ] **Step 2: Run full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS (no test covers this file's layout directly, but this confirms nothing else broke — e.g. `tests/test_app_scaffold.py` importing `app.main` transitively imports this module)

- [ ] **Step 3: Manually verify**

Create a temporary `scratch_orders_screen.py` in the repo root (not committed):

```python
import flet as ft

import db
from app.screens.orders_screen import OrdersScreen

db.init()
db.add_order({"client": "Проверка", "contact": "", "material": "PLA", "weight_g": 50,
              "print_hours": 1, "qty": 1, "cost": 100, "price": 150})


def main(page: ft.Page):
    page.add(OrdersScreen(on_open_order=lambda oid: print("open", oid)))


ft.app(target=main)
```

Run: `.venv\Scripts\python.exe scratch_orders_screen.py`
Expected: the filter/search area renders inside a soft rounded card, and the order tile below it is also a rounded card with visible spacing around it — not a flat list. Delete `scratch_orders_screen.py` (and `orders.db` if freshly created for this check) afterward.

- [ ] **Step 4: Commit**

```bash
git add app/screens/orders_screen.py
git commit -m "style: wrap orders screen filters and tiles in rounded cards"
```

---

### Task 5: Restyle the order detail screen

**Files:**
- Modify: `app/screens/order_detail.py`

**Interfaces:**
- Consumes: `theme.card`, `theme.SPACING` (Task 1). No change to `OrderDetailScreen(order_id, on_back)` constructor, `.refresh(from_sync)` signature, or any `_on_*` handler — only the `self.controls` list in `__init__` changes.

- [ ] **Step 1: Restyle `app/screens/order_detail.py`**

Find the `import` block:

```python
import flet as ft
import httpx

import db
import pricing
from app.telegram_files import TelegramFileError, download_file
```

Replace with:

```python
import flet as ft
import httpx

import db
import pricing
from app import theme
from app.telegram_files import TelegramFileError, download_file
```

Find the `self.controls = [...]` block in `__init__`:

```python
        self.controls = [
            ft.Row([ft.TextButton("← К списку", on_click=lambda e: self.on_back()), self.status_banner]),
            ft.Text(f"Заказ #{order_id}", size=20, weight=ft.FontWeight.BOLD),
            ft.Row([self.status_dd, self.paid_switch]),
            ft.Row([self.client_field, self.contact_field]),
            self.customer_dd,
            ft.Row([self.material_field, self.color_field]),
            ft.Row([self.weight_field, self.hours_field, self.qty_field]),
            ft.Row([self.deadline_field, self.price_field]),
            self.price_text,
            self.notes_field,
            ft.Text("Вложения", weight=ft.FontWeight.BOLD),
            self.attachments_column,
            ft.ElevatedButton("Добавить файл", icon=ft.Icons.UPLOAD_FILE, on_click=self._on_add_file_click),
            ft.OutlinedButton("Удалить заказ", icon=ft.Icons.DELETE, on_click=self._on_delete_click,
                               style=ft.ButtonStyle(color=ft.Colors.RED)),
        ]
        self._loaded = False
```

Replace with:

```python
        self.controls = [
            ft.Row([ft.TextButton("← К списку", on_click=lambda e: self.on_back()), self.status_banner]),
            ft.Text(f"Заказ #{order_id}", size=20, weight=ft.FontWeight.BOLD),
            theme.card(ft.Column([
                ft.Row([self.status_dd, self.paid_switch]),
                ft.Row([self.client_field, self.contact_field]),
                self.customer_dd,
            ], spacing=theme.SPACING)),
            theme.card(ft.Column([
                ft.Row([self.material_field, self.color_field]),
                ft.Row([self.weight_field, self.hours_field, self.qty_field]),
                ft.Row([self.deadline_field, self.price_field]),
                self.price_text,
                self.notes_field,
            ], spacing=theme.SPACING)),
            theme.card(ft.Column([
                ft.Text("Вложения", weight=ft.FontWeight.BOLD),
                self.attachments_column,
                ft.ElevatedButton("Добавить файл", icon=ft.Icons.UPLOAD_FILE, on_click=self._on_add_file_click),
            ], spacing=theme.SPACING)),
            ft.OutlinedButton("Удалить заказ", icon=ft.Icons.DELETE, on_click=self._on_delete_click,
                               style=ft.ButtonStyle(color=ft.Colors.RED)),
        ]
        self._loaded = False
```

Also update `super().__init__(expand=True, spacing=10)` (near the top of `__init__`) to `super().__init__(expand=True, spacing=theme.SPACING)`.

No other lines in this file change — every method body (`refresh`, `_attachment_row`, `_on_*` handlers, `did_mount`, `will_unmount`) stays exactly as it is today.

- [ ] **Step 2: Run full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS — in particular `tests/test_file_picker_overlay.py`'s three tests must still pass unchanged, since `did_mount`/`will_unmount` were not touched by this task.

- [ ] **Step 3: Manually verify**

Create a temporary `scratch_order_detail.py` (not committed):

```python
import flet as ft

import db
from app.screens.order_detail import OrderDetailScreen

db.init()
order_id = db.add_order({"client": "Проверка", "contact": "@test", "material": "PLA",
                          "weight_g": 50, "print_hours": 1, "qty": 1, "cost": 100, "price": 150})


def main(page: ft.Page):
    page.add(OrderDetailScreen(order_id=order_id, on_back=lambda: print("back")))


ft.app(target=main)
```

Run: `.venv\Scripts\python.exe scratch_order_detail.py`
Expected: three distinct rounded cards ("Заказчик и статус" fields, "Печать и цена" fields, "Вложения"), with visible spacing between them; editing a field and changing status still works exactly as before. Delete the scratch script (and `orders.db` if freshly created) afterward.

- [ ] **Step 4: Commit**

```bash
git add app/screens/order_detail.py
git commit -m "style: group order detail fields into rounded cards"
```

---

### Task 6: Restyle the new-order form

**Files:**
- Modify: `app/screens/new_order.py`

**Interfaces:**
- Consumes: `theme.card`, `theme.SPACING` (Task 1). No change to `NewOrderScreen(on_created)` constructor or any handler — only `self.controls` in `__init__` changes.

- [ ] **Step 1: Restyle `app/screens/new_order.py`**

Find the `import` block:

```python
import flet as ft

import db
import pricing
```

Replace with:

```python
import flet as ft

import db
import pricing
from app import theme
```

Find the `self.controls = [...]` block:

```python
        self.controls = [
            ft.Text("Новый заказ", size=20, weight=ft.FontWeight.BOLD),
            ft.Row([self.client_field, self.contact_field]),
            self.description_field,
            ft.Row([self.material_dd, self.color_field]),
            ft.Row([self.weight_field, self.hours_field, self.qty_field]),
            ft.Row([self.deadline_field, self.reverse_checkbox]),
            self.price_preview,
            self.custom_price_field,
            ft.Row([ft.ElevatedButton("Прикрепить файлы", icon=ft.Icons.UPLOAD_FILE,
                                       on_click=lambda e: self.file_picker.pick_files(allow_multiple=True)),
                    self.files_text]),
            self.error_text,
            ft.ElevatedButton("Создать заказ", icon=ft.Icons.ADD, on_click=self._on_save),
        ]
```

Replace with:

```python
        self.controls = [
            ft.Text("Новый заказ", size=20, weight=ft.FontWeight.BOLD),
            theme.card(ft.Column([
                ft.Row([self.client_field, self.contact_field]),
                self.description_field,
            ], spacing=theme.SPACING)),
            theme.card(ft.Column([
                ft.Row([self.material_dd, self.color_field]),
                ft.Row([self.weight_field, self.hours_field, self.qty_field]),
                ft.Row([self.deadline_field, self.reverse_checkbox]),
                self.price_preview,
                self.custom_price_field,
                ft.Row([ft.ElevatedButton("Прикрепить файлы", icon=ft.Icons.UPLOAD_FILE,
                                           on_click=lambda e: self.file_picker.pick_files(allow_multiple=True)),
                        self.files_text]),
            ], spacing=theme.SPACING)),
            self.error_text,
            ft.ElevatedButton("Создать заказ", icon=ft.Icons.ADD, on_click=self._on_save),
        ]
```

Also update `super().__init__(expand=True, spacing=10)` to `super().__init__(expand=True, spacing=theme.SPACING)`.

No other lines change — `did_mount`, `will_unmount`, `_on_file_picked`, `_recalc`, `_on_save`, `_reset_form` stay exactly as they are today.

- [ ] **Step 2: Run full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS, including `tests/test_file_picker_overlay.py`'s `test_new_order_repeated_tab_visits_do_not_duplicate_file_picker`.

- [ ] **Step 3: Manually verify**

Create a temporary `scratch_new_order.py` (not committed):

```python
import flet as ft

import db
from app.screens.new_order import NewOrderScreen

db.init()
db.set_setting("materials", {"PLA": 4000, "PETG": 6000})


def main(page: ft.Page):
    page.add(NewOrderScreen(on_created=lambda oid: print("created", oid)))


ft.app(target=main)
```

Run: `.venv\Scripts\python.exe scratch_new_order.py`
Expected: two rounded cards ("Заказчик", "Параметры печати"); typing a client name and clicking "Создать заказ" still creates an order and resets the form, exactly as before. Delete the scratch script (and `orders.db` if freshly created) afterward.

- [ ] **Step 4: Commit**

```bash
git add app/screens/new_order.py
git commit -m "style: group new-order form fields into rounded cards"
```

---

### Task 7: Restyle the customers screen

**Files:**
- Modify: `app/screens/customers_screen.py`

**Interfaces:**
- Consumes: `theme.card`, `theme.SPACING` (Task 1). No change to `CustomersScreen()` constructor or `.refresh(from_sync)` signature.

- [ ] **Step 1: Restyle `app/screens/customers_screen.py`**

Find:

```python
import flet as ft

import db
import pricing


class CustomersScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=10)
        self.search_text = ""
        self.selected_customer_id: int | None = None
        self._notes_field: ft.TextField | None = None

        self.search_field = ft.TextField(label="Поиск клиента", on_change=self._on_search)
        self.list_view = ft.ListView(expand=True, spacing=6)
        self.detail_column = ft.Column(visible=False, spacing=8)

        self.controls = [self.search_field, self.list_view, self.detail_column]
        self.refresh()
```

Replace with:

```python
import flet as ft

import db
import pricing
from app import theme


class CustomersScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.search_text = ""
        self.selected_customer_id: int | None = None
        self._notes_field: ft.TextField | None = None

        self.search_field = ft.TextField(label="Поиск клиента", on_change=self._on_search)
        self.list_view = ft.ListView(expand=True, spacing=theme.SPACING)
        self.detail_column = ft.Column(spacing=8)
        self.detail_card = theme.card(self.detail_column, visible=False)

        self.controls = [theme.card(self.search_field), self.list_view, self.detail_card]
        self.refresh()
```

Find:

```python
    def refresh(self, from_sync: bool = False) -> None:
        customers = db.list_customers(self.search_text.strip())
        self.list_view.controls = [self._customer_tile(c) for c in customers] or [
            ft.Text("Клиентов нет.", italic=True)
        ]
        if self.selected_customer_id is not None:
            self._render_detail(self.selected_customer_id, from_sync=from_sync)
        if self.page:
            self.update()

    def _customer_tile(self, c) -> ft.Control:
        subtitle = f"{c['orders_count']} заказ(ов) · оплачено {pricing.money(c['paid_total'])}"
        if c["debt_total"]:
            subtitle += f" · долг {pricing.money(c['debt_total'])}"
        return ft.ListTile(
            title=ft.Text(c["name"]),
            subtitle=ft.Text(subtitle),
            on_click=lambda e, cid=c["id"]: self._open_customer(cid),
        )
```

Replace with:

```python
    def refresh(self, from_sync: bool = False) -> None:
        customers = db.list_customers(self.search_text.strip())
        self.list_view.controls = [self._customer_tile(c) for c in customers] or [
            ft.Text("Клиентов нет.", italic=True)
        ]
        if self.selected_customer_id is not None:
            self._render_detail(self.selected_customer_id, from_sync=from_sync)
        if self.page:
            self.update()

    def _customer_tile(self, c) -> ft.Control:
        subtitle = f"{c['orders_count']} заказ(ов) · оплачено {pricing.money(c['paid_total'])}"
        if c["debt_total"]:
            subtitle += f" · долг {pricing.money(c['debt_total'])}"
        return theme.card(
            ft.ListTile(
                title=ft.Text(c["name"]),
                subtitle=ft.Text(subtitle),
                on_click=lambda e, cid=c["id"]: self._open_customer(cid),
            ),
            padding=0,
        )
```

Find the `_render_detail` method:

```python
    def _render_detail(self, customer_id: int, from_sync: bool = False) -> None:
        customer = db.get_customer(customer_id)
        if not customer:
            self.detail_column.visible = False
            self.selected_customer_id = None
            return
        if from_sync and self.detail_column.controls:
            # notes_field — TextField с сохранением по on_blur: во время live-sync
            # переиспользуем текущий контрол, чтобы не затереть незасохранённый ввод.
            notes_field = self._notes_field
        else:
            notes_field = ft.TextField(
                label="Заметки", value=customer["notes"] or "", multiline=True,
                on_blur=lambda e, cid=customer_id: db.update_customer(cid, notes=notes_field.value),
            )
            self._notes_field = notes_field
        orders = [o for o in db.list_orders("all", limit=200) if o["customer_id"] == customer_id]
        order_rows = [
            ft.Text(f"#{o['id']} · {db.STATUSES.get(o['status'], o['status'])} · {pricing.money(o['price'])}")
            for o in orders
        ] or [ft.Text("Заказов пока нет.", italic=True)]

        self.detail_column.visible = True
        self.detail_column.controls = [
            ft.Text(customer["name"], size=18, weight=ft.FontWeight.BOLD),
            ft.Text(f"Контакт: {customer['contact'] or '—'}"),
            notes_field,
            ft.Text("История заказов:", weight=ft.FontWeight.BOLD),
            *order_rows,
        ]
```

Replace with:

```python
    def _render_detail(self, customer_id: int, from_sync: bool = False) -> None:
        customer = db.get_customer(customer_id)
        if not customer:
            self.detail_card.visible = False
            self.selected_customer_id = None
            return
        if from_sync and self.detail_column.controls:
            # notes_field — TextField с сохранением по on_blur: во время live-sync
            # переиспользуем текущий контрол, чтобы не затереть незасохранённый ввод.
            notes_field = self._notes_field
        else:
            notes_field = ft.TextField(
                label="Заметки", value=customer["notes"] or "", multiline=True,
                on_blur=lambda e, cid=customer_id: db.update_customer(cid, notes=notes_field.value),
            )
            self._notes_field = notes_field
        orders = [o for o in db.list_orders("all", limit=200) if o["customer_id"] == customer_id]
        order_rows = [
            ft.Text(f"#{o['id']} · {db.STATUSES.get(o['status'], o['status'])} · {pricing.money(o['price'])}")
            for o in orders
        ] or [ft.Text("Заказов пока нет.", italic=True)]

        self.detail_card.visible = True
        self.detail_column.controls = [
            ft.Text(customer["name"], size=18, weight=ft.FontWeight.BOLD),
            ft.Text(f"Контакт: {customer['contact'] or '—'}"),
            notes_field,
            ft.Text("История заказов:", weight=ft.FontWeight.BOLD),
            *order_rows,
        ]
```

(Only `self.detail_column.visible = ...` became `self.detail_card.visible = ...` in two places — `detail_column` itself no longer carries a `visible` flag, its wrapping card does.)

- [ ] **Step 2: Run full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 3: Manually verify**

Create a temporary `scratch_customers.py` (not committed):

```python
import flet as ft

import db
from app.screens.customers_screen import CustomersScreen

db.init()
db.add_order({"client": "Иван Петров", "contact": "@ivan", "cost": 0, "price": 500})


def main(page: ft.Page):
    page.add(CustomersScreen())


ft.app(target=main)
```

Run: `.venv\Scripts\python.exe scratch_customers.py`
Expected: search field in a rounded card, "Иван Петров" shown as a rounded card tile; clicking it shows the detail panel inside its own rounded card, with editable notes and order history working as before. Delete the scratch script (and `orders.db` if freshly created) afterward.

- [ ] **Step 4: Commit**

```bash
git add app/screens/customers_screen.py
git commit -m "style: wrap customers screen search, tiles, and detail panel in rounded cards"
```

---

### Task 8: Restyle the prices screen

**Files:**
- Modify: `app/screens/prices_screen.py`

**Interfaces:**
- Consumes: `theme.card`, `theme.SPACING` (Task 1). No change to `PricesScreen()` constructor or `.refresh()` signature.

- [ ] **Step 1: Restyle `app/screens/prices_screen.py`**

Find:

```python
import flet as ft

import db
import pricing


class PricesScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=10)
        self.materials_column = ft.Column(spacing=4)
        self.new_material_name = ft.TextField(label="Материал (напр. PLA)", width=200)
        self.new_material_price = ft.TextField(label="Цена за кг", width=150)
        self.hour_rate_field = ft.TextField(label="Ставка часа печати", on_blur=self._save_scalars)
        self.reverse_price_field = ft.TextField(label="Реверс-моделирование", on_blur=self._save_scalars)
        self.currency_field = ft.TextField(label="Валюта", on_blur=self._save_scalars)
        self.status_text = ft.Text("")

        self.controls = [
            ft.Text("Цены и настройки", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Материалы (₽/кг):", weight=ft.FontWeight.BOLD),
            self.materials_column,
            ft.Row([self.new_material_name, self.new_material_price,
                    ft.ElevatedButton("Добавить", on_click=self._add_material)]),
            self.hour_rate_field,
            self.reverse_price_field,
            self.currency_field,
            self.status_text,
        ]
        self.refresh()
```

Replace with:

```python
import flet as ft

import db
import pricing
from app import theme


class PricesScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.materials_column = ft.Column(spacing=4)
        self.new_material_name = ft.TextField(label="Материал (напр. PLA)", width=200)
        self.new_material_price = ft.TextField(label="Цена за кг", width=150)
        self.hour_rate_field = ft.TextField(label="Ставка часа печати", on_blur=self._save_scalars)
        self.reverse_price_field = ft.TextField(label="Реверс-моделирование", on_blur=self._save_scalars)
        self.currency_field = ft.TextField(label="Валюта", on_blur=self._save_scalars)
        self.status_text = ft.Text("")

        self.controls = [
            ft.Text("Цены и настройки", size=20, weight=ft.FontWeight.BOLD),
            theme.card(ft.Column([
                ft.Text("Материалы (₽/кг):", weight=ft.FontWeight.BOLD),
                self.materials_column,
                ft.Row([self.new_material_name, self.new_material_price,
                        ft.ElevatedButton("Добавить", on_click=self._add_material)]),
            ], spacing=theme.SPACING)),
            theme.card(ft.Column([
                self.hour_rate_field,
                self.reverse_price_field,
                self.currency_field,
            ], spacing=theme.SPACING)),
            self.status_text,
        ]
        self.refresh()
```

No other lines change — `refresh`, `_material_row`, `_add_material`, `_save_scalars` stay exactly as they are today.

- [ ] **Step 2: Run full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 3: Manually verify**

Create a temporary `scratch_prices.py` (not committed):

```python
import flet as ft

import db
from app.screens.prices_screen import PricesScreen

db.init()


def main(page: ft.Page):
    page.add(PricesScreen())


ft.app(target=main)
```

Run: `.venv\Scripts\python.exe scratch_prices.py`
Expected: two rounded cards ("Материалы", "Ставки"); editing a material price or adding a new one still saves correctly, exactly as before. Delete the scratch script (and `orders.db` if freshly created) afterward.

- [ ] **Step 4: Commit**

```bash
git add app/screens/prices_screen.py
git commit -m "style: group prices screen materials and rates into rounded cards"
```

---

### Task 9: Rebuild the stats screen as a KPI card dashboard

**Files:**
- Modify: `app/screens/stats_screen.py`

**Interfaces:**
- Consumes: `theme.card`, `theme.SPACING` (Task 1); `db.stats()`, `db.STATUSES`, `pricing.money` (unchanged). Produces: `StatsScreen()` still has a zero-argument `.refresh()` — `app/main.py`'s `on_db_changed()` calls `stats_screen.refresh()` with no arguments, unchanged.

- [ ] **Step 1: Rewrite `app/screens/stats_screen.py`**

Replace the entire file with:

```python
"""Экран «Статистика»: карточки с ключевыми показателями и разбивка по статусам/материалам."""
import flet as ft

import db
import pricing
from app import theme


class StatsScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING)
        self.kpi_row = ft.Row(spacing=theme.SPACING, wrap=True)
        self.details_column = ft.Column(spacing=6)
        self.controls = [
            ft.Text("Статистика", size=20, weight=ft.FontWeight.BOLD),
            self.kpi_row,
            theme.card(self.details_column),
        ]
        self.refresh()

    def refresh(self) -> None:
        s = db.stats()
        total = sum(s["by_status"].values())

        self.kpi_row.controls = [
            self._kpi_card("Выручка", pricing.money(s["revenue"])),
            self._kpi_card("Прибыль", pricing.money(s["profit"])),
            self._kpi_card("Ждём оплату", pricing.money(s["unpaid"])),
            self._kpi_card("Заказов всего", str(total)),
        ]

        status_lines = [
            ft.Text(f"{label}: {s['by_status'].get(code, 0)}")
            for code, label in db.STATUSES.items() if s["by_status"].get(code)
        ] or [ft.Text("Заказов пока нет.", italic=True)]
        material_lines = [
            ft.Text(f"• {name}: {grams / 1000:.2f} кг") for name, grams in s["materials"]
        ] or [ft.Text("—")]

        self.details_column.controls = [
            ft.Text(f"Этот месяц: {s['month_orders']} заказов, оплачено {pricing.money(s['month_revenue'])}"),
            ft.Divider(),
            ft.Text("По статусам:", weight=ft.FontWeight.BOLD),
            *status_lines,
            ft.Divider(),
            ft.Text(f"Расход материала (всего {s['grams'] / 1000:.2f} кг):", weight=ft.FontWeight.BOLD),
            *material_lines,
        ]

        if self.page:
            self.update()

    def _kpi_card(self, label: str, value: str) -> ft.Control:
        return theme.card(
            ft.Column([
                ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(value, size=20, weight=ft.FontWeight.BOLD),
            ], spacing=4, tight=True),
            width=180,
        )
```

`db.stats()`'s return shape (`by_status`, `revenue`, `profit`, `unpaid`, `grams`, `month_orders`, `month_revenue`, `materials`) is unchanged — only how the values are laid out changes.

- [ ] **Step 2: Run full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 3: Manually verify**

Create a temporary `scratch_stats.py` (not committed):

```python
import flet as ft

import db
from app.screens.stats_screen import StatsScreen

db.init()
order_id = db.add_order({"client": "Тест", "contact": "", "material": "PLA",
                          "weight_g": 100, "print_hours": 1, "qty": 1, "cost": 400, "price": 500})
db.update_order(order_id, paid=1)


def main(page: ft.Page):
    page.add(StatsScreen())


ft.app(target=main)
```

Run: `.venv\Scripts\python.exe scratch_stats.py`
Expected: a row of 4 compact rounded KPI cards (Выручка 500, Прибыль 100, Ждём оплату 0, Заказов всего 1) above a details card showing the month summary, status breakdown, and material usage — no more flat stacked text list. Delete the scratch script (and `orders.db` if freshly created) afterward.

- [ ] **Step 4: Commit**

```bash
git add app/screens/stats_screen.py
git commit -m "style: rebuild stats screen as a KPI card dashboard"
```

---

### Task 10: Full-app manual verification pass

**Files:**
- None (verification only — no code changes expected unless this step reveals a real bug, in which case fix it in the relevant file and note the deviation in the report)

**Interfaces:**
- None — this task is the final gate confirming Tasks 1-9 work together as a whole app.

- [ ] **Step 1: Run the full automated test suite one more time**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS (all tests from Tasks 1-9 plus every pre-existing test)

- [ ] **Step 2: Manually verify the whole app**

Run: `.venv\Scripts\python.exe app\main.py`

Verify, in one continuous session:
1. Every one of the 5 navigation sections (Заказы, Новый заказ, Клиенты, Цены, Статистика) renders with rounded cards and visible spacing — no leftover flat/unstyled sections.
2. Click the theme-toggle icon button 3 times (system → light → dark → system) — the whole app's colors switch each time, including inside cards, and the icon updates.
3. Close the app and reopen it — it comes back in the same theme you left it in (not reset to system).
4. Create a new order, open it from the orders list, edit a few fields, go back, reopen it, delete it — all still work exactly as before the redesign (this exercises the exact flow that Task 14 of the previous plan fixed a crash in — confirm it's still crash-free with the new card layout).
5. Navigate between all 5 tabs repeatedly (10+ times) and confirm the app stays responsive — this is the regression check for the `page.overlay` leak fixed in commit `f129b21`, now under the new layout.

- [ ] **Step 3: Report**

No commit needed for this task unless Step 2 revealed and required fixing a real bug — in that case, fix it, add/update a test if the fix is testable, and commit with a message describing the bug found and fixed.

---

## Self-Review Notes

- **Spec coverage:** `app/theme.py` module with card layout + Material 3 accent (Task 1) ✓; theme toggle persisted via `db.settings`, default system (Tasks 2-3) ✓; card-based regrouping of all six screens per the spec's per-screen breakdown (Tasks 4-9) ✓; stats screen becomes a KPI dashboard, resolving the deferred finding from the previous plan's final review (Task 9) ✓; navigation layout and business logic explicitly unchanged (Global Constraints) ✓.
- **Placeholder scan:** no TBD/TODO; every step has concrete code or a concrete manual-verification script.
- **Type/signature consistency:** every screen's constructor and `.refresh()` signature is called out explicitly as unchanged in each task's Interfaces section, and Task 3's `app/main.py` diff is written against those exact, unchanged signatures — no cross-task mismatch.
