# Standalone Mode, Excel Export, Google Sheets Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the Telegram bot entirely (Mochi Desktop becomes the sole, fully local data owner), add a one-click Excel export of all data, and add automatic one-way sync of the same data to a Google Sheet via a service account.

**Architecture:** `bot.py`, `start.bat`, `app/telegram_files.py`, and the `aiogram`/`httpx` dependencies are removed outright. A new `app/export.py` is the single source of truth for "what data goes in an export" — plain Python row-lists built from `db.py`/`pricing.py`, with no knowledge of the output format. Two thin writers consume it: `app/excel_writer.py` (local `.xlsx` via `openpyxl`, triggered by a button) and `app/sheets_sync.py` (Google Sheets API via a service account, triggered automatically by the existing `LiveSync`/`on_db_changed()` change-detection mechanism already wired into `app/main.py`).

**Tech Stack:** Python, Flet, `openpyxl`, `google-api-python-client`, `google-auth`, `google-auth-httplib2`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-24-standalone-excel-sheets.md`

## Global Constraints

- The app must keep working fully standalone with no `.env` file at all — missing Google credentials must never crash startup or any user action, only silently skip cloud sync (matching the existing offline-first precedent already established for the now-removed Telegram integration).
- `app/export.py` is the only place that reads `db.py`/`pricing.py` for export purposes — `app/excel_writer.py` and `app/sheets_sync.py` must not query `db.py` directly, only consume `app/export.py`'s functions, so the three sheets' contents can never drift between the two output formats.
- Google Sheets sync is automatic-only (driven by `on_db_changed()`), no manual "sync now" button, and sync failures are logged (`logging.warning`) only — never surfaced to the user via dialog/snackbar, since it's an unrequested background process.
- Excel export IS user-initiated (a button click) and DOES get a snackbar for success/failure, since it's a direct action the user is waiting on.
- No screen constructor/`.refresh()` signature changes anywhere this plan touches, beyond what's explicitly specified in a task.

---

## File Structure

**Create:**
- `app/export.py` — data-shaping: `build_orders_sheet()`, `build_customers_sheet()`, `build_prices_sheet()`, `build_all_sheets()`.
- `tests/test_export.py`
- `app/excel_writer.py` — `export_to_excel(path)` via `openpyxl`.
- `tests/test_excel_writer.py`
- `app/sheets_sync.py` — `is_configured()`, `sync_now()`, `sync_in_background()`, `SheetsSyncError`.
- `tests/test_sheets_sync.py`

**Modify:**
- `db.py` — add `list_orders_all()` (no row limit, used only by export/sync).
- `tests/test_db_baseline.py` — test for `list_orders_all()`.
- `app/screens/order_detail.py` — remove the Telegram-download attachment action and its imports.
- `app/main.py` — add the Excel-export button; wire `sheets_sync.sync_in_background()` into `on_db_changed()`.
- `requirements.txt` — remove `aiogram`, `httpx`; add `openpyxl`, `google-api-python-client`, `google-auth`, `google-auth-httplib2`.
- `.env.example` — remove `BOT_TOKEN`/`ADMIN_IDS`; add `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE`.
- `README.md` — remove all bot/Telegram content, document Excel export and the Google Sheets one-time setup walkthrough.

**Delete:**
- `bot.py`, `start.bat`, `app/telegram_files.py`, `tests/test_telegram_files.py`.

---

### Task 1: Retire the Telegram bot process

**Files:**
- Delete: `bot.py`, `start.bat`
- Modify: `requirements.txt`, `.env.example`, `README.md`

**Interfaces:**
- Produces: nothing new — this task only removes the bot process. `db.py`/`pricing.py` (which `bot.py` used to import from) are untouched and continue to be used by the app.

- [ ] **Step 1: Delete the bot files**

```bash
git rm bot.py start.bat
```

- [ ] **Step 2: Remove `aiogram` from `requirements.txt`**

Find:
```
aiogram>=3.13,<4
python-dotenv>=1.0
flet>=0.24,<0.28
httpx>=0.27,<1
pytest>=8.0,<9
```

Replace with (this task only drops `aiogram`; `httpx` is still used by `app/telegram_files.py` until Task 2 removes that module and drops `httpx` too — don't remove it here):

```
python-dotenv>=1.0
flet>=0.24,<0.28
httpx>=0.27,<1
pytest>=8.0,<9
```

- [ ] **Step 3: Remove Telegram settings from `.env.example`**

Find:
```
BOT_TOKEN=токен_от_BotFather
ADMIN_IDS=
```

Replace with an empty file (0 bytes) — later tasks (Task 7) will add the Google Sheets variables here. If your tool requires non-empty file content, it's fine to leave this file temporarily empty; Task 7 populates it.

- [ ] **Step 4: Update `README.md`**

Replace the entire file with:

```markdown
# Mochi Desktop — панель управления заказами 3D-печати

Полностью локальное Windows-приложение для приёма и ведения заказов на
3D-печать. Все данные хранятся только на вашем компьютере, в файле
`orders.db` рядом с приложением — никуда в сеть не уходят, кроме
опциональной синхронизации в вашу собственную Google Таблицу (см. ниже).

## Запуск

Дважды кликнуть `start_app.bat` (при первом запуске сам создаст `.venv`
и поставит зависимости). Приложение работает, пока открыто окно.

Вручную:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app\main.py
```

## Что умеет

- **Заказы** — список с фильтрами и поиском, карточка заказа: статус,
  оплата, цена, срок, заметки, вложения, удаление.
- **Новый заказ** — форма создания с автоматическим расчётом цены и
  прикреплением файлов (фото, STL и т.д.) прямо с компьютера.
- **Клиенты** — справочник с историей заказов и суммами (оплачено/долг).
- **Цены** — редактирование материалов, ставки часа, цены
  реверс-моделирования, валюты.
- **Статистика** — дашборд: выручка, прибыль, долги, расход материала.
- **Тема** — светлая/тёмная/системная, кнопка в интерфейсе.
- **Экспорт в Excel** — кнопка в интерфейсе, сохраняет все заказы,
  клиентов и цены в один `.xlsx`-файл.
- **Синхронизация с Google Таблицами** — опциональная, см. ниже.

## Формула цены

```
себестоимость = вес × кол-во × цена_материала/1000 + часы × кол-во × цена_часа
цена = себестоимость (+ доплата за реверс-моделирование, если нет своей 3D-модели)
```

Материалы, ставка часа и валюта редактируются на экране «Цены».

## Синхронизация с Google Таблицами (опционально)

Приложение может автоматически поддерживать актуальную копию заказов,
клиентов и цен в вашей собственной Google Таблице. Без этой настройки
приложение работает как обычно — просто без облачной копии.

Настройка (один раз, 10-15 минут):

1. Откройте [Google Cloud Console](https://console.cloud.google.com/),
   создайте новый проект (или используйте существующий).
2. Включите **Google Sheets API** для этого проекта (раздел
   «APIs & Services» → «Enable APIs and Services»).
3. Создайте служебный аккаунт (Service Account): «IAM & Admin» →
   «Service Accounts» → «Create Service Account». Роль не важна — доступ
   выдаётся напрямую на таблицу (шаг 5).
4. Откройте созданный аккаунт → вкладка «Keys» → «Add Key» → «Create new
   key» → JSON. Скачается `.json`-файл — сохраните его рядом с
   приложением (например, `google-service-account.json`), **никому не
   пересылайте этот файл**.
5. Откройте свою Google Таблицу → «Настройки доступа» → добавьте адрес
   служебного аккаунта (выглядит как
   `имя@проект.iam.gserviceaccount.com`, указан в JSON-файле и в консоли)
   с правами **Редактор**.
6. Скопируйте ID таблицы — это часть ссылки между `/d/` и `/edit`,
   например для `https://docs.google.com/spreadsheets/d/ABC123/edit`
   это `ABC123`.
7. Скопируйте `.env.example` в `.env` и заполните:
   ```
   GOOGLE_SHEET_ID=ID_из_шага_6
   GOOGLE_SERVICE_ACCOUNT_FILE=google-service-account.json
   ```

После этого любое изменение в приложении (новый заказ, смена цены и т.д.)
через несколько секунд автоматически появляется в таблице — три листа:
«Заказы», «Клиенты», «Цены» (создаются сами при первой синхронизации).

Собрать отдельный `.exe`:

```bash
.venv\Scripts\flet pack app\main.py --name "Mochi Desktop"
```
```

- [ ] **Step 5: Verify nothing else references the deleted files**

Run: `grep -rn "bot.py\|start\.bat\b" --include="*.py" --include="*.md" .` (excluding `start_app.bat`, which stays)
Expected: no remaining references outside of this plan/spec's own documentation files.

- [ ] **Step 6: Run the full test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS — deleting `bot.py`/`start.bat` doesn't affect any test (nothing in `tests/` imports `bot.py`).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .env.example README.md
git commit -m "feat: retire the Telegram bot, app is now fully standalone"
```

---

### Task 2: Remove the Telegram file-download feature

**Files:**
- Delete: `app/telegram_files.py`, `tests/test_telegram_files.py`
- Modify: `app/screens/order_detail.py`, `requirements.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing new — `OrderDetailScreen`'s constructor/`.refresh()` signature and every other method besides `_attachment_row`/`_download_attachment` are unchanged.

- [ ] **Step 1: Delete the Telegram file-download module and its tests**

```bash
git rm app/telegram_files.py tests/test_telegram_files.py
```

- [ ] **Step 2: Update `app/screens/order_detail.py`**

Find:
```python
import flet as ft
import httpx

import db
import pricing
from app import theme
from app.telegram_files import TelegramFileError, download_file
```

Replace with:
```python
import flet as ft

import db
import pricing
from app import theme
```

Find:
```python
    def _attachment_row(self, a) -> ft.Control:
        label = a["filename"] or a["file_id"] or f"вложение #{a['id']}"
        actions = [ft.IconButton(ft.Icons.DELETE, on_click=lambda e, aid=a["id"]: self._delete_attachment(aid))]
        if a["source"] == "telegram":
            actions.insert(
                0, ft.IconButton(ft.Icons.DOWNLOAD, on_click=lambda e, aid=a["id"]: self._download_attachment(aid))
            )
        else:
            actions.insert(0, ft.IconButton(ft.Icons.FOLDER_OPEN, on_click=lambda e, p=a["local_path"]: self._open_path(p)))
        return ft.Row([ft.Text(f"📎 {label} ({a['source']})", expand=True), *actions])
```

Replace with:
```python
    def _attachment_row(self, a) -> ft.Control:
        label = a["filename"] or a["file_id"] or f"вложение #{a['id']}"
        actions = [ft.IconButton(ft.Icons.DELETE, on_click=lambda e, aid=a["id"]: self._delete_attachment(aid))]
        if a["local_path"]:
            actions.insert(0, ft.IconButton(ft.Icons.FOLDER_OPEN, on_click=lambda e, p=a["local_path"]: self._open_path(p)))
        return ft.Row([ft.Text(f"📎 {label} ({a['source']})", expand=True), *actions])
```

Find:
```python
    def _download_attachment(self, attachment_id: int) -> None:
        attachment = db.get_attachment(attachment_id)
        try:
            path = download_file(attachment["file_id"])
        except (TelegramFileError, httpx.HTTPError, OSError) as exc:
            self.status_banner.color = ft.Colors.RED
            self.status_banner.value = str(exc)
            self.update()
            return
        self.status_banner.color = None
        self.status_banner.value = f"Скачано: {path}"
        self.update()

    def _delete_attachment(self, attachment_id: int) -> None:
```

Replace with:
```python
    def _delete_attachment(self, attachment_id: int) -> None:
```

(This removes the entire `_download_attachment` method — nothing else in that region changes.)

- [ ] **Step 3: Remove `httpx` from `requirements.txt`**

Find:
```
python-dotenv>=1.0
flet>=0.24,<0.28
httpx>=0.27,<1
pytest>=8.0,<9
```

Replace with:
```
python-dotenv>=1.0
flet>=0.24,<0.28
pytest>=8.0,<9
```

- [ ] **Step 4: Run the full test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS — no test references `app.telegram_files` or `_download_attachment` (the deleted `tests/test_telegram_files.py` was the only test of the removed module).

- [ ] **Step 5: Manually verify**

Create a temporary `scratch_order_detail.py` in the repo root (not committed):

```python
import flet as ft

import db
from app.screens.order_detail import OrderDetailScreen

db.init()
order_id = db.add_order({"client": "Проверка", "contact": "", "material": "PLA",
                          "weight_g": 50, "print_hours": 1, "qty": 1, "cost": 100, "price": 150})
db.add_attachment(order_id, "telegram", file_id="LEGACY123", file_type="photo")


def main(page: ft.Page):
    page.add(OrderDetailScreen(order_id=order_id, on_back=lambda: print("back")))


ft.app(target=main)
```

Run: `.venv\Scripts\python.exe scratch_order_detail.py`
Expected: the legacy Telegram-sourced attachment shows in the list with only a delete icon (no download icon), and no exception is raised. Delete the scratch script (and `orders.db` if freshly created) afterward.

- [ ] **Step 6: Commit**

```bash
git add app/screens/order_detail.py requirements.txt
git commit -m "feat: remove Telegram file-download feature (no more Telegram integration)"
```

---

### Task 3: `db.list_orders_all()` for export/sync

**Files:**
- Modify: `db.py`
- Test: `tests/test_db_baseline.py`

**Interfaces:**
- Produces: `db.list_orders_all() -> list[sqlite3.Row]` — every order, no limit, ordered by `id`. Relied on by Task 4.

- [ ] **Step 1: Write the failing test**

In `tests/test_db_baseline.py`, add:

```python
def test_list_orders_all_returns_every_order_unordered_by_limit(temp_db):
    for i in range(3):
        db.add_order({"client": f"Клиент {i}", "contact": "", "cost": 0, "price": 0})
    orders = db.list_orders_all()
    assert len(orders) == 3
    assert [o["id"] for o in orders] == sorted(o["id"] for o in orders)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_baseline.py -k list_orders_all -v`
Expected: FAIL with `AttributeError: module 'db' has no attribute 'list_orders_all'`

- [ ] **Step 3: Implement `list_orders_all()`**

In `db.py`, find:

```python
def search_orders(text: str, limit: int = 40):
```

Insert immediately before it:

```python
def list_orders_all():
    """Все заказы без ограничения — используется для экспорта/синхронизации."""
    with _conn() as c:
        return c.execute("SELECT * FROM orders ORDER BY id").fetchall()


def search_orders(text: str, limit: int = 40):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_baseline.py -v`
Expected: PASS (all tests including the new one)

Run full suite: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db_baseline.py
git commit -m "feat: add list_orders_all() for export/sync (no row limit)"
```

---

### Task 4: `app/export.py` — shared data-shaping for exports

**Files:**
- Create: `app/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `db.list_orders_all()` (Task 3), `db.list_customers()`, `db.get_settings()`, `db.STATUSES`, `pricing.money` is NOT used here (raw numeric values go in the export, not formatted currency strings, so spreadsheet software can sum/sort them).
- Produces: `export.build_orders_sheet() -> list[list]`, `export.build_customers_sheet() -> list[list]`, `export.build_prices_sheet() -> list[list]`, `export.build_all_sheets() -> dict[str, list[list]]` (keys: `"Заказы"`, `"Клиенты"`, `"Цены"`). Relied on by Task 5 and Task 7.

- [ ] **Step 1: Write the failing test**

Create `tests/test_export.py`:

```python
"""Тесты для app/export.py — сборка строк для Excel/Google Таблиц."""
import db
from app import export


def test_build_orders_sheet_has_header_row_and_one_data_row(temp_db):
    order_id = db.add_order({
        "client": "Иван", "contact": "@ivan", "material": "PLA",
        "weight_g": 100, "print_hours": 2, "qty": 1, "cost": 400, "price": 600,
    })
    db.update_order(order_id, paid=1)

    rows = export.build_orders_sheet()

    assert rows[0][0] == "ID"
    assert len(rows) == 2
    data_row = rows[1]
    assert data_row[0] == order_id
    assert data_row[1] == "Иван"
    assert data_row[2] == "@ivan"


def test_build_orders_sheet_shows_paid_status_in_russian(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    db.update_order(order_id, paid=1)
    rows = export.build_orders_sheet()
    header = rows[0]
    paid_col = header.index("Оплачен")
    assert rows[1][paid_col] == "Да"


def test_build_customers_sheet_includes_aggregates(temp_db):
    order_id = db.add_order({"client": "Мария", "contact": "@maria", "cost": 100, "price": 200})
    db.update_order(order_id, paid=1)

    rows = export.build_customers_sheet()

    assert rows[0][0] == "ID"
    assert len(rows) == 2
    header = rows[0]
    data_row = rows[1]
    assert data_row[header.index("Имя")] == "Мария"
    assert data_row[header.index("Заказов")] == 1
    assert data_row[header.index("Оплачено")] == 200


def test_build_prices_sheet_has_materials_and_rates_sections(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 55)

    rows = export.build_prices_sheet()

    assert rows[0] == ["Материал", "Цена за кг"]
    assert ["PLA", 4000] in rows
    assert ["Параметр", "Значение"] in rows
    assert ["Ставка часа печати", 55] in rows


def test_build_all_sheets_returns_all_three_named_sheets(temp_db):
    sheets = export.build_all_sheets()
    assert set(sheets.keys()) == {"Заказы", "Клиенты", "Цены"}
    for rows in sheets.values():
        assert len(rows) >= 1  # хотя бы заголовок
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.export'`

- [ ] **Step 3: Implement `app/export.py`**

```python
"""Сборка данных заказов/клиентов/цен в виде простых строк — общий источник
для локального Excel-экспорта и синхронизации с Google Таблицами."""
from typing import Any

import db

ORDER_COLUMNS = [
    "ID", "Клиент", "Контакт", "Описание", "Материал", "Цвет", "Вес, г",
    "Часы печати", "Кол-во", "Срок", "Статус", "Оплачен", "Себестоимость",
    "Цена", "Заметки", "Создан",
]

CUSTOMER_COLUMNS = ["ID", "Имя", "Контакт", "Заметки", "Заказов", "Оплачено", "Долг", "Создан"]


def build_orders_sheet() -> list[list[Any]]:
    rows: list[list[Any]] = [ORDER_COLUMNS]
    for o in db.list_orders_all():
        rows.append([
            o["id"],
            o["client"],
            o["contact"] or "",
            o["description"] or "",
            o["material"] or "",
            o["color"] or "",
            o["weight_g"] or 0,
            o["print_hours"] or 0,
            o["qty"] or 1,
            o["deadline"] or "",
            db.STATUSES.get(o["status"], o["status"]),
            "Да" if o["paid"] else "Нет",
            o["cost"] or 0,
            o["price"] or 0,
            o["notes"] or "",
            o["created_at"],
        ])
    return rows


def build_customers_sheet() -> list[list[Any]]:
    rows: list[list[Any]] = [CUSTOMER_COLUMNS]
    for c in db.list_customers():
        rows.append([
            c["id"],
            c["name"],
            c["contact"] or "",
            c["notes"] or "",
            c["orders_count"],
            c["paid_total"],
            c["debt_total"],
            c["created_at"],
        ])
    return rows


def build_prices_sheet() -> list[list[Any]]:
    settings = db.get_settings()
    rows: list[list[Any]] = [["Материал", "Цена за кг"]]
    rows.extend([name, price] for name, price in settings["materials"].items())
    rows.append([])
    rows.append(["Параметр", "Значение"])
    rows.append(["Ставка часа печати", settings["hour_rate"]])
    rows.append(["Реверс-моделирование", settings["reverse_price"]])
    rows.append(["Валюта", settings["currency"]])
    return rows


def build_all_sheets() -> dict[str, list[list[Any]]]:
    return {
        "Заказы": build_orders_sheet(),
        "Клиенты": build_customers_sheet(),
        "Цены": build_prices_sheet(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_export.py -v`
Expected: PASS (all 5 tests)

Run full suite: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/export.py tests/test_export.py
git commit -m "feat: add app/export.py as the shared data source for Excel/Sheets exports"
```

---

### Task 5: `app/excel_writer.py` — local `.xlsx` export

**Files:**
- Create: `app/excel_writer.py`
- Test: `tests/test_excel_writer.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `export.build_all_sheets()` (Task 4).
- Produces: `excel_writer.export_to_excel(path: str | Path) -> None`. Relied on by Task 6.

- [ ] **Step 1: Add `openpyxl` to `requirements.txt`**

Find:
```
python-dotenv>=1.0
flet>=0.24,<0.28
pytest>=8.0,<9
```

Replace with:
```
python-dotenv>=1.0
flet>=0.24,<0.28
pytest>=8.0,<9
openpyxl>=3.1,<4
```

Install it: `.venv\Scripts\python.exe -m pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `tests/test_excel_writer.py`:

```python
"""Тесты для app/excel_writer.py — запись .xlsx через openpyxl."""
import openpyxl

import db
from app import excel_writer


def test_export_to_excel_creates_file_with_three_sheets(temp_db, tmp_path):
    db.add_order({"client": "Иван", "contact": "", "material": "PLA",
                   "weight_g": 100, "print_hours": 1, "qty": 1, "cost": 100, "price": 200})
    dest = tmp_path / "export.xlsx"

    excel_writer.export_to_excel(dest)

    assert dest.exists()
    wb = openpyxl.load_workbook(dest)
    assert set(wb.sheetnames) == {"Заказы", "Клиенты", "Цены"}


def test_export_to_excel_writes_order_row_correctly(temp_db, tmp_path):
    order_id = db.add_order({"client": "Мария", "contact": "@maria", "material": "PETG",
                              "weight_g": 50, "print_hours": 2, "qty": 1, "cost": 300, "price": 500})
    dest = tmp_path / "export.xlsx"

    excel_writer.export_to_excel(dest)

    wb = openpyxl.load_workbook(dest)
    ws = wb["Заказы"]
    header = [cell.value for cell in ws[1]]
    data_row = [cell.value for cell in ws[2]]
    assert header[0] == "ID"
    assert data_row[header.index("ID")] == order_id
    assert data_row[header.index("Клиент")] == "Мария"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_excel_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.excel_writer'`

- [ ] **Step 4: Implement `app/excel_writer.py`**

```python
"""Запись заказов/клиентов/цен в .xlsx через openpyxl."""
from pathlib import Path

from openpyxl import Workbook

from app.export import build_all_sheets


def export_to_excel(path: str | Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)  # убираем дефолтный пустой лист "Sheet"
    for sheet_name, rows in build_all_sheets().items():
        ws = wb.create_sheet(title=sheet_name)
        for row in rows:
            ws.append(row)
    wb.save(path)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_excel_writer.py -v`
Expected: PASS (both tests)

Run full suite: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/excel_writer.py tests/test_excel_writer.py requirements.txt
git commit -m "feat: add app/excel_writer.py for local .xlsx export"
```

---

### Task 6: Wire the Excel-export button into `app/main.py`

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `excel_writer.export_to_excel(path)` (Task 5).
- Produces: nothing new for later tasks.

- [ ] **Step 1: Update `app/main.py`**

Find:
```python
import db
from app import theme
from app.live_sync import LiveSync
```

Replace with:
```python
import db
from app import theme
from app.excel_writer import export_to_excel
from app.live_sync import LiveSync
```

Find:
```python
    theme_button = ft.IconButton(
        icon=theme.THEME_ICONS.get(current_theme_mode, theme.THEME_ICONS["system"]),
        tooltip="Тема оформления",
        on_click=toggle_theme,
    )

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        leading=theme_button,
```

Replace with:
```python
    theme_button = ft.IconButton(
        icon=theme.THEME_ICONS.get(current_theme_mode, theme.THEME_ICONS["system"]),
        tooltip="Тема оформления",
        on_click=toggle_theme,
    )

    def on_export_file_selected(e: ft.FilePickerResultEvent) -> None:
        if not e.path:
            return
        try:
            export_to_excel(e.path)
            page.open(ft.SnackBar(ft.Text(f"Экспортировано: {e.path}")))
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
```

(`export_file_picker` is added to `page.overlay` exactly once here, in `main()`'s own top-level scope — `main()` runs once per page lifetime, so there's no remount/leak risk like the per-screen `FilePicker`s had before their `did_mount`/`will_unmount` fix; this one never needs a `will_unmount` counterpart.)

- [ ] **Step 2: Run the full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 3: Manually verify**

Run: `.venv\Scripts\python.exe app\main.py`

Verify: the navigation rail now shows two icons at the top (theme toggle, then export); clicking the export icon opens a native "Save As" dialog defaulting to `mochi_export.xlsx`; after choosing a location, a snackbar confirms the export and the resulting file opens correctly in Excel/LibreOffice with three sheets (Заказы/Клиенты/Цены) containing your test data.

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: add Excel export button to the navigation rail"
```

---

### Task 7: `app/sheets_sync.py` — Google Sheets sync module

**Files:**
- Create: `app/sheets_sync.py`
- Test: `tests/test_sheets_sync.py`
- Modify: `requirements.txt`, `.env.example`

**Interfaces:**
- Consumes: `export.build_all_sheets()` (Task 4).
- Produces: `sheets_sync.SheetsSyncError(RuntimeError)`, `sheets_sync.is_configured() -> bool`, `sheets_sync.sync_now() -> None` (raises `SheetsSyncError` on failure), `sheets_sync.sync_in_background(on_error: Callable[[Exception], None] | None = None) -> None`. Relied on by Task 8.

- [ ] **Step 1: Add Google API dependencies to `requirements.txt`**

Find:
```
python-dotenv>=1.0
flet>=0.24,<0.28
pytest>=8.0,<9
openpyxl>=3.1,<4
```

Replace with:
```
python-dotenv>=1.0
flet>=0.24,<0.28
pytest>=8.0,<9
openpyxl>=3.1,<4
google-api-python-client>=2.100,<3
google-auth>=2.23,<3
google-auth-httplib2>=0.2,<1
```

Install: `.venv\Scripts\python.exe -m pip install -r requirements.txt`

- [ ] **Step 2: Add Google Sheets settings to `.env.example`**

Task 1 left `.env.example` empty (0 bytes) after removing the Telegram variables. Set its content to:
```
GOOGLE_SHEET_ID=
GOOGLE_SERVICE_ACCOUNT_FILE=
```

- [ ] **Step 3: Write the failing test**

Create `tests/test_sheets_sync.py`:

```python
"""Тесты для app/sheets_sync.py — Google API-клиент подменяется фейком."""
import db
from app import sheets_sync


class _FakeValues:
    def __init__(self, calls):
        self._calls = calls

    def clear(self, spreadsheetId, range):
        self._calls.append(("clear", range))
        return self

    def update(self, spreadsheetId, range, valueInputOption, body):
        self._calls.append(("update", range, body["values"]))
        return self

    def execute(self):
        return {}


class _FakeSpreadsheets:
    def __init__(self, calls, existing_sheet_titles):
        self._calls = calls
        self._existing = existing_sheet_titles

    def get(self, spreadsheetId):
        self._pending = "get"
        return self

    def batchUpdate(self, spreadsheetId, body):
        for req in body["requests"]:
            self._existing.append(req["addSheet"]["properties"]["title"])
        self._pending = "batchUpdate"
        return self

    def values(self):
        return _FakeValues(self._calls)

    def execute(self):
        if self._pending == "get":
            return {"sheets": [{"properties": {"title": t}} for t in self._existing]}
        return {}


class _FakeService:
    def __init__(self, existing_sheet_titles):
        self._calls = []
        self._existing = existing_sheet_titles

    def spreadsheets(self):
        return _FakeSpreadsheets(self._calls, self._existing)


def test_is_configured_false_when_env_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
    assert sheets_sync.is_configured() is False


def test_is_configured_true_when_both_env_set(monkeypatch, tmp_path):
    key_file = tmp_path / "key.json"
    key_file.write_text("{}")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "abc123")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(key_file))
    assert sheets_sync.is_configured() is True


def test_sync_now_updates_all_three_sheets(monkeypatch, temp_db):
    db.add_order({"client": "Тест", "contact": "", "cost": 0, "price": 0})
    monkeypatch.setenv("GOOGLE_SHEET_ID", "fake-id")
    fake_service = _FakeService(existing_sheet_titles=["Заказы", "Клиенты", "Цены"])
    monkeypatch.setattr(sheets_sync, "_build_service", lambda: fake_service)

    sheets_sync.sync_now()

    update_ranges = {call[1] for call in fake_service._calls if call[0] == "update"}
    assert update_ranges == {"Заказы!A1", "Клиенты!A1", "Цены!A1"}


def test_sync_now_creates_missing_sheets(monkeypatch, temp_db):
    monkeypatch.setenv("GOOGLE_SHEET_ID", "fake-id")
    fake_service = _FakeService(existing_sheet_titles=[])  # пустая таблица, ни одного листа
    monkeypatch.setattr(sheets_sync, "_build_service", lambda: fake_service)

    sheets_sync.sync_now()

    assert set(fake_service._existing) == {"Заказы", "Клиенты", "Цены"}


def test_sync_now_raises_sheets_sync_error_when_sheet_id_missing(monkeypatch, temp_db):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    try:
        sheets_sync.sync_now()
        assert False, "должно было бросить SheetsSyncError"
    except sheets_sync.SheetsSyncError:
        pass


def test_sync_in_background_does_nothing_when_not_configured(monkeypatch, temp_db):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
    called = []
    monkeypatch.setattr(sheets_sync, "sync_now", lambda: called.append(True))

    sheets_sync.sync_in_background()
    import time
    time.sleep(0.2)  # дать фоновому потоку шанс запуститься, если бы он был запущен

    assert called == []
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sheets_sync.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sheets_sync'`

- [ ] **Step 5: Implement `app/sheets_sync.py`**

```python
"""Автосинхронизация заказов/клиентов/цен в Google Таблицу через служебный аккаунт."""
import logging
import os
import threading
from pathlib import Path
from typing import Callable

from app.export import build_all_sheets

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsSyncError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(os.getenv("GOOGLE_SHEET_ID", "").strip()) and bool(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    )


def _build_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not key_path or not Path(key_path).exists():
        raise SheetsSyncError(f"Файл служебного аккаунта не найден: {key_path!r}")
    creds = Credentials.from_service_account_file(key_path, scopes=_SCOPES)
    return build("sheets", "v4", credentials=creds)


def _ensure_sheets_exist(service, sheet_id: str, sheet_names: list[str]) -> None:
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in spreadsheet.get("sheets", [])}
    missing = [name for name in sheet_names if name not in existing]
    if missing:
        requests = [{"addSheet": {"properties": {"title": name}}} for name in missing]
        service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()


def sync_now() -> None:
    """Синхронно перезаписывает все три листа в Google Таблице. Бросает SheetsSyncError при любом сбое."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if not sheet_id:
        raise SheetsSyncError("GOOGLE_SHEET_ID не задан в .env")
    try:
        service = _build_service()
        sheets = build_all_sheets()
        _ensure_sheets_exist(service, sheet_id, list(sheets.keys()))
        for sheet_name, rows in sheets.items():
            service.spreadsheets().values().clear(spreadsheetId=sheet_id, range=sheet_name).execute()
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=f"{sheet_name}!A1",
                valueInputOption="RAW", body={"values": rows},
            ).execute()
    except SheetsSyncError:
        raise
    except Exception as exc:  # noqa: BLE001 - любая ошибка сети/API оборачивается в единый тип
        raise SheetsSyncError(str(exc)) from exc


def sync_in_background(on_error: Callable[[Exception], None] | None = None) -> None:
    """Запускает sync_now() в отдельном потоке, если синхронизация настроена; иначе ничего не делает."""
    if not is_configured():
        return

    def _run() -> None:
        try:
            sync_now()
        except SheetsSyncError as exc:
            logging.warning("Синхронизация с Google Таблицами не удалась: %s", exc)
            if on_error:
                on_error(exc)

    threading.Thread(target=_run, daemon=True).start()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sheets_sync.py -v`
Expected: PASS (all 6 tests)

Run full suite: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/sheets_sync.py tests/test_sheets_sync.py requirements.txt .env.example
git commit -m "feat: add app/sheets_sync.py for automatic Google Sheets sync"
```

---

### Task 8: Wire `sheets_sync` into `app/main.py`'s live-sync

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `sheets_sync.sync_in_background()` (Task 7).
- Produces: nothing new — this is the final integration point.

- [ ] **Step 1: Update `app/main.py`**

Find:
```python
import db
from app import theme
from app.excel_writer import export_to_excel
from app.live_sync import LiveSync
```

Replace with:
```python
import db
from app import sheets_sync, theme
from app.excel_writer import export_to_excel
from app.live_sync import LiveSync
```

Find:
```python
    def on_db_changed() -> None:
        orders_section.refresh(from_sync=True)
        customers_screen.refresh(from_sync=True)
        stats_screen.refresh()
```

Replace with:
```python
    def on_db_changed() -> None:
        orders_section.refresh(from_sync=True)
        customers_screen.refresh(from_sync=True)
        stats_screen.refresh()
        sheets_sync.sync_in_background()
```

- [ ] **Step 2: Run the full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 3: Manually verify (without real Google credentials)**

Run: `.venv\Scripts\python.exe app\main.py` with no `.env` file present (or one without `GOOGLE_SHEET_ID`/`GOOGLE_SERVICE_ACCOUNT_FILE`).

Verify: create/edit an order — the app behaves exactly as before (no crash, no delay, no visible error), since `sheets_sync.sync_in_background()` no-ops when unconfigured. This confirms the offline-first Global Constraint holds.

- [ ] **Step 4: Manually verify with real Google credentials (optional, requires your own setup)**

If you've completed the README's Google Sheets setup walkthrough (Task 1's README section) with a real `.env`, `GOOGLE_SHEET_ID`, and `GOOGLE_SERVICE_ACCOUNT_FILE`: create or edit an order, wait a few seconds, and confirm the target Google Sheet's "Заказы"/"Клиенты"/"Цены" tabs appear (auto-created if missing) and reflect the change.

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "feat: trigger Google Sheets sync from the existing live-sync change detection"
```

---

### Task 9: Full-app manual verification pass

**Files:**
- None (verification only — no code changes expected unless this step reveals a real bug, in which case fix it in the relevant file and note the deviation in the report)

**Interfaces:**
- None — this is the final gate confirming Tasks 1-8 work together as a whole app.

- [ ] **Step 1: Run the full automated test suite one more time**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS (every test from Tasks 1-8 plus every pre-existing test)

- [ ] **Step 2: Confirm no Telegram/bot residue**

Run: `grep -rn "aiogram\|BOT_TOKEN\|telegram" --include="*.py" .` (case-sensitive; `app/telegram_files.py` references inside old commit messages/docs don't count)
Expected: no hits in any `.py` file under `app/`, `db.py`, `pricing.py`, or `tests/` (the word "telegram" may still legitimately appear in the `source` column values `"telegram"` stored in the `attachments` table from legacy data, and in `db.py`'s `_migrate_attachments_v1` migration function, which stays — it's about reading old data, not about talking to Telegram).

- [ ] **Step 3: Manually verify the whole app end-to-end**

Run: `.venv\Scripts\python.exe app\main.py` (with no `.env`, to confirm the fully-standalone case first)

Verify, in one continuous session:
1. The app launches with no `.env` file present at all — no crash, no error dialog.
2. Create a new order, edit it, mark it paid, add a local file attachment, delete a different order.
3. Click "Экспорт в Excel", save the file, open it — confirm three sheets with correct data matching what's in the app.
4. Toggle the theme — still works as before (unaffected by this plan).
5. Navigate through all 5 tabs repeatedly (10+ times) — still responsive (this plan didn't touch the `page.overlay` mechanism, but it's worth reconfirming nothing regressed).

- [ ] **Step 4: Report**

No commit needed for this task unless Step 2 or Step 3 revealed and required fixing a real bug — in that case, fix it, add/update a test if the fix is testable, and commit with a message describing the bug found and fixed.

---

## Self-Review Notes

- **Spec coverage:** Telegram/bot fully removed (Tasks 1-2) ✓; `app/export.py` as single shared data source (Task 4) ✓; Excel export button with save-dialog + snackbar feedback (Tasks 5-6) ✓; Google Sheets auto-sync via the existing live-sync mechanism, silent-on-failure, auto-creates missing sheets (Tasks 7-8) ✓; offline-first constraint (works with no `.env`) explicitly verified (Task 8 Step 3, Task 9 Step 3) ✓; README walkthrough for the one-time Google Cloud service-account setup (Task 1) ✓.
- **Placeholder scan:** no TBD/TODO; every step has concrete code, exact old_string/new_string blocks, or a concrete manual-verification script.
- **Type/signature consistency:** `export.build_all_sheets() -> dict[str, list[list]]` is defined once (Task 4) and consumed identically by `excel_writer.export_to_excel()` (Task 5) and `sheets_sync.sync_now()` (Task 7) — both iterate the same `{sheet_name: rows}` shape, so the three sheets' contents can never drift between the two output formats.
