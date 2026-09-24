# Mochi Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Windows desktop app (Python + Flet) that shares `orders.db` with the existing Telegram bot, giving full CRUD over orders, customers, prices, file attachments, and stats — without depending on Telegram to function.

**Architecture:** Two independent processes (`bot.py`, `app/`) reading/writing the same SQLite file in WAL mode. Business logic (`db.py`, new `pricing.py`) is shared by both via direct Python import — no HTTP layer between them. The app polls the DB every few seconds for live updates and can also create orders/customers/attachments entirely on its own, with no Telegram involvement.

**Tech Stack:** Python 3.10+, Flet (desktop UI), sqlite3 (stdlib), httpx (Telegram Bot API file downloads), pytest (tests).

**Spec:** `docs/superpowers/specs/2026-09-24-desktop-app-design.md`

## Global Constraints

- The app must work fully offline from Telegram: creating/editing orders, customers, prices, and attaching local files must never require `BOT_TOKEN` or network access. Only *downloading a Telegram-sourced attachment* needs the token.
- `bot.py`'s existing behavior and command interface must not change (only its pricing/formatting helpers move to `pricing.py`, imported back in by name).
- All new SQL schema changes are additive and migrate forward automatically in `db.init()`, following the existing `_migrate_pricing_v2` pattern (idempotent, flagged in `settings`).
- SQLite must run in WAL mode so the bot and the app can read/write concurrently.
- No new abstraction beyond what's specified — reuse `db.py`/`pricing.py` functions directly from the app; don't wrap them in extra layers.

---

## File Structure

**Create:**
- `pricing.py` — price calculation + formatting helpers (moved out of `bot.py`), shared by bot and app.
- `tests/conftest.py` — pytest fixture providing a temporary SQLite DB.
- `tests/test_pricing.py`, `tests/test_db_customers.py`, `tests/test_db_attachments.py`, `tests/test_app_scaffold.py`, `tests/test_telegram_files.py`, `tests/test_live_sync.py`
- `app/__init__.py`, `app/main.py` — entry point + navigation shell.
- `app/telegram_files.py` — download/cache Telegram attachments via Bot API.
- `app/live_sync.py` — background polling for live updates.
- `app/screens/__init__.py`
- `app/screens/orders_screen.py` — order list + filters + search.
- `app/screens/order_detail.py` — order view/edit + attachments.
- `app/screens/new_order.py` — create-order form.
- `app/screens/customers_screen.py` — customer directory.
- `app/screens/prices_screen.py` — materials/rates settings.
- `app/screens/stats_screen.py` — stats dashboard.
- `start_app.bat` — first-run setup + launch for the app (mirrors `start.bat`).

**Modify:**
- `bot.py` — remove pricing/formatting function bodies, import them from `pricing.py`.
- `db.py` — WAL mode, `customers` + `attachments` tables and migrations, new query functions, `change_fingerprint()`, `add_order` auto-links customer.
- `requirements.txt` — add `flet`, `httpx`, `pytest`.
- `.gitignore` — ignore `app/files_cache/`, `app/files_storage/`, `.pytest_cache/`.
- `README.md` — document the app alongside the bot.

---

### Task 1: Extract pricing/formatting helpers into `pricing.py`

**Files:**
- Create: `pricing.py`
- Modify: `bot.py:1-231` (remove helper bodies, add import)
- Test: `tests/test_pricing.py`

**Interfaces:**
- Produces: `pricing.money(value: float) -> str`, `pricing.parse_number(text: str | None) -> float | None`, `pricing.parse_hours(text: str | None) -> float | None`, `pricing.parse_date(text: str | None) -> str | None`, `pricing.fmt_date(iso: str | None) -> str`, `pricing.deadline_mark(order) -> str`, `pricing.calc_price(material, weight_g, hours, qty, reverse=False) -> dict`, `pricing.price_breakdown(material, weight_g, hours, qty, reverse=False) -> str`, `pricing.recalc_order_price(oid: int) -> None`. These are relied on by every later task that touches price display/calculation.

- [ ] **Step 1: Write the failing test**

Create `tests/test_pricing.py`:

```python
"""Тесты для pricing.py (используется и ботом, и приложением)."""
import db
import pricing


def test_money_formats_with_currency(temp_db):
    db.set_setting("currency", "₽")
    assert pricing.money(1234) == "1 234 ₽"


def test_parse_number_accepts_comma_decimal():
    assert pricing.parse_number("12,5") == 12.5


def test_parse_number_rejects_negative():
    assert pricing.parse_number("-5") is None


def test_parse_hours_accepts_colon_format():
    assert pricing.parse_hours("2:30") == 2.5


def test_parse_hours_accepts_ru_short_format():
    assert pricing.parse_hours("2ч 30м") == 2.5


def test_parse_date_accepts_relative_words():
    assert pricing.parse_date("сегодня") is not None
    assert pricing.parse_date("завтра") is not None


def test_parse_date_rejects_garbage():
    assert pricing.parse_date("не дата") is None


def test_calc_price_matches_formula(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 50)
    db.set_setting("reverse_price", 1000)
    result = pricing.calc_price("PLA", weight_g=100, hours=2, qty=1)
    assert result["material_cost"] == 100 * 1 * 4000 / 1000
    assert result["time_cost"] == 2 * 1 * 50
    assert result["reverse_cost"] == 0
    assert result["price"] == result["material_cost"] + result["time_cost"]


def test_calc_price_adds_reverse_engineering_cost(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 50)
    db.set_setting("reverse_price", 1000)
    result = pricing.calc_price("PLA", weight_g=0, hours=0, qty=1, reverse=True)
    assert result["reverse_cost"] == 1000
    assert result["price"] == 1000


def test_recalc_order_price_updates_stored_values(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 50)
    order_id = db.add_order({
        "client": "Тест", "contact": "", "material": "PLA",
        "weight_g": 100, "print_hours": 1, "qty": 1, "cost": 0, "price": 0,
    })
    pricing.recalc_order_price(order_id)
    order = db.get_order(order_id)
    assert order["price"] == 100 * 4000 / 1000 + 1 * 50
```

Note: this test file uses a `temp_db` fixture that doesn't exist yet — it will be added in Task 2. For this task, create `tests/conftest.py` now (minimal version) so the test can run:

Create `tests/conftest.py`:

```python
"""Общие pytest-фикстуры."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

import db


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Подменяет db.DB_PATH на временный файл и инициализирует схему."""
    db_path = tmp_path / "test_orders.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init()
    yield db_path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_pricing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing'`

- [ ] **Step 3: Create `pricing.py`**

```python
"""Расчёт цены и форматирование — используется и ботом, и десктоп-приложением."""
import re
from datetime import date, datetime

import db


def money(value: float) -> str:
    cur = db.get_settings()["currency"]
    return f"{value:,.0f}".replace(",", " ") + f" {cur}"


def parse_number(text: str | None) -> float | None:
    if not text:
        return None
    text = text.strip().replace(",", ".").replace(" ", "")
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value >= 0 else None


def parse_hours(text: str | None) -> float | None:
    """Принимает «2.5», «2,5», «2:30», «2ч 30м», «150м»."""
    if not text:
        return None
    t = text.strip().lower()
    if m := re.fullmatch(r"(\d+):(\d{1,2})", t):
        return int(m[1]) + int(m[2]) / 60
    if m := re.fullmatch(r"(?:(\d+(?:[.,]\d+)?)\s*ч)?\s*(?:(\d+)\s*м(?:ин)?)?", t):
        if m[1] or m[2]:
            return float((m[1] or "0").replace(",", ".")) + int(m[2] or 0) / 60
    return parse_number(t)


def parse_date(text: str | None) -> str | None:
    """«25.09», «25.09.2026», «25/09/26», «сегодня», «завтра» → ISO-дата."""
    if not text:
        return None
    t = text.strip().lower()
    today = date.today()
    if t == "сегодня":
        return today.isoformat()
    if t == "завтра":
        return date.fromordinal(today.toordinal() + 1).isoformat()
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?", t)
    if not m:
        return None
    day, month = int(m[1]), int(m[2])
    year = int(m[3]) if m[3] else today.year
    if year < 100:
        year += 2000
    try:
        d = date(year, month, day)
    except ValueError:
        return None
    if not m[3] and d < today:
        d = d.replace(year=year + 1)
    return d.isoformat()


def fmt_date(iso: str | None) -> str:
    return datetime.fromisoformat(iso).strftime("%d.%m.%Y") if iso else "—"


def deadline_mark(order) -> str:
    if not order["deadline"] or order["status"] not in db.ACTIVE_STATUSES:
        return ""
    days = (date.fromisoformat(order["deadline"]) - date.today()).days
    if days < 0:
        return f"🔥 просрочен на {-days} дн."
    if days == 0:
        return "⚠️ сегодня"
    if days == 1:
        return "⏰ завтра"
    return f"через {days} дн."


def calc_price(material: str | None, weight_g: float, hours: float, qty: int, reverse: bool = False) -> dict:
    s = db.get_settings()
    per_kg = s["materials"].get(material or "", 0)
    material_cost = weight_g * qty * per_kg / 1000
    time_cost = hours * qty * s["hour_rate"]
    reverse_cost = s["reverse_price"] if reverse else 0
    cost = material_cost + time_cost
    price = cost + reverse_cost
    return {
        "material_cost": material_cost, "time_cost": time_cost,
        "reverse_cost": reverse_cost, "cost": cost, "price": price,
    }


def price_breakdown(material, weight_g, hours, qty, reverse: bool = False) -> str:
    s = db.get_settings()
    p = calc_price(material, weight_g, hours, qty, reverse)
    lines = [
        f"Материал: {weight_g:g} г × {qty} × {s['materials'].get(material, 0)}/кг = {money(p['material_cost'])}",
        f"Время: {hours:g} ч × {qty} × {s['hour_rate']}/ч = {money(p['time_cost'])}",
    ]
    if reverse:
        lines.append(f"Реверс-моделирование: {money(p['reverse_cost'])}")
    lines.append(f"Итоговая цена: <b>{money(p['price'])}</b>")
    return "\n".join(lines)


def recalc_order_price(oid: int) -> None:
    o = db.get_order(oid)
    p = calc_price(o["material"], o["weight_g"], o["print_hours"], o["qty"], bool(o["reverse_engineering"]))
    db.update_order(oid, cost=round(p["cost"], 2), price=p["price"])
```

- [ ] **Step 4: Update `bot.py` to use `pricing.py`**

In `bot.py`, find this exact block (currently lines 100-206, right after the `MAIN_KB`/`SKIP_KB`/`CANCEL_KB` definitions and the `OwnerOnly` middleware, before `def order_card(o) -> str:`):

```python
# ---------- утилиты ----------

def money(value: float) -> str:
    cur = db.get_settings()["currency"]
    return f"{value:,.0f}".replace(",", " ") + f" {cur}"


def parse_number(text: str | None) -> float | None:
    if not text:
        return None
    text = text.strip().replace(",", ".").replace(" ", "")
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value >= 0 else None


def parse_hours(text: str | None) -> float | None:
    """Принимает «2.5», «2,5», «2:30», «2ч 30м», «150м»."""
    if not text:
        return None
    t = text.strip().lower()
    if m := re.fullmatch(r"(\d+):(\d{1,2})", t):
        return int(m[1]) + int(m[2]) / 60
    if m := re.fullmatch(r"(?:(\d+(?:[.,]\d+)?)\s*ч)?\s*(?:(\d+)\s*м(?:ин)?)?", t):
        if m[1] or m[2]:
            return float((m[1] or "0").replace(",", ".")) + int(m[2] or 0) / 60
    return parse_number(t)


def parse_date(text: str | None) -> str | None:
    """«25.09», «25.09.2026», «25/09/26», «сегодня», «завтра» → ISO-дата."""
    if not text:
        return None
    t = text.strip().lower()
    today = date.today()
    if t == "сегодня":
        return today.isoformat()
    if t == "завтра":
        return date.fromordinal(today.toordinal() + 1).isoformat()
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?", t)
    if not m:
        return None
    day, month = int(m[1]), int(m[2])
    year = int(m[3]) if m[3] else today.year
    if year < 100:
        year += 2000
    try:
        d = date(year, month, day)
    except ValueError:
        return None
    if not m[3] and d < today:  # без года и дата прошла — значит следующий год
        d = d.replace(year=year + 1)
    return d.isoformat()


def fmt_date(iso: str | None) -> str:
    return datetime.fromisoformat(iso).strftime("%d.%m.%Y") if iso else "—"


def deadline_mark(order) -> str:
    if not order["deadline"] or order["status"] not in db.ACTIVE_STATUSES:
        return ""
    days = (date.fromisoformat(order["deadline"]) - date.today()).days
    if days < 0:
        return f"🔥 просрочен на {-days} дн."
    if days == 0:
        return "⚠️ сегодня"
    if days == 1:
        return "⏰ завтра"
    return f"через {days} дн."


def calc_price(material: str | None, weight_g: float, hours: float, qty: int, reverse: bool = False) -> dict:
    s = db.get_settings()
    per_kg = s["materials"].get(material or "", 0)
    material_cost = weight_g * qty * per_kg / 1000
    time_cost = hours * qty * s["hour_rate"]
    reverse_cost = s["reverse_price"] if reverse else 0
    cost = material_cost + time_cost
    price = cost + reverse_cost
    return {
        "material_cost": material_cost, "time_cost": time_cost,
        "reverse_cost": reverse_cost, "cost": cost, "price": price,
    }


def price_breakdown(material, weight_g, hours, qty, reverse: bool = False) -> str:
    s = db.get_settings()
    p = calc_price(material, weight_g, hours, qty, reverse)
    lines = [
        f"Материал: {weight_g:g} г × {qty} × {s['materials'].get(material, 0)}/кг = {money(p['material_cost'])}",
        f"Время: {hours:g} ч × {qty} × {s['hour_rate']}/ч = {money(p['time_cost'])}",
    ]
    if reverse:
        lines.append(f"Реверс-моделирование: {money(p['reverse_cost'])}")
    lines.append(f"Итоговая цена: <b>{money(p['price'])}</b>")
    return "\n".join(lines)


def recalc_order_price(oid: int) -> None:
    o = db.get_order(oid)
    p = calc_price(o["material"], o["weight_g"], o["print_hours"], o["qty"], bool(o["reverse_engineering"]))
    db.update_order(oid, cost=round(p["cost"], 2), price=p["price"])
```

Replace it with:

```python
# ---------- утилиты ----------
```

Then find `import db` near the top of `bot.py` and change it to:

```python
import db
from pricing import (
    calc_price,
    deadline_mark,
    fmt_date,
    money,
    parse_date,
    parse_hours,
    parse_number,
    price_breakdown,
    recalc_order_price,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_pricing.py -v`
Expected: PASS (all tests)

Also sanity-check `bot.py` still imports cleanly:
Run: `.venv\Scripts\python.exe -c "import bot"`
Expected: no errors printed.

- [ ] **Step 6: Commit**

```bash
git add pricing.py bot.py tests/conftest.py tests/test_pricing.py
git commit -m "refactor: extract pricing helpers into pricing.py for reuse by desktop app"
```

---

### Task 2: WAL mode + baseline regression tests for `db.py`

**Files:**
- Modify: `db.py:44-78` (the `init()` function), `.gitignore`
- Test: `tests/test_db_baseline.py`

**Interfaces:**
- Consumes: `tests/conftest.py::temp_db` fixture from Task 1.
- Produces: nothing new — this task only turns on WAL and adds a regression safety net before schema changes begin in Tasks 3-4.

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_baseline.py`:

```python
"""Регрессионные тесты текущего поведения db.py, до добавления customers/attachments."""
import db


def test_wal_mode_is_enabled(temp_db):
    with db._conn() as c:
        mode = c.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_add_and_get_order_roundtrip(temp_db):
    order_id = db.add_order({
        "client": "Иван", "contact": "@ivan", "material": "PLA",
        "weight_g": 50, "print_hours": 1.5, "qty": 2, "cost": 100, "price": 150,
    })
    order = db.get_order(order_id)
    assert order["client"] == "Иван"
    assert order["status"] == "new"
    assert order["paid"] == 0


def test_update_order_changes_fields(temp_db):
    order_id = db.add_order({"client": "Иван", "contact": "", "cost": 0, "price": 0})
    db.update_order(order_id, status="printing", paid=1)
    order = db.get_order(order_id)
    assert order["status"] == "printing"
    assert order["paid"] == 1


def test_list_orders_active_excludes_delivered(temp_db):
    active_id = db.add_order({"client": "A", "contact": "", "cost": 0, "price": 0})
    done_id = db.add_order({"client": "B", "contact": "", "cost": 0, "price": 0})
    db.update_order(done_id, status="delivered")
    active_ids = {o["id"] for o in db.list_orders("active")}
    assert active_id in active_ids
    assert done_id not in active_ids


def test_settings_roundtrip(temp_db):
    db.set_setting("hour_rate", 75)
    assert db.get_settings()["hour_rate"] == 75
```

- [ ] **Step 2: Run test to verify WAL test fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_baseline.py -v`
Expected: `test_wal_mode_is_enabled` FAILS (journal mode is `delete`, not `wal`); the other tests already PASS since they cover existing behavior.

- [ ] **Step 3: Enable WAL mode in `db.py`**

In `db.py`, find:

```python
def init() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS orders (
```

Replace with:

```python
def init() -> None:
    with _conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute(
            """CREATE TABLE IF NOT EXISTS orders (
```

- [ ] **Step 4: Add ignores for upcoming app directories**

In `.gitignore`, add these lines:

```
app/files_cache/
app/files_storage/
.pytest_cache/
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS (all tests from Task 1 and Task 2)

- [ ] **Step 6: Commit**

```bash
git add db.py .gitignore tests/test_db_baseline.py
git commit -m "feat: enable SQLite WAL mode for concurrent bot+app access"
```

---

### Task 3: `customers` table, migration, and query functions

**Files:**
- Modify: `db.py` (schema in `init()`, new migration function, new public functions, `add_order`)
- Test: `tests/test_db_customers.py`

**Interfaces:**
- Consumes: `tests/conftest.py::temp_db`.
- Produces: `db.find_or_create_customer(name: str, contact: str | None) -> int`, `db.get_customer(customer_id: int) -> sqlite3.Row | None`, `db.list_customers(search: str = "") -> list[sqlite3.Row]` (rows include `orders_count`, `paid_total`, `debt_total`), `db.update_customer(customer_id: int, **fields) -> None`. `db.add_order(data)` now also returns an order whose `customer_id` is auto-populated. Relied on by Task 9 (order detail, customer reassignment) and Task 11 (customers screen).

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_customers.py`:

```python
"""Тесты для таблицы customers и автопривязки заказов к клиентам."""
import db


def test_find_or_create_customer_creates_new(temp_db):
    cid = db.find_or_create_customer("Иван Петров", "+79990000000")
    customer = db.get_customer(cid)
    assert customer["name"] == "Иван Петров"
    assert customer["contact"] == "+79990000000"


def test_find_or_create_customer_reuses_existing_case_insensitive(temp_db):
    cid1 = db.find_or_create_customer("Иван Петров", "+79990000000")
    cid2 = db.find_or_create_customer(" иван петров ", " +79990000000 ")
    assert cid1 == cid2


def test_add_order_links_customer_automatically(temp_db):
    order_id = db.add_order({
        "client": "Мария Сидорова", "contact": "@maria", "material": "PLA",
        "weight_g": 100, "print_hours": 2, "qty": 1, "cost": 500, "price": 600,
    })
    order = db.get_order(order_id)
    assert order["customer_id"] is not None
    customer = db.get_customer(order["customer_id"])
    assert customer["name"] == "Мария Сидорова"


def test_second_order_same_client_reuses_customer(temp_db):
    first = db.add_order({"client": "Пётр", "contact": "111", "cost": 0, "price": 0})
    second = db.add_order({"client": "Пётр", "contact": "111", "cost": 0, "price": 0})
    o1, o2 = db.get_order(first), db.get_order(second)
    assert o1["customer_id"] == o2["customer_id"]


def test_list_customers_aggregates_orders(temp_db):
    order_id = db.add_order({"client": "Клиент", "contact": "c1", "cost": 100, "price": 200})
    db.update_order(order_id, paid=1)
    rows = db.list_customers()
    assert len(rows) == 1
    assert rows[0]["orders_count"] == 1
    assert rows[0]["paid_total"] == 200
    assert rows[0]["debt_total"] == 0


def test_list_customers_search_filters_by_name(temp_db):
    db.add_order({"client": "Анна", "contact": "a", "cost": 0, "price": 0})
    db.add_order({"client": "Борис", "contact": "b", "cost": 0, "price": 0})
    rows = db.list_customers("анн")
    assert len(rows) == 1
    assert rows[0]["name"] == "Анна"


def test_update_customer_changes_notes(temp_db):
    cid = db.find_or_create_customer("Клиент", "c")
    db.update_customer(cid, notes="Постоянный клиент")
    assert db.get_customer(cid)["notes"] == "Постоянный клиент"


def test_migrate_customers_v1_groups_legacy_orders(temp_db):
    # Заказ, созданный «по-старому», без customer_id (имитирует БД до этой миграции).
    with db._conn() as c:
        c.execute(
            "INSERT INTO orders (created_at, client, contact, cost, price) VALUES (?, ?, ?, ?, ?)",
            ("2026-01-01T00:00:00", "Анна Легаси", "89990000000", 0, 0),
        )
        c.execute("DELETE FROM settings WHERE key = 'customers_v1'")
    db.init()  # повторный init должен смигрировать старый заказ
    rows = db.list_customers()
    assert any(r["name"] == "Анна Легаси" for r in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_customers.py -v`
Expected: FAIL with `AttributeError: module 'db' has no attribute 'find_or_create_customer'`

- [ ] **Step 3: Add the `customers` table and migration to `db.py`**

In `db.py`, find:

```python
        cols = {r["name"] for r in c.execute("PRAGMA table_info(orders)")}
        if "reverse_engineering" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN reverse_engineering INTEGER DEFAULT 0")
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        _migrate_pricing_v2(c)
```

Replace with:

```python
        cols = {r["name"] for r in c.execute("PRAGMA table_info(orders)")}
        if "reverse_engineering" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN reverse_engineering INTEGER DEFAULT 0")
        c.execute(
            """CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        if "customer_id" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER REFERENCES customers(id)")
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        _migrate_pricing_v2(c)
        _migrate_customers_v1(c)
```

Then, right after the existing `_migrate_pricing_v2` function, add:

```python
def _migrate_customers_v1(c) -> None:
    """Разовая группировка существующих заказов без customer_id в таблицу customers."""
    if c.execute("SELECT 1 FROM settings WHERE key = 'customers_v1'").fetchone():
        return
    groups: dict[tuple[str, str], list[int]] = {}
    for row in c.execute("SELECT id, client, contact FROM orders WHERE customer_id IS NULL"):
        key = ((row["client"] or "").strip().lower(), (row["contact"] or "").strip().lower())
        if not key[0]:
            continue
        groups.setdefault(key, []).append(row["id"])
    for order_ids in groups.values():
        first = c.execute(
            "SELECT client, contact FROM orders WHERE id = ?", (order_ids[0],)
        ).fetchone()
        cur = c.execute(
            "INSERT INTO customers (name, contact, notes, created_at) VALUES (?, ?, '', ?)",
            (first["client"], first["contact"], datetime.now().isoformat(timespec="seconds")),
        )
        customer_id = cur.lastrowid
        c.executemany(
            "UPDATE orders SET customer_id = ? WHERE id = ?",
            [(customer_id, oid) for oid in order_ids],
        )
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('customers_v1', 'true')")
```

- [ ] **Step 4: Add customer query functions and wire `add_order`**

In `db.py`, find the `# ---------- заказы ----------` section and the `add_order` function:

```python
# ---------- заказы ----------

def add_order(data: dict) -> int:
    fields = [
        "client", "contact", "description", "file_id", "file_type", "material", "color",
        "weight_g", "print_hours", "qty", "deadline", "cost", "price", "notes",
        "reverse_engineering",
    ]
    values = [data.get(f) for f in fields]
    with _conn() as c:
        cur = c.execute(
            f"INSERT INTO orders (created_at, {', '.join(fields)}) "
            f"VALUES (?, {', '.join('?' * len(fields))})",
            [datetime.now().isoformat(timespec="seconds"), *values],
        )
        return cur.lastrowid
```

Replace with:

```python
# ---------- клиенты ----------

def find_or_create_customer(name: str, contact: str | None) -> int:
    name = (name or "").strip()
    contact = (contact or "").strip()
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM customers WHERE lower(trim(name)) = ? "
            "AND lower(trim(COALESCE(contact, ''))) = ?",
            (name.lower(), contact.lower()),
        ).fetchone()
        if row:
            return row["id"]
        cur = c.execute(
            "INSERT INTO customers (name, contact, notes, created_at) VALUES (?, ?, '', ?)",
            (name, contact, datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def get_customer(customer_id: int):
    with _conn() as c:
        return c.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()


def list_customers(search: str = ""):
    like = f"%{search}%"
    with _conn() as c:
        return c.execute(
            """SELECT c.*,
                COUNT(o.id) AS orders_count,
                COALESCE(SUM(CASE WHEN o.paid = 1 THEN o.price END), 0) AS paid_total,
                COALESCE(SUM(CASE WHEN o.paid = 0 AND o.status != 'cancelled' THEN o.price END), 0) AS debt_total
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.id
            WHERE (? = '' OR c.name LIKE ? OR c.contact LIKE ?)
            GROUP BY c.id
            ORDER BY c.name COLLATE NOCASE""",
            (search, like, like),
        ).fetchall()


def update_customer(customer_id: int, **fields) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE customers SET {sets} WHERE id = ?", [*fields.values(), customer_id])


# ---------- заказы ----------

def add_order(data: dict) -> int:
    fields = [
        "client", "contact", "description", "file_id", "file_type", "material", "color",
        "weight_g", "print_hours", "qty", "deadline", "cost", "price", "notes",
        "reverse_engineering", "customer_id",
    ]
    data = dict(data)
    if not data.get("customer_id") and data.get("client"):
        data["customer_id"] = find_or_create_customer(data["client"], data.get("contact"))
    values = [data.get(f) for f in fields]
    with _conn() as c:
        cur = c.execute(
            f"INSERT INTO orders (created_at, {', '.join(fields)}) "
            f"VALUES (?, {', '.join('?' * len(fields))})",
            [datetime.now().isoformat(timespec="seconds"), *values],
        )
        return cur.lastrowid
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_customers.py -v`
Expected: PASS (all tests)

Run full suite to check nothing else broke:
Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add db.py tests/test_db_customers.py
git commit -m "feat: add customers table with automatic order linking"
```

---

### Task 4: `attachments` table, migration, query functions, and `change_fingerprint()`

**Files:**
- Modify: `db.py`
- Test: `tests/test_db_attachments.py`

**Interfaces:**
- Consumes: `tests/conftest.py::temp_db`.
- Produces: `db.add_attachment(order_id: int, source: str, *, file_id: str | None = None, local_path: str | None = None, filename: str | None = None, file_type: str | None = None) -> int`, `db.list_attachments(order_id: int) -> list[sqlite3.Row]`, `db.get_attachment(attachment_id: int) -> sqlite3.Row | None`, `db.delete_attachment(attachment_id: int) -> None`, `db.change_fingerprint() -> tuple`. `source` is `"telegram"` or `"local"`. Relied on by Task 6 (telegram_files), Task 7 (live_sync), Task 9 (order detail attachments UI), Task 10 (new order attachments).

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_attachments.py`:

```python
"""Тесты для таблицы attachments и миграции старого поля orders.file_id."""
import db


def test_add_and_list_attachment_local(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    att_id = db.add_attachment(
        order_id, "local", local_path="app/files_storage/1/model.stl",
        filename="model.stl", file_type="document",
    )
    attachments = db.list_attachments(order_id)
    assert len(attachments) == 1
    assert attachments[0]["id"] == att_id
    assert attachments[0]["source"] == "local"
    assert attachments[0]["filename"] == "model.stl"


def test_add_and_list_attachment_telegram(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    db.add_attachment(order_id, "telegram", file_id="ABC123", file_type="photo")
    attachments = db.list_attachments(order_id)
    assert attachments[0]["source"] == "telegram"
    assert attachments[0]["file_id"] == "ABC123"


def test_delete_attachment_removes_it(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    att_id = db.add_attachment(order_id, "local", local_path="x", filename="x", file_type="document")
    db.delete_attachment(att_id)
    assert db.list_attachments(order_id) == []


def test_get_attachment_returns_row(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    att_id = db.add_attachment(order_id, "local", local_path="x", filename="x", file_type="document")
    assert db.get_attachment(att_id)["id"] == att_id


def test_migrate_attachments_v1_moves_legacy_file_id(temp_db):
    order_id = db.add_order({
        "client": "К", "contact": "", "cost": 0, "price": 0,
        "file_id": "LEGACY_FILE", "file_type": "photo",
    })
    with db._conn() as c:
        c.execute("DELETE FROM settings WHERE key = 'attachments_v1'")
    db.init()  # повторный init должен смигрировать file_id в attachments
    attachments = db.list_attachments(order_id)
    assert len(attachments) == 1
    assert attachments[0]["source"] == "telegram"
    assert attachments[0]["file_id"] == "LEGACY_FILE"


def test_change_fingerprint_changes_on_new_order(temp_db):
    before = db.change_fingerprint()
    db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    after = db.change_fingerprint()
    assert before != after


def test_change_fingerprint_changes_on_new_attachment(temp_db):
    order_id = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    before = db.change_fingerprint()
    db.add_attachment(order_id, "local", local_path="x", filename="x", file_type="document")
    after = db.change_fingerprint()
    assert before != after
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_attachments.py -v`
Expected: FAIL with `AttributeError: module 'db' has no attribute 'add_attachment'`

- [ ] **Step 3: Add the `attachments` table and migration to `db.py`**

In `db.py`, find:

```python
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        _migrate_pricing_v2(c)
        _migrate_customers_v1(c)
```

Replace with:

```python
        c.execute(
            """CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                source TEXT NOT NULL,
                file_id TEXT,
                local_path TEXT,
                filename TEXT,
                file_type TEXT,
                added_at TEXT NOT NULL
            )"""
        )
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        _migrate_pricing_v2(c)
        _migrate_customers_v1(c)
        _migrate_attachments_v1(c)
```

Then, right after `_migrate_customers_v1`, add:

```python
def _migrate_attachments_v1(c) -> None:
    """Разовый перенос старого orders.file_id в таблицу attachments."""
    if c.execute("SELECT 1 FROM settings WHERE key = 'attachments_v1'").fetchone():
        return
    now = datetime.now().isoformat(timespec="seconds")
    for row in c.execute(
        "SELECT id, file_id, file_type FROM orders WHERE file_id IS NOT NULL AND file_id != ''"
    ):
        c.execute(
            "INSERT INTO attachments (order_id, source, file_id, filename, file_type, added_at) "
            "VALUES (?, 'telegram', ?, NULL, ?, ?)",
            (row["id"], row["file_id"], row["file_type"], now),
        )
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('attachments_v1', 'true')")
```

- [ ] **Step 4: Add attachment functions and `change_fingerprint()`**

At the end of `db.py`, after the existing `stats()` function, add:

```python
# ---------- вложения ----------

def add_attachment(order_id: int, source: str, *, file_id: str | None = None,
                    local_path: str | None = None, filename: str | None = None,
                    file_type: str | None = None) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO attachments (order_id, source, file_id, local_path, filename, file_type, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (order_id, source, file_id, local_path, filename, file_type,
             datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def list_attachments(order_id: int):
    with _conn() as c:
        return c.execute(
            "SELECT * FROM attachments WHERE order_id = ? ORDER BY id", (order_id,)
        ).fetchall()


def get_attachment(attachment_id: int):
    with _conn() as c:
        return c.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()


def delete_attachment(attachment_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))


# ---------- отпечаток состояния (для live-обновления) ----------

def change_fingerprint() -> tuple:
    """Лёгкий отпечаток состояния БД: меняется при любом изменении заказов/клиентов/вложений."""
    with _conn() as c:
        row = c.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM orders) AS orders_count, "
            "(SELECT COALESCE(MAX(id), 0) FROM orders) AS max_order_id, "
            "(SELECT COUNT(*) FROM customers) AS customers_count, "
            "(SELECT COUNT(*) FROM attachments) AS attachments_count"
        ).fetchone()
    return (row["orders_count"], row["max_order_id"], row["customers_count"], row["attachments_count"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_attachments.py -v`
Expected: PASS (all tests)

Run full suite:
Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add db.py tests/test_db_attachments.py
git commit -m "feat: add attachments table, legacy file_id migration, change fingerprint"
```

---

### Task 5: Dependencies + app package scaffold

**Files:**
- Modify: `requirements.txt`
- Create: `app/__init__.py`, `app/main.py`
- Test: `tests/test_app_scaffold.py`

**Interfaces:**
- Produces: `app.main.main(page: ft.Page) -> None` — the Flet entry point. Later tasks extend this function's body to add the navigation shell (Task 14), but the module and function must exist now so every subsequent `app/` task can be imported and tested.

- [ ] **Step 1: Write the failing test**

Create `tests/test_app_scaffold.py`:

```python
"""Проверяет, что пакет app/ собирается и импортируется корректно."""
import importlib


def test_app_main_module_imports_and_has_entrypoint():
    module = importlib.import_module("app.main")
    assert callable(module.main)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_app_scaffold.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Update `requirements.txt`**

Replace the full contents of `requirements.txt` with:

```
aiogram>=3.13,<4
python-dotenv>=1.0
flet>=0.24,<0.28
httpx>=0.27,<1
pytest>=8.0,<9
```

Install the new dependencies:
Run: `.venv\Scripts\python.exe -m pip install -r requirements.txt`

- [ ] **Step 4: Create the app package**

Create `app/__init__.py` (empty file).

Create `app/main.py`:

```python
"""Точка входа Mochi Desktop — админ-панели, использующей общую с ботом orders.db."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import flet as ft
from dotenv import load_dotenv

import db

load_dotenv(ROOT / ".env")


def main(page: ft.Page) -> None:
    page.title = "Mochi Desktop"
    page.window.width = 1100
    page.window.height = 750
    db.init()
    page.add(
        ft.Text("Mochi Desktop", size=24, weight=ft.FontWeight.BOLD),
        ft.Text("Приложение запущено, база данных готова."),
    )


if __name__ == "__main__":
    ft.app(target=main)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_app_scaffold.py -v`
Expected: PASS

- [ ] **Step 6: Manually verify the window opens**

Run: `.venv\Scripts\python.exe app\main.py`
Expected: a native window titled "Mochi Desktop" opens showing the two placeholder lines of text, and `orders.db` exists in the project root afterward. Close the window when done.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt app/__init__.py app/main.py tests/test_app_scaffold.py
git commit -m "feat: scaffold Flet desktop app entry point"
```

---

### Task 6: `telegram_files.py` — download/cache Telegram attachments

**Files:**
- Create: `app/telegram_files.py`
- Test: `tests/test_telegram_files.py`

**Interfaces:**
- Produces: `app.telegram_files.TelegramFileError(RuntimeError)`, `app.telegram_files.download_file(file_id: str, *, cache_dir: Path = CACHE_DIR) -> Path` — returns local path to the downloaded (or already-cached) file. Relied on by Task 9 (order detail "download Telegram attachment" button).

- [ ] **Step 1: Write the failing test**

Create `tests/test_telegram_files.py`:

```python
"""Тесты для скачивания файлов из Telegram Bot API (сеть замокана)."""
import httpx
import pytest

from app import telegram_files as tf


class _FakeResponse:
    def __init__(self, json_data=None, content=b""):
        self._json = json_data
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None):
        if "getFile" in url:
            return _FakeResponse(json_data={"ok": True, "result": {"file_path": "documents/model.stl"}})
        return _FakeResponse(content=b"STL-DATA")


def test_download_file_saves_and_returns_path(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "fake-token")
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    dest = tf.download_file("FILEID123", cache_dir=tmp_path)

    assert dest.exists()
    assert dest.read_bytes() == b"STL-DATA"


def test_download_file_uses_cache_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "fake-token")
    cached = tmp_path / "FILEID123_model.stl"
    cached.write_bytes(b"cached")

    def _boom(*a, **k):
        raise AssertionError("не должен обращаться к сети, если файл уже в кэше")

    monkeypatch.setattr(httpx, "Client", _boom)

    dest = tf.download_file("FILEID123", cache_dir=tmp_path)
    assert dest.read_bytes() == b"cached"


def test_download_file_without_token_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    with pytest.raises(tf.TelegramFileError):
        tf.download_file("FILEID123", cache_dir=tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_telegram_files.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.telegram_files'`

- [ ] **Step 3: Implement `app/telegram_files.py`**

```python
"""Скачивание файлов из Telegram Bot API по file_id, с кэшем на диск."""
import os
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).resolve().parent / "files_cache"


class TelegramFileError(RuntimeError):
    pass


def _bot_token() -> str:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise TelegramFileError("BOT_TOKEN не задан в .env")
    return token


def _find_cached(file_id: str, cache_dir: Path) -> Path | None:
    matches = list(cache_dir.glob(f"{file_id}_*"))
    return matches[0] if matches else None


def download_file(file_id: str, *, cache_dir: Path = CACHE_DIR) -> Path:
    """Скачивает файл по file_id (или возвращает уже скачанную копию из кэша)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = _find_cached(file_id, cache_dir)
    if cached:
        return cached

    token = _bot_token()
    with httpx.Client(timeout=30) as client:
        info = client.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id})
        info.raise_for_status()
        payload = info.json()
        if not payload.get("ok"):
            raise TelegramFileError(f"Telegram API вернул ошибку: {payload}")
        file_path = payload["result"]["file_path"]

        dest = cache_dir / f"{file_id}_{Path(file_path).name}"
        download = client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
        download.raise_for_status()
        dest.write_bytes(download.content)
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_telegram_files.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add app/telegram_files.py tests/test_telegram_files.py
git commit -m "feat: download and cache Telegram file_id attachments"
```

---

### Task 7: `live_sync.py` — background polling for live updates

**Files:**
- Create: `app/live_sync.py`
- Test: `tests/test_live_sync.py`

**Interfaces:**
- Consumes: `db.change_fingerprint()` from Task 4.
- Produces: `app.live_sync.LiveSync(on_change: Callable[[], None], interval: float = 3.0)` with `.start()` and `.stop()` methods — calls `on_change()` from a background thread whenever `db.change_fingerprint()` differs from the last observed value. Relied on by Task 14 (main shell wiring).

- [ ] **Step 1: Write the failing test**

Create `tests/test_live_sync.py`:

```python
"""Тесты для фонового опроса БД (LiveSync)."""
import time

import db
from app.live_sync import LiveSync


def test_live_sync_calls_on_change_when_db_changes(temp_db):
    events = []
    sync = LiveSync(on_change=lambda: events.append(1), interval=0.05)
    sync.start()
    try:
        time.sleep(0.12)
        assert events == [], "не должно быть событий без изменений в БД"

        db.add_order({"client": "Тест", "contact": "", "cost": 0, "price": 0})
        time.sleep(0.2)
        assert events, "LiveSync должен был заметить новый заказ"
    finally:
        sync.stop()


def test_live_sync_stop_prevents_further_calls(temp_db):
    events = []
    sync = LiveSync(on_change=lambda: events.append(1), interval=0.05)
    sync.start()
    sync.stop()
    count_after_stop = len(events)
    db.add_order({"client": "Тест2", "contact": "", "cost": 0, "price": 0})
    time.sleep(0.15)
    assert len(events) == count_after_stop
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_live_sync.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.live_sync'`

- [ ] **Step 3: Implement `app/live_sync.py`**

```python
"""Фоновый опрос БД, чтобы экраны обновлялись без ручного refresh."""
import threading
from typing import Callable

import db


class LiveSync:
    """Раз в interval секунд сравнивает db.change_fingerprint() и вызывает on_change() при изменении."""

    def __init__(self, on_change: Callable[[], None], interval: float = 3.0):
        self._on_change = on_change
        self._interval = interval
        self._last = db.change_fingerprint()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            current = db.change_fingerprint()
            if current != self._last:
                self._last = current
                self._on_change()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_live_sync.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add app/live_sync.py tests/test_live_sync.py
git commit -m "feat: add LiveSync background polling for cross-process DB updates"
```

---

### Task 8: Orders list screen

**Files:**
- Create: `app/screens/__init__.py`, `app/screens/orders_screen.py`

**Interfaces:**
- Consumes: `db.list_orders(kind: str, limit: int) -> list[Row]`, `db.search_orders(text, limit) -> list[Row]`, `db.STATUSES`, `pricing.money`, `pricing.deadline_mark`.
- Produces: `app.screens.orders_screen.OrdersScreen(on_open_order: Callable[[int], None])` — a `ft.Column` with a `.refresh()` method that re-reads the DB and re-renders the list. Relied on by Task 14 (main shell).

- [ ] **Step 1: Implement `app/screens/orders_screen.py`**

There is no meaningful way to unit-test Flet control trees without a running Flet test harness, so this task is verified manually (Step 2) instead of with pytest — consistent with the rest of the UI tasks in this plan.

Create `app/screens/__init__.py` (empty file).

Create `app/screens/orders_screen.py`:

```python
"""Экран «Заказы»: список с фильтрами и поиском, переход в карточку заказа."""
from typing import Callable

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

    def _on_filter_change(self, e: ft.ControlEvent) -> None:
        self.kind = FILTERS[self.tabs.selected_index][0]
        self.refresh()

    def _on_search_change(self, e: ft.ControlEvent) -> None:
        self.search_text = self.search_field.value or ""
        self.refresh()

    def refresh(self) -> None:
        self._render()
        if self.page:
            self.update()

    def _render(self) -> None:
        text = self.search_text.strip()
        orders = db.search_orders(text) if text else db.list_orders(self.kind)
        self.list_view.controls = [self._order_tile(o) for o in orders] or [
            ft.Text("Заказов нет.", italic=True)
        ]

    def _order_tile(self, o) -> ft.Control:
        mark = pricing.deadline_mark(o)
        subtitle = f"{db.STATUSES.get(o['status'], o['status'])} · {pricing.money(o['price'])}"
        if not o["paid"]:
            subtitle += " · не оплачен"
        if mark:
            subtitle += f" · {mark}"
        return ft.ListTile(
            title=ft.Text(f"#{o['id']} {o['client']}"),
            subtitle=ft.Text(subtitle),
            on_click=lambda e, oid=o["id"]: self.on_open_order(oid),
        )
```

- [ ] **Step 2: Manually verify**

Add a temporary smoke run: create `scratch_orders_screen.py` in the repo root (not committed) with:

```python
import flet as ft

from app.screens.orders_screen import OrdersScreen
import db

db.init()
db.add_order({"client": "Проверка", "contact": "", "material": "PLA", "weight_g": 50,
              "print_hours": 1, "qty": 1, "cost": 100, "price": 150})


def main(page: ft.Page):
    page.add(OrdersScreen(on_open_order=lambda oid: print("open", oid)))


ft.app(target=main)
```

Run: `.venv\Scripts\python.exe scratch_orders_screen.py`
Expected: a window opens with tabs (Активные/Неоплаченные/Завершённые/Все), a search field, and a tile "#1 Проверка". Clicking the tile prints `open 1` to the console. Delete `scratch_orders_screen.py` and `orders.db` afterward if it was created fresh for this check.

- [ ] **Step 3: Commit**

```bash
git add app/screens/__init__.py app/screens/orders_screen.py
git commit -m "feat: add orders list screen with filters and search"
```

---

### Task 9: Order detail/edit screen with attachments

**Files:**
- Create: `app/screens/order_detail.py`

**Interfaces:**
- Consumes: `db.get_order`, `db.update_order`, `db.delete_order`, `db.list_customers`, `db.list_attachments`, `db.add_attachment`, `db.delete_attachment`, `db.get_attachment`, `db.STATUSES`, `pricing.calc_price`, `pricing.recalc_order_price`, `pricing.money`, `pricing.fmt_date`, `app.telegram_files.download_file`, `app.telegram_files.TelegramFileError`.
- Produces: `app.screens.order_detail.OrderDetailScreen(order_id: int, on_back: Callable[[], None])` — a `ft.Column` with a `.refresh()` method (re-reads `order_id` from the DB; used by live sync while this screen is open). Relied on by Task 14.

- [ ] **Step 1: Implement `app/screens/order_detail.py`**

```python
"""Экран карточки заказа: просмотр/редактирование, статус, оплата, вложения."""
import shutil
from pathlib import Path
from typing import Callable

import flet as ft

import db
import pricing
from app.telegram_files import TelegramFileError, download_file

LOCAL_STORAGE = Path(__file__).resolve().parent.parent / "files_storage"


class OrderDetailScreen(ft.Column):
    def __init__(self, order_id: int, on_back: Callable[[], None]):
        super().__init__(expand=True, spacing=10)
        self.order_id = order_id
        self.on_back = on_back

        self.status_dd = ft.Dropdown(
            label="Статус",
            options=[ft.dropdown.Option(code, label) for code, label in db.STATUSES.items()],
            on_change=self._on_status_change,
        )
        self.paid_switch = ft.Switch(label="Оплачен", on_change=self._on_paid_change)
        self.client_field = ft.TextField(label="Клиент", on_blur=self._on_client_blur)
        self.contact_field = ft.TextField(label="Контакт", on_blur=self._on_client_blur)
        self.customer_dd = ft.Dropdown(label="Привязан к клиенту", on_change=self._on_customer_change)
        self.material_field = ft.TextField(label="Материал", on_blur=self._on_price_fields_blur)
        self.color_field = ft.TextField(label="Цвет", on_blur=self._on_other_field_blur, value="")
        self.weight_field = ft.TextField(label="Вес, г", on_blur=self._on_price_fields_blur)
        self.hours_field = ft.TextField(label="Часы печати", on_blur=self._on_price_fields_blur)
        self.qty_field = ft.TextField(label="Кол-во", on_blur=self._on_price_fields_blur)
        self.deadline_field = ft.TextField(label="Срок (ГГГГ-ММ-ДД)", on_blur=self._on_deadline_blur)
        self.price_field = ft.TextField(label="Цена (можно задать вручную)", on_blur=self._on_price_manual_blur)
        self.notes_field = ft.TextField(label="Заметки", multiline=True, on_blur=self._on_other_field_blur)
        self.price_text = ft.Text()
        self.attachments_column = ft.Column(spacing=4)

        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.status_banner = ft.Text("", color=ft.Colors.RED)

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

    def did_mount(self) -> None:
        self.page.overlay.append(self.file_picker)
        self.page.update()
        self.refresh()

    def refresh(self) -> None:
        order = db.get_order(self.order_id)
        if not order:
            self.on_back()
            return
        self.status_dd.value = order["status"]
        self.paid_switch.value = bool(order["paid"])
        self.client_field.value = order["client"] or ""
        self.contact_field.value = order["contact"] or ""
        self.material_field.value = order["material"] or ""
        self.color_field.value = order["color"] or ""
        self.weight_field.value = str(order["weight_g"] or 0)
        self.hours_field.value = str(order["print_hours"] or 0)
        self.qty_field.value = str(order["qty"] or 1)
        self.deadline_field.value = order["deadline"] or ""
        self.price_field.value = str(order["price"] or 0)
        self.notes_field.value = order["notes"] or ""
        self.price_text.value = (
            f"Себестоимость: {pricing.money(order['cost'])} · Цена: {pricing.money(order['price'])}"
        )

        customers = db.list_customers()
        self.customer_dd.options = [ft.dropdown.Option(str(c["id"]), c["name"]) for c in customers]
        self.customer_dd.value = str(order["customer_id"]) if order["customer_id"] else None

        self.attachments_column.controls = [self._attachment_row(a) for a in db.list_attachments(self.order_id)] or [
            ft.Text("Вложений нет.", italic=True)
        ]

        if self.page:
            self.update()

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

    def _open_path(self, path: str) -> None:
        import os
        os.startfile(path)  # noqa: S606 - открытие локального файла по клику пользователя

    def _download_attachment(self, attachment_id: int) -> None:
        attachment = db.get_attachment(attachment_id)
        try:
            path = download_file(attachment["file_id"])
        except TelegramFileError as exc:
            self.status_banner.value = str(exc)
            self.update()
            return
        self.status_banner.value = f"Скачано: {path}"
        self.update()

    def _delete_attachment(self, attachment_id: int) -> None:
        db.delete_attachment(attachment_id)
        self.refresh()

    def _on_add_file_click(self, e: ft.ControlEvent) -> None:
        self.file_picker.pick_files(allow_multiple=True)

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        dest_dir = LOCAL_STORAGE / str(self.order_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for f in e.files:
            dest = dest_dir / f.name
            shutil.copy(f.path, dest)
            db.add_attachment(
                self.order_id, "local", local_path=str(dest), filename=f.name,
                file_type="document",
            )
        self.refresh()

    def _on_status_change(self, e: ft.ControlEvent) -> None:
        db.update_order(self.order_id, status=self.status_dd.value)
        self.refresh()

    def _on_paid_change(self, e: ft.ControlEvent) -> None:
        db.update_order(self.order_id, paid=1 if self.paid_switch.value else 0)

    def _on_client_blur(self, e: ft.ControlEvent) -> None:
        db.update_order(self.order_id, client=self.client_field.value, contact=self.contact_field.value)
        self.refresh()

    def _on_customer_change(self, e: ft.ControlEvent) -> None:
        value = self.customer_dd.value
        db.update_order(self.order_id, customer_id=int(value) if value else None)

    def _on_other_field_blur(self, e: ft.ControlEvent) -> None:
        db.update_order(self.order_id, color=self.color_field.value, notes=self.notes_field.value)

    def _on_deadline_blur(self, e: ft.ControlEvent) -> None:
        parsed = pricing.parse_date(self.deadline_field.value) or self.deadline_field.value or None
        db.update_order(self.order_id, deadline=parsed)
        self.refresh()

    def _on_price_manual_blur(self, e: ft.ControlEvent) -> None:
        value = pricing.parse_number(self.price_field.value)
        if value is not None:
            db.update_order(self.order_id, price=value)
            self.refresh()

    def _on_price_fields_blur(self, e: ft.ControlEvent) -> None:
        weight = pricing.parse_number(self.weight_field.value) or 0
        hours = pricing.parse_number(self.hours_field.value) or 0
        qty = int(pricing.parse_number(self.qty_field.value) or 1)
        db.update_order(
            self.order_id, material=self.material_field.value, weight_g=weight,
            print_hours=hours, qty=qty,
        )
        pricing.recalc_order_price(self.order_id)
        self.refresh()

    def _on_delete_click(self, e: ft.ControlEvent) -> None:
        def confirm(e2: ft.ControlEvent) -> None:
            self.page.close(dialog)
            db.delete_order(self.order_id)
            self.on_back()

        def cancel(e2: ft.ControlEvent) -> None:
            self.page.close(dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Удалить заказ?"),
            content=ft.Text(f"Заказ #{self.order_id} будет удалён без возможности восстановить."),
            actions=[ft.TextButton("Отмена", on_click=cancel), ft.TextButton("Удалить", on_click=confirm)],
        )
        self.page.open(dialog)
```

- [ ] **Step 2: Manually verify**

Create a temporary `scratch_order_detail.py` in the repo root (not committed):

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
Expected: the card for order #1 loads with all fields populated; changing status/paid/material/weight updates immediately (price recalculates); clicking "Добавить файл" opens a native file picker and, after picking a file, it appears in the attachments list with a folder-open icon; clicking "Удалить заказ" shows a confirm dialog. Delete `scratch_order_detail.py` and `orders.db` afterward if created fresh for this check.

- [ ] **Step 3: Commit**

```bash
git add app/screens/order_detail.py
git commit -m "feat: add order detail screen with editing and attachments"
```

---

### Task 10: New order form

**Files:**
- Create: `app/screens/new_order.py`

**Interfaces:**
- Consumes: `db.add_order`, `db.add_attachment`, `db.get_settings`, `pricing.calc_price`, `pricing.money`, `pricing.parse_number`, `pricing.parse_date`.
- Produces: `app.screens.new_order.NewOrderScreen(on_created: Callable[[int], None])` — a `ft.Column`. Relied on by Task 14.

- [ ] **Step 1: Implement `app/screens/new_order.py`**

```python
"""Экран «Новый заказ»: форма создания без необходимости в Telegram."""
import shutil
from pathlib import Path
from typing import Callable

import flet as ft

import db
import pricing

LOCAL_STORAGE = Path(__file__).resolve().parent.parent / "files_storage"


class NewOrderScreen(ft.Column):
    def __init__(self, on_created: Callable[[int], None]):
        super().__init__(expand=True, spacing=10)
        self.on_created = on_created
        self._picked_files: list = []

        self.client_field = ft.TextField(label="Клиент *")
        self.contact_field = ft.TextField(label="Контакт")
        self.description_field = ft.TextField(label="Описание", multiline=True)
        self.material_dd = ft.Dropdown(label="Материал", on_change=self._recalc)
        self.color_field = ft.TextField(label="Цвет")
        self.weight_field = ft.TextField(label="Вес, г", value="0", on_change=self._recalc)
        self.hours_field = ft.TextField(label="Часы печати", value="0", on_change=self._recalc)
        self.qty_field = ft.TextField(label="Кол-во", value="1", on_change=self._recalc)
        self.deadline_field = ft.TextField(label="Срок (сегодня / завтра / 25.09)")
        self.reverse_checkbox = ft.Checkbox(label="Реверс-моделирование (нет STL)", on_change=self._recalc)
        self.price_preview = ft.Text()
        self.custom_price_field = ft.TextField(label="Своя цена (необязательно)")
        self.files_text = ft.Text("Файлы не выбраны.")
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.error_text = ft.Text("", color=ft.Colors.RED)

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

    def did_mount(self) -> None:
        self.page.overlay.append(self.file_picker)
        settings = db.get_settings()
        self.material_dd.options = [ft.dropdown.Option(m) for m in settings["materials"]]
        self.page.update()
        self._recalc(None)

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        self._picked_files = list(e.files or [])
        self.files_text.value = ", ".join(f.name for f in self._picked_files) or "Файлы не выбраны."
        self.update()

    def _recalc(self, e: ft.ControlEvent | None) -> None:
        weight = pricing.parse_number(self.weight_field.value) or 0
        hours = pricing.parse_number(self.hours_field.value) or 0
        qty = int(pricing.parse_number(self.qty_field.value) or 1)
        result = pricing.calc_price(
            self.material_dd.value, weight, hours, qty, bool(self.reverse_checkbox.value)
        )
        self.price_preview.value = f"Расчётная цена: {pricing.money(result['price'])}"
        if self.page:
            self.update()

    def _on_save(self, e: ft.ControlEvent) -> None:
        if not (self.client_field.value or "").strip():
            self.error_text.value = "Укажите клиента."
            self.update()
            return

        weight = pricing.parse_number(self.weight_field.value) or 0
        hours = pricing.parse_number(self.hours_field.value) or 0
        qty = int(pricing.parse_number(self.qty_field.value) or 1)
        reverse = bool(self.reverse_checkbox.value)
        calc = pricing.calc_price(self.material_dd.value, weight, hours, qty, reverse)
        custom_price = pricing.parse_number(self.custom_price_field.value)
        price = custom_price if custom_price is not None else calc["price"]

        order_id = db.add_order({
            "client": self.client_field.value.strip(),
            "contact": self.contact_field.value or "",
            "description": self.description_field.value or "",
            "material": self.material_dd.value,
            "color": self.color_field.value or "",
            "weight_g": weight,
            "print_hours": hours,
            "qty": qty,
            "deadline": pricing.parse_date(self.deadline_field.value),
            "cost": round(calc["cost"], 2),
            "price": price,
            "notes": "",
            "reverse_engineering": 1 if reverse else 0,
        })

        dest_dir = LOCAL_STORAGE / str(order_id)
        for f in self._picked_files:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f.name
            shutil.copy(f.path, dest)
            db.add_attachment(order_id, "local", local_path=str(dest), filename=f.name, file_type="document")

        self._reset_form()
        self.on_created(order_id)

    def _reset_form(self) -> None:
        self.client_field.value = ""
        self.contact_field.value = ""
        self.description_field.value = ""
        self.color_field.value = ""
        self.weight_field.value = "0"
        self.hours_field.value = "0"
        self.qty_field.value = "1"
        self.deadline_field.value = ""
        self.reverse_checkbox.value = False
        self.custom_price_field.value = ""
        self.error_text.value = ""
        self._picked_files = []
        self.files_text.value = "Файлы не выбраны."
        self._recalc(None)
```

- [ ] **Step 2: Manually verify**

Create a temporary `scratch_new_order.py` in the repo root (not committed):

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
Expected: form loads with PLA/PETG in the material dropdown; changing weight/hours/qty updates "Расчётная цена" live; filling client name and clicking "Создать заказ" prints `created 1` and the form clears. Verify via `db.get_order(1)` in a Python shell that a customer was auto-linked (`customer_id` is set). Delete `scratch_new_order.py` and `orders.db` afterward if created fresh for this check.

- [ ] **Step 3: Commit**

```bash
git add app/screens/new_order.py
git commit -m "feat: add new order form with live price preview and attachments"
```

---

### Task 11: Customers screen

**Files:**
- Create: `app/screens/customers_screen.py`

**Interfaces:**
- Consumes: `db.list_customers`, `db.update_customer`, `db.list_orders`, `pricing.money`.
- Produces: `app.screens.customers_screen.CustomersScreen()` — a `ft.Column` with a `.refresh()` method. Relied on by Task 14.

- [ ] **Step 1: Implement `app/screens/customers_screen.py`**

```python
"""Экран «Клиенты»: список с поиском и карточка клиента с историей заказов."""
import flet as ft

import db
import pricing


class CustomersScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=10)
        self.search_text = ""
        self.selected_customer_id: int | None = None

        self.search_field = ft.TextField(label="Поиск клиента", on_change=self._on_search)
        self.list_view = ft.ListView(expand=True, spacing=6)
        self.detail_column = ft.Column(visible=False, spacing=8)

        self.controls = [self.search_field, self.list_view, self.detail_column]
        self.refresh()

    def _on_search(self, e: ft.ControlEvent) -> None:
        self.search_text = self.search_field.value or ""
        self.refresh()

    def refresh(self) -> None:
        customers = db.list_customers(self.search_text.strip())
        self.list_view.controls = [self._customer_tile(c) for c in customers] or [
            ft.Text("Клиентов нет.", italic=True)
        ]
        if self.selected_customer_id is not None:
            self._render_detail(self.selected_customer_id)
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

    def _open_customer(self, customer_id: int) -> None:
        self.selected_customer_id = customer_id
        self._render_detail(customer_id)
        self.update()

    def _render_detail(self, customer_id: int) -> None:
        customer = db.get_customer(customer_id)
        if not customer:
            self.detail_column.visible = False
            self.selected_customer_id = None
            return
        notes_field = ft.TextField(
            label="Заметки", value=customer["notes"] or "", multiline=True,
            on_blur=lambda e, cid=customer_id: db.update_customer(cid, notes=notes_field.value),
        )
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

- [ ] **Step 2: Manually verify**

Create a temporary `scratch_customers.py` in the repo root (not committed):

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
Expected: "Иван Петров" appears in the list with "1 заказ(ов)"; clicking it shows contact, an editable notes field, and the order history with order #1. Delete `scratch_customers.py` and `orders.db` afterward if created fresh for this check.

- [ ] **Step 3: Commit**

```bash
git add app/screens/customers_screen.py
git commit -m "feat: add customers directory screen with order history"
```

---

### Task 12: Prices/settings screen

**Files:**
- Create: `app/screens/prices_screen.py`

**Interfaces:**
- Consumes: `db.get_settings`, `db.set_setting`, `pricing.parse_number`, `pricing.money`.
- Produces: `app.screens.prices_screen.PricesScreen()` — a `ft.Column` with a `.refresh()` method. Relied on by Task 14.

- [ ] **Step 1: Implement `app/screens/prices_screen.py`**

```python
"""Экран «Цены»: редактирование материалов, ставки часа, реверс-цены, валюты."""
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

    def refresh(self) -> None:
        settings = db.get_settings()
        self.materials_column.controls = [
            self._material_row(name, price) for name, price in settings["materials"].items()
        ] or [ft.Text("Материалов нет.", italic=True)]
        self.hour_rate_field.value = str(settings["hour_rate"])
        self.reverse_price_field.value = str(settings["reverse_price"])
        self.currency_field.value = settings["currency"]
        if self.page:
            self.update()

    def _material_row(self, name: str, price: float) -> ft.Control:
        price_field = ft.TextField(value=str(price), width=120)

        def save(e: ft.ControlEvent) -> None:
            value = pricing.parse_number(price_field.value)
            if value is None:
                return
            settings = db.get_settings()
            settings["materials"][name] = value
            db.set_setting("materials", settings["materials"])
            self.status_text.value = f"Сохранено: {name}"
            self.update()

        def delete(e: ft.ControlEvent) -> None:
            settings = db.get_settings()
            settings["materials"].pop(name, None)
            db.set_setting("materials", settings["materials"])
            self.refresh()

        price_field.on_blur = save
        return ft.Row([ft.Text(name, width=100), price_field, ft.IconButton(ft.Icons.DELETE, on_click=delete)])

    def _add_material(self, e: ft.ControlEvent) -> None:
        name = (self.new_material_name.value or "").strip()
        value = pricing.parse_number(self.new_material_price.value)
        if not name or value is None:
            self.status_text.value = "Укажите название материала и цену."
            self.update()
            return
        settings = db.get_settings()
        settings["materials"][name] = value
        db.set_setting("materials", settings["materials"])
        self.new_material_name.value = ""
        self.new_material_price.value = ""
        self.status_text.value = f"Добавлено: {name}"
        self.refresh()

    def _save_scalars(self, e: ft.ControlEvent) -> None:
        hour_rate = pricing.parse_number(self.hour_rate_field.value)
        reverse_price = pricing.parse_number(self.reverse_price_field.value)
        if hour_rate is not None:
            db.set_setting("hour_rate", hour_rate)
        if reverse_price is not None:
            db.set_setting("reverse_price", reverse_price)
        if self.currency_field.value:
            db.set_setting("currency", self.currency_field.value.strip())
        self.status_text.value = "Настройки сохранены."
        self.update()
```

- [ ] **Step 2: Manually verify**

Create a temporary `scratch_prices.py` in the repo root (not committed):

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
Expected: default materials (PLA/PETG/ABS) are listed with editable prices; adding "TPU"/"5000" appends a new row; editing the hour rate field and clicking elsewhere saves it (verify with `db.get_settings()["hour_rate"]` in a Python shell). Delete `scratch_prices.py` and `orders.db` afterward if created fresh for this check.

- [ ] **Step 3: Commit**

```bash
git add app/screens/prices_screen.py
git commit -m "feat: add prices/settings screen for materials and rates"
```

---

### Task 13: Stats dashboard screen

**Files:**
- Create: `app/screens/stats_screen.py`

**Interfaces:**
- Consumes: `db.stats() -> dict`, `db.STATUSES`, `pricing.money`.
- Produces: `app.screens.stats_screen.StatsScreen()` — a `ft.Column` with a `.refresh()` method. Relied on by Task 14.

- [ ] **Step 1: Implement `app/screens/stats_screen.py`**

```python
"""Экран «Статистика»: выручка, прибыль, долги, расход материала."""
import flet as ft

import db
import pricing


class StatsScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=10)
        self.content_column = ft.Column(spacing=6)
        self.controls = [ft.Text("Статистика", size=20, weight=ft.FontWeight.BOLD), self.content_column]
        self.refresh()

    def refresh(self) -> None:
        s = db.stats()
        total = sum(s["by_status"].values())
        status_lines = [
            ft.Text(f"{label}: {s['by_status'].get(code, 0)}")
            for code, label in db.STATUSES.items() if s["by_status"].get(code)
        ] or [ft.Text("Заказов пока нет.", italic=True)]
        material_lines = [
            ft.Text(f"• {name}: {grams / 1000:.2f} кг") for name, grams in s["materials"]
        ] or [ft.Text("—")]

        self.content_column.controls = [
            ft.Text(f"Всего заказов: {total}"),
            *status_lines,
            ft.Divider(),
            ft.Text(f"Этот месяц: {s['month_orders']} заказов, оплачено {pricing.money(s['month_revenue'])}"),
            ft.Divider(),
            ft.Text(f"💰 Выручка (оплачено): {pricing.money(s['revenue'])}", weight=ft.FontWeight.BOLD),
            ft.Text(f"📈 Прибыль: {pricing.money(s['profit'])}", weight=ft.FontWeight.BOLD),
            ft.Text(f"💸 Ждём оплату: {pricing.money(s['unpaid'])}", weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text(f"Расход материала (всего {s['grams'] / 1000:.2f} кг):", weight=ft.FontWeight.BOLD),
            *material_lines,
        ]
        if self.page:
            self.update()
```

- [ ] **Step 2: Manually verify**

Create a temporary `scratch_stats.py` in the repo root (not committed):

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
Expected: "Всего заказов: 1", revenue/profit reflect the paid order (500/100), and material usage shows "PLA: 0.10 кг". Delete `scratch_stats.py` and `orders.db` afterward if created fresh for this check.

- [ ] **Step 3: Commit**

```bash
git add app/screens/stats_screen.py
git commit -m "feat: add stats dashboard screen"
```

---

### Task 14: Navigation shell wiring all screens + live sync

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `OrdersScreen`, `OrderDetailScreen`, `NewOrderScreen`, `CustomersScreen`, `PricesScreen`, `StatsScreen` (all from Tasks 8-13), `LiveSync` (Task 7).
- Produces: the finished `app.main.main(page)` navigation shell — nothing further depends on this; it's the top of the tree.

- [ ] **Step 1: Update `app/main.py`**

Replace the full contents of `app/main.py` with:

```python
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
        orders_section._open_order(order_id)
        nav_rail.selected_index = 0
        page.update()

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
        stats_screen.refresh()

    page.pubsub.subscribe(lambda _: on_db_changed())
    live_sync = LiveSync(on_change=lambda: page.pubsub.send_all("db_changed"), interval=3.0)
    live_sync.start()
    page.on_disconnect = lambda e: live_sync.stop()

    page.add(ft.Row([nav_rail, ft.VerticalDivider(width=1), content], expand=True))


if __name__ == "__main__":
    ft.app(target=main)
```

- [ ] **Step 2: Run full automated test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS (all tests from every previous task)

- [ ] **Step 3: Manually verify the full app end-to-end**

Run: `.venv\Scripts\python.exe app\main.py`

Verify:
1. Window opens with a navigation rail (Заказы / Новый заказ / Клиенты / Цены / Статистика) and the orders list as the default view.
2. Click "Новый заказ", fill in a client and material, save — it should switch to "Заказы" and open the new order's detail card.
3. In the detail card, change status/paid/price — the change should persist (close and reopen the app to confirm it's saved).
4. Click "Клиенты" — the client from step 2 should appear with 1 order.
5. Click "Цены" — edit a material price, then go back to "Новый заказ" — the recalculated price preview should reflect the new rate.
6. Click "Статистика" — numbers should reflect the orders created so far.
7. **Live sync check:** with the app still open on the orders list, in a separate terminal run `.venv\Scripts\python.exe -c "import db; db.init(); db.add_order({'client': 'Из другого процесса', 'contact': '', 'cost': 0, 'price': 100})"` — within ~3 seconds the new order should appear in the app's list without any manual refresh.

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: wire navigation shell connecting all screens with live sync"
```

---

### Task 15: Packaging and documentation

**Files:**
- Create: `start_app.bat`
- Modify: `README.md`

**Interfaces:**
- None — this is the final packaging/documentation task, nothing depends on it.

- [ ] **Step 1: Create `start_app.bat`**

```bat
@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title Mochi Desktop

echo ============================================
echo    Запуск Mochi Desktop
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден на компьютере.
    echo Установите Python 3.10 или новее с https://www.python.org/downloads/
    echo При установке поставьте галочку "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Первый запуск: создаю окружение, подождите...
    python -m venv .venv
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение ".venv".
        pause
        exit /b 1
    )
)

echo Проверяю необходимые библиотеки...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить библиотеки. Проверьте интернет-соединение.
    pause
    exit /b 1
)

if not exist ".env" (
    echo Файл .env не найден — приложение всё равно запустится, но скачивание
    echo файлов из Telegram будет недоступно, пока не заполните BOT_TOKEN.
    echo Скопируйте .env.example в .env, если нужен доступ к файлам из Telegram.
    echo.
)

echo Запускаю Mochi Desktop...
".venv\Scripts\python.exe" app\main.py

echo.
echo ============================================
echo Приложение закрыто.
echo ============================================
pause
```

- [ ] **Step 2: Update `README.md`**

Find the line `Данные хранятся в \`orders.db\` (SQLite) — его стоит периодически копировать.` at the end of `README.md` and, after it, add:

```markdown

## Mochi Desktop (приложение для Windows)

Дважды кликнуть `start_app.bat` (при первом запуске сам создаст `.venv` и поставит
зависимости). Приложение — отдельный инструмент поверх той же `orders.db`: работает
независимо от Telegram (можно полностью создавать и вести заказы без бота), но если
бот тоже запущен — оба видят одни и те же данные и подхватывают изменения друг друга
в течение нескольких секунд.

Что умеет:
- **Заказы** — список с фильтрами и поиском, полное редактирование карточки заказа.
- **Новый заказ** — форма создания заказа с автоматическим расчётом цены и
  прикреплением файлов (фото, STL и т.д.) прямо с компьютера.
- **Клиенты** — справочник с историей заказов и суммами (оплачено/долг) по каждому.
- **Цены** — редактирование материалов, ставки часа, цены реверс-моделирования,
  валюты — без единой команды в Telegram.
- **Статистика** — тот же дашборд, что и `/stats` у бота, но в виде окна.

Вложения из Telegram (`file_id`) можно скачать прямо из карточки заказа — для этого
нужен `BOT_TOKEN` в `.env` (тот же файл, что использует бот).

Собрать отдельный `.exe`:

```bash
.venv\Scripts\flet pack app\main.py --name "Mochi Desktop"
```
```

- [ ] **Step 3: Manually verify**

Run: `start_app.bat` (double-click it, or run from a fresh terminal)
Expected: on first run it creates `.venv`, installs dependencies, and launches the app window. On subsequent runs it skips straight to launching.

- [ ] **Step 4: Commit**

```bash
git add start_app.bat README.md
git commit -m "docs: add start_app.bat and document Mochi Desktop in README"
```

---

## Self-Review Notes

- **Spec coverage:** architecture (shared WAL SQLite, Tasks 2-4) ✓; customers directory (Task 3, 11) ✓; prices/settings editing (Task 12) ✓; orders + new order + attachments, both Telegram and local (Tasks 6, 8-10) ✓; stats dashboard (Task 13) ✓; live updates (Tasks 4, 7, 14) ✓; standalone-from-Telegram requirement (Tasks 9-10 never require `BOT_TOKEN` except the explicit "download Telegram attachment" action) ✓; packaging (Task 15) ✓.
- **Placeholder scan:** no TBD/TODO markers; every step has runnable code or a concrete manual-verification script.
- **Type/signature consistency:** `OrdersScreen(on_open_order)`, `OrderDetailScreen(order_id, on_back)`, `NewOrderScreen(on_created)`, `CustomersScreen()`, `PricesScreen()`, `StatsScreen()`, `LiveSync(on_change, interval)` are defined once (Tasks 7-13) and used with matching signatures in Task 14's shell.
