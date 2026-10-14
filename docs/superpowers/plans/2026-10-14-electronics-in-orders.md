# Электроника в заказах — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** В заказ, кроме печати, можно добавить электронику — список компонентов (закупка × наценка), пайку и прошивку фиксированными суммами; это попадает в цену, себестоимость, прибыль, PDF, смету и выгрузку.

**Architecture:** Новые колонки в `orders` (`has_print`, `has_electronics`, `soldering_price`, `firmware_price`, `components_markup`) и таблица `order_components`. `pricing.calc_price()` получает необязательные аргументы электроники, `pricing.calc_order(order)` считает по строке из базы и становится единым входом для экранов, PDF и сметы. Общий виджет строк компонентов — `app/components_editor.py`.

**Tech Stack:** Python 3, Flet 0.27, SQLite, fpdf2, openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-10-14-electronics-in-orders-design.md`

## Global Constraints

- Весь код и тексты интерфейса — на русском, стиль и плотность комментариев как в соседнем коде.
- Электроника вносится на весь заказ: «Кол-во, шт» умножает только печать.
- Брак — только от печати.
- Себестоимость = пластик по закупке + компоненты по закупке; всё остальное в цене — прибыль.
- Старые заказы после миграции: `has_print = 1`, `has_electronics = 0`, цены и себестоимость не меняются.
- Наценка по умолчанию — настройка `components_markup` = 20 (%).
- Закупка и наценка никогда не попадают в PDF для клиента.
- Тесты: `.venv\Scripts\python.exe -m pytest -q` из `W\TGbot`; при проверке приложения из исходников не трогать настоящую Google Таблицу.
- Версия сборки — 1.10.0; перед заменой exe — копия `orders.backup-before-1.10.0.db`.

## Review Focus

- Пустая строка компонента (без названия) в форме — не сохраняется и не ломает расчёт (тест в задаче 3).
- Нечисловая цена/кол-во компонента («пятьсот») — ошибка у поля, в базу ничего не пишется (тесты в задачах 3 и 5).
- Выключенная печать с заполненным весом — вес не попадает ни в цену, ни в «граммы» статистики (тесты в задачах 1 и 2).
- Смена закупки пластика в «Ценах» (`recalc_costs`) не теряет закупку компонентов в себестоимости (тест в задаче 1).
- Смена номера и удаление заказа уносят его компоненты (тест в задаче 1).

---

### Task 1: База — колонки, таблица компонентов, себестоимость

**Files:**
- Modify: `db.py`
- Test: `tests/test_db_components.py` (создать)

**Interfaces:**
- Produces:
  - `db.DEFAULT_SETTINGS["components_markup"] == 20`
  - `db.set_components(order_id: int, components: list[dict]) -> None` — заменяет все компоненты заказа; dict: `name`, `qty`, `unit_cost`; строки с пустым `name` пропускаются.
  - `db.list_components(order_id: int) -> list[sqlite3.Row]` (поля `id, order_id, name, qty, unit_cost`, по `id`).
  - `db.components_by_order() -> dict[int, list[sqlite3.Row]]`.
  - `db.component_catalog() -> dict[str, float]` — название → закупка из самой поздней строки, по алфавиту.
  - `db.expense(material, weight_g, hours, qty, settings, components_purchase: float = 0, has_print: bool = True) -> dict` с ключами `plastic, components, time, total`.
  - `add_order` принимает `has_print, has_electronics, soldering_price, firmware_price, components_markup`.

- [ ] **Step 1: Write the failing tests** — `tests/test_db_components.py`:

```python
"""Электроника в заказе: компоненты, новые колонки, себестоимость с компонентами."""
import sqlite3

import db


def _order(**extra) -> int:
    return db.add_order({"client": "К", "contact": "", "cost": 0, "price": 1000, **extra})


def test_new_order_defaults_to_print_only(temp_db):
    o = db.get_order(_order())
    assert o["has_print"] == 1 and o["has_electronics"] == 0
    assert o["soldering_price"] == 0 and o["firmware_price"] == 0 and o["components_markup"] == 0


def test_components_markup_setting_default(temp_db):
    assert db.get_settings()["components_markup"] == 20


def test_set_components_replaces_and_skips_blank_names(temp_db):
    oid = _order(has_electronics=1)
    db.set_components(oid, [{"name": "ESP32", "qty": 2, "unit_cost": 450}, {"name": "  ", "qty": 1, "unit_cost": 9}])
    db.set_components(oid, [{"name": " Лента WS2812 ", "qty": 1.5, "unit_cost": 300}])
    rows = db.list_components(oid)
    assert [(r["name"], r["qty"], r["unit_cost"]) for r in rows] == [("Лента WS2812", 1.5, 300)]


def test_component_catalog_keeps_latest_price(temp_db):
    a, b = _order(), _order()
    db.set_components(a, [{"name": "ESP32", "qty": 1, "unit_cost": 450}, {"name": "Экран", "qty": 1, "unit_cost": 700}])
    db.set_components(b, [{"name": "ESP32", "qty": 1, "unit_cost": 500}])
    assert db.component_catalog() == {"ESP32": 500, "Экран": 700}


def test_components_by_order_groups_rows(temp_db):
    a = _order()
    db.set_components(a, [{"name": "ESP32", "qty": 1, "unit_cost": 450}, {"name": "Провод", "qty": 3, "unit_cost": 10}])
    grouped = db.components_by_order()
    assert [r["name"] for r in grouped[a]] == ["ESP32", "Провод"]


def test_expense_adds_components_and_skips_plastic_without_print(temp_db):
    s = {**db.get_settings(), "purchase_prices": {"PLA": 2}}
    assert db.expense("PLA", 100, 1, 1, s, components_purchase=900)["total"] == 1100
    off = db.expense("PLA", 100, 1, 1, s, components_purchase=900, has_print=False)
    assert off["plastic"] == 0 and off["total"] == 900


def test_recalc_costs_keeps_components(temp_db):
    db.set_setting("purchase_prices", {"PLA": 2})
    oid = _order(material="PLA", weight_g=100, qty=1, has_electronics=1)
    db.set_components(oid, [{"name": "ESP32", "qty": 2, "unit_cost": 450}])
    db.recalc_costs()
    assert db.get_order(oid)["cost"] == 200 + 900
    db.update_order(oid, has_electronics=0)
    db.recalc_costs()
    assert db.get_order(oid)["cost"] == 200


def test_renumber_and_delete_carry_components(temp_db, tmp_path):
    oid = _order()
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 450}])
    db.renumber_order(oid, 50, storage_dir=tmp_path)
    assert [r["name"] for r in db.list_components(50)] == ["ESP32"]
    db.delete_order(50)
    assert db.list_components(50) == []


def test_delete_customer_with_orders_removes_components(temp_db):
    oid = _order()
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 450}])
    db.delete_customer(db.get_order(oid)["customer_id"], delete_orders=True)
    assert db.list_components(oid) == []


def test_fingerprint_changes_on_components(temp_db):
    oid = _order()
    before = db.change_fingerprint()
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 450}])
    assert db.change_fingerprint() != before


def test_search_finds_order_by_component(temp_db):
    oid = _order()
    db.set_components(oid, [{"name": "ESP32-WROOM", "qty": 1, "unit_cost": 450}])
    assert [o["id"] for o in db.search_orders("WROOM")] == [oid]


def test_stats_grams_skip_orders_without_print(temp_db):
    _order(material="PLA", weight_g=100, qty=1)
    _order(material="PLA", weight_g=999, qty=1, has_print=0, has_electronics=1)
    s = db.stats()
    assert s["grams"] == 100 and s["materials"] == [("PLA", 100)]


def test_old_database_migrates_without_changing_prices(temp_db):
    """База старой версии: колонок электроники нет — init() добавляет их, цены и себестоимость те же."""
    oid = _order(material="PLA", weight_g=100, qty=1, cost=150, price=777)
    with sqlite3.connect(temp_db) as c:
        c.execute("DROP TABLE order_components")
        for col in ("has_print", "has_electronics", "soldering_price", "firmware_price", "components_markup"):
            c.execute(f"ALTER TABLE orders DROP COLUMN {col}")
    db.init()
    o = db.get_order(oid)
    assert (o["has_print"], o["has_electronics"], o["price"], o["cost"]) == (1, 0, 777, 150)
    assert db.list_components(oid) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_components.py -q`
Expected: FAIL — `no such column: has_print` / `AttributeError: module 'db' has no attribute 'set_components'`.

- [ ] **Step 3: Implement in `db.py`**

3a. `DEFAULT_SETTINGS` — после `"defect_percent"`:

```python
    "components_markup": 20,  # % наценки на компоненты электроники — подставляется в новые заказы
```

3b. В `init()` сразу после блока `if "prepayment" not in cols: ...` добавить колонки, а после создания `attachments` — таблицу (обе до `_recalc_costs`):

```python
        for col, ddl in (("has_print", "INTEGER DEFAULT 1"), ("has_electronics", "INTEGER DEFAULT 0"),
                         ("soldering_price", "REAL DEFAULT 0"), ("firmware_price", "REAL DEFAULT 0"),
                         ("components_markup", "REAL DEFAULT 0")):
            if col not in cols:
                # Старые заказы — только печать, без электроники: цены не меняются.
                c.execute(f"ALTER TABLE orders ADD COLUMN {col} {ddl}")
```

```python
        c.execute(
            """CREATE TABLE IF NOT EXISTS order_components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                name TEXT NOT NULL,
                qty REAL NOT NULL DEFAULT 1,
                unit_cost REAL NOT NULL DEFAULT 0
            )"""
        )
```

3c. `expense()`:

```python
def expense(material: str | None, weight_g: float, hours: float, qty: int, settings: dict,
            components_purchase: float = 0, has_print: bool = True) -> dict:
    """Себестоимость: пластик по закупочной цене + компоненты электроники по закупке. Всё остальное
    в цене — часы печати, наценки, брак, реверс-моделирование, пайка, прошивка, ручная цена — это прибыль."""
    purchase = settings.get("purchase_prices", {}).get(material or "", 0) or 0
    plastic = (weight_g or 0) * (qty or 1) * purchase if has_print else 0
    time = (hours or 0) * (qty or 1) * settings["hour_rate"] if has_print else 0
    components = components_purchase or 0
    return {"plastic": plastic, "components": components, "time": time, "total": plastic + components}
```

3d. `_recalc_costs()`:

```python
def _recalc_costs(c) -> None:
    settings = dict(DEFAULT_SETTINGS)
    settings.update({r["key"]: json.loads(r["value"]) for r in c.execute("SELECT key, value FROM settings")
                     if r["key"] in DEFAULT_SETTINGS})
    rows = c.execute(
        "SELECT o.id, o.material, o.weight_g, o.print_hours, o.qty, o.has_print, o.has_electronics, "
        "(SELECT COALESCE(SUM(qty * unit_cost), 0) FROM order_components oc WHERE oc.order_id = o.id) AS parts "
        "FROM orders o").fetchall()
    c.executemany("UPDATE orders SET cost = ? WHERE id = ?", [
        (round(expense(r["material"], r["weight_g"], r["print_hours"], r["qty"], settings,
                       r["parts"] if r["has_electronics"] else 0, bool(r["has_print"]))["total"], 2), r["id"])
        for r in rows
    ])
```

3e. `add_order()` — дополнить `fields` и умолчания:

```python
        "reverse_engineering", "customer_id", "defect_percent", "prepayment",
        "has_print", "has_electronics", "soldering_price", "firmware_price", "components_markup",
    ]
    ...
    data.setdefault("defect_percent", 0)
    data["prepayment"] = data.get("prepayment") or 0
    data["has_print"] = 1 if data.get("has_print", 1) else 0
    data["has_electronics"] = 1 if data.get("has_electronics") else 0
    for key in ("soldering_price", "firmware_price", "components_markup"):
        data[key] = data.get(key) or 0
```

3f. `renumber_order()` — в транзакции рядом с `spool_usage`:

```python
            c.execute("UPDATE order_components SET order_id = ? WHERE order_id = ?", (new_id, old_id))
```

3g. `delete_order()`:

```python
def delete_order(order_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM order_components WHERE order_id = ?", (order_id,))
        c.execute("DELETE FROM orders WHERE id = ?", (order_id,))
```

3h. `delete_customer()` — в ветке `delete_orders` перед удалением заказов:

```python
            c.execute(
                "DELETE FROM order_components WHERE order_id IN (SELECT id FROM orders WHERE customer_id = ?)",
                (customer_id,),
            )
```

3i. `search_orders()`:

```python
        return c.execute(
            "SELECT * FROM orders WHERE client LIKE ? OR contact LIKE ? OR description LIKE ? "
            "OR notes LIKE ? OR id IN (SELECT order_id FROM order_components WHERE name LIKE ?) "
            "ORDER BY id DESC LIMIT ?",
            (like, like, like, like, like, limit),
        ).fetchall()
```

3j. `stats()` — граммы только у заказов с печатью: в общем запросе
`THEN weight_g * qty` → `CASE WHEN status != 'cancelled' AND has_print = 1 THEN weight_g * qty END`, в `materials` добавить `AND has_print = 1` в `WHERE`.

3k. Новый раздел после «вложений»:

```python
# ---------- компоненты электроники ----------

def set_components(order_id: int, components: list[dict]) -> None:
    """Заменяет компоненты заказа целиком. Строки без названия пропускаются."""
    rows = [((comp.get("name") or "").strip(), comp.get("qty") or 0, comp.get("unit_cost") or 0)
            for comp in components]
    with _conn() as c:
        c.execute("DELETE FROM order_components WHERE order_id = ?", (order_id,))
        c.executemany("INSERT INTO order_components (order_id, name, qty, unit_cost) VALUES (?, ?, ?, ?)",
                      [(order_id, *r) for r in rows if r[0]])


def list_components(order_id: int) -> list[sqlite3.Row]:
    with _conn() as c:
        return c.execute("SELECT * FROM order_components WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()


def components_by_order() -> dict[int, list[sqlite3.Row]]:
    """{номер заказа: его компоненты} — для списка заказов и выгрузки одним запросом."""
    grouped: dict[int, list[sqlite3.Row]] = {}
    with _conn() as c:
        for r in c.execute("SELECT * FROM order_components ORDER BY order_id, id"):
            grouped.setdefault(r["order_id"], []).append(r)
    return grouped


def component_catalog() -> dict[str, float]:
    """{название: закупка за штуку} из прошлых заказов — последняя цена; для подсказок при вводе."""
    with _conn() as c:
        rows = c.execute("SELECT name, unit_cost FROM order_components ORDER BY id").fetchall()
    latest = {r["name"]: r["unit_cost"] for r in rows}
    return dict(sorted(latest.items(), key=lambda kv: kv[0].lower()))
```

3l. `change_fingerprint()` — добавить в SELECT

```python
            ", (SELECT COUNT(*) || ':' || COALESCE(MAX(id), 0) || ':' || COALESCE(SUM(qty * unit_cost), 0) "
            "FROM order_components) AS components_sig"
```

(вставить после `usage_sig` перед закрывающей кавычкой) и `row["components_sig"]` в конец возвращаемого кортежа.

- [ ] **Step 4: Run tests**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: всё зелёное (226 старых + 14 новых).

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db_components.py
git commit -m "feat: order components and electronics columns in the database"
```

---

### Task 2: Расчёт цены с электроникой

**Files:**
- Modify: `pricing.py`
- Test: `tests/test_pricing_electronics.py` (создать)

**Interfaces:**
- Consumes: `db.expense(..., components_purchase, has_print)`, `db.list_components`.
- Produces:
  - `pricing.calc_price(material, weight_g, hours, qty, reverse=False, defect_percent=0, *, has_print=True, has_electronics=False, components=(), markup=0, soldering=0, firmware=0) -> dict` — прежние ключи + `components_purchase, components_cost, soldering_cost, firmware_cost, has_print, has_electronics`.
  - `pricing.calc_order(order) -> dict` — то же по строке заказа (компоненты из базы).
  - `pricing.recalc_order_price(oid)` — через `calc_order`.

- [ ] **Step 1: Write the failing tests** — `tests/test_pricing_electronics.py`:

```python
"""Цена заказа с электроникой: компоненты с наценкой, пайка, прошивка; брак — только от печати."""
import db
import pricing


def _setup():
    db.set_setting("materials", {"PLA": 4})
    db.set_setting("purchase_prices", {"PLA": 2})
    db.set_setting("hour_rate", 50)


PARTS = [{"name": "ESP32", "qty": 2, "unit_cost": 450}, {"name": "Экран", "qty": 1, "unit_cost": 100}]


def test_old_calls_unchanged(temp_db):
    _setup()
    p = pricing.calc_price("PLA", 100, 2, 1)
    assert p["price"] == 500 and p["cost"] == 200 and p["components_cost"] == 0


def test_print_plus_electronics(temp_db):
    _setup()
    p = pricing.calc_price("PLA", 100, 2, 1, defect_percent=10, has_electronics=True, components=PARTS,
                           markup=20, soldering=500, firmware=1500)
    assert p["components_purchase"] == 1000
    assert p["components_cost"] == 1200
    assert p["defect_cost"] == 50  # 10% только от печати (400 + 100)
    assert p["price"] == 550 + 1200 + 500 + 1500
    assert p["cost"] == 200 + 1000
    assert p["profit"] == p["price"] - 1200


def test_qty_multiplies_only_print(temp_db):
    _setup()
    p = pricing.calc_price("PLA", 100, 0, 3, has_electronics=True, components=PARTS, soldering=500)
    assert p["material_cost"] == 1200 and p["components_purchase"] == 1000 and p["soldering_cost"] == 500


def test_disabled_parts_are_ignored(temp_db):
    _setup()
    only_el = pricing.calc_price("PLA", 100, 2, 1, has_print=False, has_electronics=True, components=PARTS)
    assert only_el["material_cost"] == 0 and only_el["time_cost"] == 0 and only_el["price"] == 1000
    assert only_el["cost"] == 1000
    only_print = pricing.calc_price("PLA", 100, 2, 1, components=PARTS, soldering=500)
    assert only_print["components_cost"] == 0 and only_print["soldering_cost"] == 0 and only_print["price"] == 500


def test_calc_order_reads_components_from_db(temp_db):
    _setup()
    oid = db.add_order({"client": "К", "contact": "", "material": "PLA", "weight_g": 100, "print_hours": 2,
                        "qty": 1, "cost": 0, "price": 0, "has_electronics": 1, "components_markup": 20,
                        "soldering_price": 500, "firmware_price": 1500})
    db.set_components(oid, PARTS)
    pricing.recalc_order_price(oid)
    o = db.get_order(oid)
    assert o["price"] == 500 + 1200 + 500 + 1500 and o["cost"] == 1200
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_pricing_electronics.py -q`
Expected: FAIL — `unexpected keyword argument 'has_electronics'`.

- [ ] **Step 3: Implement in `pricing.py`** — заменить `calc_price` и `recalc_order_price`, добавить `calc_order`:

```python
def calc_price(material: str | None, weight_g: float, hours: float, qty: int, reverse: bool = False,
               defect_percent: float = 0, *, has_print: bool = True, has_electronics: bool = False,
               components=(), markup: float = 0, soldering: float = 0, firmware: float = 0) -> dict:
    """Печать: брак — надбавка в % от стоимости печати (материал + время); на реверс не начисляется.
    Электроника (на весь заказ, «Кол-во» её не умножает): компоненты по закупке × (1 + наценка %),
    пайка и прошивка — суммами. Выключенная часть не считается, даже если поля заполнены.
    cost — себестоимость (пластик + компоненты по закупке), profit — всё, что сверх неё."""
    s = db.get_settings()
    per_gram = s["materials"].get(material or "", 0)  # ₽ за грамм
    material_cost = weight_g * qty * per_gram if has_print else 0
    time_cost = hours * qty * s["hour_rate"] if has_print else 0
    defect_cost = (material_cost + time_cost) * (defect_percent or 0) / 100
    reverse_cost = s["reverse_price"] if reverse and has_print else 0
    purchase = sum((c["qty"] or 0) * (c["unit_cost"] or 0) for c in components) if has_electronics else 0
    components_cost = purchase * (1 + (markup or 0) / 100)
    soldering_cost = (soldering or 0) if has_electronics else 0
    firmware_cost = (firmware or 0) if has_electronics else 0
    price = material_cost + time_cost + defect_cost + reverse_cost + components_cost + soldering_cost + firmware_cost
    exp = db.expense(material, weight_g, hours, qty, s, purchase, has_print)
    return {
        "material_cost": material_cost, "time_cost": time_cost, "defect_cost": defect_cost,
        "reverse_cost": reverse_cost, "components_purchase": purchase, "components_cost": components_cost,
        "soldering_cost": soldering_cost, "firmware_cost": firmware_cost, "price": price,
        "purchase_cost": exp["plastic"], "cost": exp["total"], "profit": price - exp["total"],
        "has_purchase_price": bool(s.get("purchase_prices", {}).get(material or "")),
        "has_print": has_print, "has_electronics": has_electronics,
    }


def calc_order(order) -> dict:
    """Расчёт по строке заказа из базы (компоненты — из order_components)."""
    return calc_price(
        order["material"], order["weight_g"] or 0, order["print_hours"] or 0, order["qty"] or 1,
        bool(order["reverse_engineering"]), order["defect_percent"] or 0,
        has_print=bool(order["has_print"]), has_electronics=bool(order["has_electronics"]),
        components=db.list_components(order["id"]), markup=order["components_markup"] or 0,
        soldering=order["soldering_price"] or 0, firmware=order["firmware_price"] or 0,
    )


def recalc_order_price(oid: int) -> None:
    p = calc_order(db.get_order(oid))
    db.update_order(oid, cost=round(p["cost"], 2), price=p["price"])
```

- [ ] **Step 4: Run tests** — `.venv\Scripts\python.exe -m pytest -q` → всё зелёное.

- [ ] **Step 5: Commit**

```bash
git add pricing.py tests/test_pricing_electronics.py
git commit -m "feat: price and cost with electronics components, soldering and firmware"
```

---

### Task 3: Виджет компонентов и строки «Итого»

**Files:**
- Create: `app/components_editor.py`
- Modify: `app/price_view.py`
- Test: `tests/test_components_editor.py` (создать), `tests/test_price_view.py` (дополнить)

**Interfaces:**
- Consumes: `db.component_catalog()`, `pricing.parse_number`, `pricing.fmt_number`, `pricing.money`, ключи `calc_price`.
- Produces:
  - `ComponentsEditor(on_change: Callable[[], None] | None = None, live: bool = True)` — `ft.Column`.
    - `set_components(rows: Iterable[Mapping]) -> None` (ключи `name, qty, unit_cost`; пустой список → ни одной строки).
    - `add_row(name="", qty=1, unit_cost=None) -> None`.
    - `get_components() -> list[dict] | None` — `None`, если в кол-ве/цене не число (ставит `error_text`); пустые названия пропускаются.
    - `preview() -> list[dict]` — то же без ошибок: нераспознанное считается 0 (для живого расчёта).
    - `live=True` — `on_change` по каждому вводу (новый заказ); `live=False` — по уходу из поля, удалению и выбору из подсказок (карточка).
  - `price_view.breakdown_rows` / `profit_rows` показывают строки электроники.

- [ ] **Step 1: Write the failing tests**

`tests/test_components_editor.py`:

```python
"""Строки компонентов электроники: ввод, проверка чисел, подсказки из прошлых заказов."""
import db
from app.components_editor import ComponentsEditor


def _editor(**kw):
    ed = ComponentsEditor(**kw)
    ed.update = lambda: None
    return ed


def test_get_components_parses_rows_and_skips_blank(temp_db):
    ed = _editor()
    ed.add_row("ESP32", 2, 450)
    ed.add_row()  # пустая строка — не компонент
    ed.rows[0].qty.value = "2"
    assert ed.get_components() == [{"name": "ESP32", "qty": 2, "unit_cost": 450}]


def test_invalid_numbers_mark_field_and_return_none(temp_db):
    ed = _editor()
    ed.add_row("ESP32", 1, 450)
    ed.rows[0].cost.value = "пятьсот"
    assert ed.get_components() is None
    assert ed.rows[0].cost.error_text
    assert ed.preview() == [{"name": "ESP32", "qty": 1, "unit_cost": 0}]


def test_blank_qty_means_one_and_blank_price_zero(temp_db):
    ed = _editor()
    ed.add_row("Провод")
    ed.rows[0].qty.value = ""
    assert ed.get_components() == [{"name": "Провод", "qty": 1, "unit_cost": 0}]


def test_known_name_fills_last_price(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 450}])
    changes = []
    ed = _editor(on_change=lambda: changes.append(1), live=False)
    ed.set_components([])
    ed.add_row()
    ed.rows[0].name.value = "esp32"
    ed.rows[0].on_name_blur(None)
    assert ed.rows[0].name.value == "ESP32" and ed.rows[0].cost.value == "450"
    assert changes


def test_pick_from_catalog_and_delete(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0})
    db.set_components(oid, [{"name": "Экран", "qty": 1, "unit_cost": 700}])
    ed = _editor()
    ed.set_components([])
    ed.pick("Экран")
    assert ed.get_components() == [{"name": "Экран", "qty": 1, "unit_cost": 700}]
    ed.remove(ed.rows[0])
    assert ed.rows == []
```

Дополнить `tests/test_price_view.py`:

```python
def test_breakdown_and_profit_show_electronics(temp_db):
    db.set_setting("currency", "₽")
    calc = {"material_cost": 0, "time_cost": 0, "defect_cost": 0, "reverse_cost": 0, "components_cost": 1200,
            "components_purchase": 1000, "soldering_cost": 500, "firmware_cost": 0, "purchase_cost": 0,
            "cost": 1000, "price": 1700, "has_print": False, "has_electronics": True, "has_purchase_price": False}
    texts = _texts(price_view.breakdown_rows(calc, defect_percent=0))
    assert "Компоненты" in texts and "1 200 ₽" in texts and "Пайка и сборка" in texts
    assert "Материал" not in texts and "Программирование" not in texts
    profit = _texts(price_view.profit_rows(calc, None))
    assert "Компоненты по закупке" in profit and "Пластик по закупке" not in profit
    assert "700 ₽" in profit
```

- [ ] **Step 2: Run to verify failure** — `.venv\Scripts\python.exe -m pytest tests/test_components_editor.py tests/test_price_view.py -q` → FAIL (`No module named 'app.components_editor'`, нет строки «Компоненты»).

- [ ] **Step 3: Implement**

`app/components_editor.py`:

```python
"""Строки компонентов электроники в заказе: название, кол-во, закупка за штуку, сумма строки.
Общие для «Нового заказа» и карточки заказа. Названия и последние цены подсказываются из прошлых заказов."""
from typing import Callable, Iterable, Mapping

import flet as ft

import db
import pricing
from app import theme

NAME_COL = {"xs": 12, "sm": 5}
QTY_COL = {"xs": 4, "sm": 2}
COST_COL = {"xs": 5, "sm": 3}
SUM_COL = {"xs": 3, "sm": 2}


class _Row:
    def __init__(self, editor: "ComponentsEditor", name: str, qty, unit_cost):
        self.editor = editor
        live = editor.on_input if editor.live else None
        commit = None if editor.live else editor.on_commit
        self.name = theme.field("Компонент", NAME_COL, value=name, dense=True, hint_text="напр. ESP32",
                                on_change=live, on_blur=self.on_name_blur)
        self.qty = theme.field("Кол-во", QTY_COL, value=pricing.fmt_number(qty), dense=True,
                               on_change=self._on_number_change, on_blur=commit)
        self.cost = theme.field("Закупка за шт", COST_COL, suffix_text="₽", dense=True,
                                value="" if unit_cost is None else pricing.fmt_number(unit_cost),
                                on_change=self._on_number_change, on_blur=commit)
        self.sum_text = ft.Text("", size=13, text_align=ft.TextAlign.RIGHT)
        self.control = ft.Row([
            theme.grid([self.name, self.qty, self.cost,
                        ft.Container(self.sum_text, col=SUM_COL, alignment=ft.alignment.center_right, height=40)],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip=theme.tip("Убрать компонент"),
                          on_click=lambda e: editor.remove(self)),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.refresh_sum()

    def values(self, strict: bool) -> dict | None:
        """{name, qty, unit_cost}; strict — с ошибками у полей и None, если число не распознано."""
        qty_text, cost_text = (self.qty.value or "").strip(), (self.cost.value or "").strip()
        qty = pricing.parse_number(qty_text) if qty_text else 1
        cost = pricing.parse_number(cost_text) if cost_text else 0
        if strict:
            self.qty.error_text = None if qty is not None else "Число"
            self.cost.error_text = None if cost is not None else "Сумма числом"
            if qty is None or cost is None:
                return None
        return {"name": (self.name.value or "").strip(), "qty": qty or 0, "unit_cost": cost or 0}

    def refresh_sum(self) -> None:
        v = self.values(strict=False)
        self.sum_text.value = pricing.money(v["qty"] * v["unit_cost"]) if v["name"] or v["unit_cost"] else ""

    def _on_number_change(self, e) -> None:
        self.refresh_sum()
        if self.editor.live:
            self.editor.on_input(e)
        else:
            self.editor.update()

    def on_name_blur(self, e) -> None:
        """Знакомое название — написание и последняя цена из прошлых заказов (если цену ещё не вводили)."""
        typed = (self.name.value or "").strip()
        known = next((n for n in self.editor.catalog if n.lower() == typed.lower()), None)
        if known:
            self.name.value = known
            if pricing.parse_number(self.cost.value) in (None, 0):
                self.cost.value = pricing.fmt_number(self.editor.catalog[known])
        self.refresh_sum()
        if self.editor.live:
            self.editor.on_input(e)
        else:
            self.editor.on_commit(e)


class ComponentsEditor(ft.Column):
    def __init__(self, on_change: Callable[[], None] | None = None, live: bool = True):
        super().__init__(spacing=8)
        self.on_change = on_change
        self.live = live
        self.rows: list[_Row] = []
        self.catalog: dict[str, float] = {}
        self.rows_column = ft.Column(spacing=8)
        self.empty_text = ft.Text("Компонентов пока нет.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.catalog_menu = ft.PopupMenuButton(
            content=ft.Row([ft.Icon(ft.Icons.HISTORY, size=18), ft.Text("Из прошлых заказов", size=13)],
                           spacing=6, tight=True),
            tooltip=theme.tip("Компоненты, которые уже были в заказах, — с последней ценой"), items=[],
        )
        self.controls = [
            self.rows_column,
            ft.Row([ft.OutlinedButton("Компонент", icon=ft.Icons.ADD, on_click=lambda e: self._add_clicked()),
                    self.catalog_menu], spacing=12, wrap=True),
        ]
        self._render()

    # ---------- данные ----------

    def load_catalog(self) -> None:
        self.catalog = db.component_catalog()
        self.catalog_menu.items = [
            ft.PopupMenuItem(text=f"{name} — {pricing.money(cost)}", on_click=lambda e, n=name: self.pick(n))
            for name, cost in self.catalog.items()
        ]
        self.catalog_menu.visible = bool(self.catalog)

    def set_components(self, rows: Iterable[Mapping]) -> None:
        self.load_catalog()
        self.rows = [_Row(self, r["name"], r["qty"], r["unit_cost"]) for r in rows]
        self._render()

    def add_row(self, name: str = "", qty: float = 1, unit_cost: float | None = None) -> None:
        self.rows.append(_Row(self, name, qty, unit_cost))
        self._render()

    def pick(self, name: str) -> None:
        """Выбор из прошлых заказов: в пустую последнюю строку или новой строкой."""
        cost = self.catalog.get(name, 0)
        last = self.rows[-1] if self.rows else None
        if last and not (last.name.value or "").strip():
            last.name.value, last.cost.value = name, pricing.fmt_number(cost)
            last.refresh_sum()
        else:
            self.add_row(name, 1, cost)
        self._changed()

    def remove(self, row: _Row) -> None:
        self.rows.remove(row)
        self._render()
        self._changed()

    def get_components(self) -> list[dict] | None:
        values = [r.values(strict=True) for r in self.rows]
        if any(v is None for v in values):
            self._safe_update()
            return None
        return [v for v in values if v["name"]]

    def preview(self) -> list[dict]:
        return [v for v in (r.values(strict=False) for r in self.rows) if v["name"]]

    # ---------- события ----------

    def on_input(self, e) -> None:
        if self.on_change:
            self.on_change()

    def on_commit(self, e) -> None:
        if self.on_change:
            self.on_change()

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()
        self._safe_update()

    def _add_clicked(self) -> None:
        self.add_row()
        self._safe_update()

    def _render(self) -> None:
        self.rows_column.controls = [r.control for r in self.rows] or [self.empty_text]

    def _safe_update(self) -> None:
        try:
            self.update()
        except AssertionError:  # ещё не на странице
            pass
```

`app/price_view.py` — заменить обе функции:

```python
def breakdown_rows(calc: dict, defect_percent: float, total: float | None = None) -> list[ft.Control]:
    """Печать (материал / время / брак / реверс) и электроника (компоненты / пайка / прошивка) — только
    включённые части, затем «Итого». total — если цена задана вручную."""
    rows = []
    if calc.get("has_print", True):
        rows += [theme.kv_row("Материал", pricing.money(calc["material_cost"])),
                 theme.kv_row("Время печати", pricing.money(calc["time_cost"]))]
        if defect_percent:
            rows.append(theme.kv_row(f"Брак {pricing.fmt_number(defect_percent)}%",
                                     f"+{pricing.money(calc['defect_cost'])}"))
        if calc["reverse_cost"]:
            rows.append(theme.kv_row("Реверс-моделирование", pricing.money(calc["reverse_cost"])))
    if calc.get("has_electronics"):
        rows.append(theme.kv_row("Компоненты", pricing.money(calc["components_cost"])))
        if calc["soldering_cost"]:
            rows.append(theme.kv_row("Пайка и сборка", pricing.money(calc["soldering_cost"])))
        if calc["firmware_cost"]:
            rows.append(theme.kv_row("Программирование", pricing.money(calc["firmware_cost"])))
    rows.append(ft.Divider(height=8))
    rows.append(theme.kv_row("Итого", pricing.money(calc["price"] if total is None else total), bold=True))
    return rows


def profit_rows(calc: dict, material: str | None, total: float | None = None) -> list[ft.Control]:
    """Себестоимость (пластик и компоненты по закупке) и прибыль — всё, что сверх неё.
    total — фактическая цена заказа, если задана вручную."""
    price = calc["price"] if total is None else total
    profit = price - calc["cost"]
    rows = []
    if calc.get("has_print", True):
        rows.append(theme.kv_row("Пластик по закупке", f"−{pricing.money(calc['purchase_cost'])}"))
    if calc.get("has_electronics"):
        rows.append(theme.kv_row("Компоненты по закупке", f"−{pricing.money(calc['components_purchase'])}"))
    rows.append(theme.kv_row("Прибыль", pricing.money(profit), bold=True,
                             color=theme.OK if profit >= 0 else theme.ERR))
    if calc.get("has_print", True) and material and not calc["has_purchase_price"]:
        rows.append(ft.Text(f"Закупка «{material}» не указана в «Ценах» — пластик считается бесплатным.",
                            size=12, color=theme.WARN))
    return rows
```

- [ ] **Step 4: Run tests** — `.venv\Scripts\python.exe -m pytest -q` → зелёное.

- [ ] **Step 5: Commit**

```bash
git add app/components_editor.py app/price_view.py tests/test_components_editor.py tests/test_price_view.py
git commit -m "feat: components editor and electronics rows in the price summary"
```

---

### Task 4: «Новый заказ» — переключатели частей и секция «Электроника»

**Files:**
- Modify: `app/screens/new_order.py`
- Test: `tests/test_new_order_electronics.py` (создать)

**Interfaces:**
- Consumes: `ComponentsEditor(on_change, live=True)`, `pricing.calc_price(... has_print, has_electronics, components, markup, soldering, firmware)`, `db.add_order` с новыми полями, `db.set_components`.
- Produces: атрибуты экрана `print_switch`, `electronics_switch`, `components_editor`, `markup_field`, `soldering_field`, `firmware_field`, `print_body`, `electronics_body`.

- [ ] **Step 1: Write the failing tests** — `tests/test_new_order_electronics.py`:

```python
"""«Новый заказ» с электроникой (без запуска окна)."""
import db
from app.screens.new_order import NewOrderScreen


def _screen(monkeypatch):
    db.set_setting("materials", {"PLA": 4})
    db.set_setting("purchase_prices", {"PLA": 2})
    db.set_setting("hour_rate", 50)
    db.set_setting("defect_percent", 0)
    created = []
    screen = NewOrderScreen(on_created=created.append)
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.components_editor.update = lambda: None
    screen.client_field.value = "Иван"
    return screen, created


def test_print_and_electronics_order(temp_db, monkeypatch):
    screen, created = _screen(monkeypatch)
    screen.material_dd.value = "PLA"
    screen.weight_field.value = "100"
    screen.hours_field.value = "2"
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    screen.components_editor.add_row("ESP32", 2, 450)
    screen.markup_field.value = "20"
    screen.soldering_field.value = "500"
    screen.firmware_field.value = "1500"
    screen._on_save(None)
    o = db.get_order(created[0])
    assert (o["has_print"], o["has_electronics"]) == (1, 1)
    assert o["price"] == 500 + 1080 + 500 + 1500
    assert o["cost"] == 200 + 900
    assert [r["name"] for r in db.list_components(o["id"])] == ["ESP32"]


def test_electronics_only_ignores_print_fields(temp_db, monkeypatch):
    screen, created = _screen(monkeypatch)
    screen.weight_field.value = "100"
    screen.print_switch.value = False
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    assert not screen.print_body.visible and screen.electronics_body.visible
    screen.components_editor.add_row("Лента", 1, 300)
    screen.markup_field.value = "0"
    screen._on_save(None)
    o = db.get_order(created[0])
    assert o["has_print"] == 0 and o["weight_g"] == 0 and o["material"] is None and o["price"] == 300


def test_no_parts_is_an_error(temp_db, monkeypatch):
    screen, created = _screen(monkeypatch)
    screen.print_switch.value = False
    screen._on_parts_change(None)
    screen._on_save(None)
    assert not created and "электрон" in screen.error_text.value.lower()


def test_bad_component_price_blocks_save(temp_db, monkeypatch):
    screen, created = _screen(monkeypatch)
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    screen.components_editor.add_row("ESP32", 1, 450)
    screen.components_editor.rows[0].cost.value = "пятьсот"
    screen._on_save(None)
    assert not created and screen.error_text.value


def test_markup_default_from_settings_and_reset(temp_db, monkeypatch):
    db.set_setting("components_markup", 35)
    screen, created = _screen(monkeypatch)
    assert screen.markup_field.value == "35"
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    screen.components_editor.add_row("ESP32", 1, 450)
    screen._on_save(None)
    assert created
    assert not screen.electronics_switch.value and screen.components_editor.rows == []
```

- [ ] **Step 2: Run to verify failure** — `.venv\Scripts\python.exe -m pytest tests/test_new_order_electronics.py -q` → FAIL (`no attribute 'components_editor'`).

- [ ] **Step 3: Implement in `app/screens/new_order.py`**

Импорт: `from app import client_pdf, input_hints, price_view, theme` → `from app import client_pdf, input_hints, price_view, theme` + `from app.components_editor import ComponentsEditor`.

В `__init__` после `reverse_checkbox`:

```python
        settings = db.get_settings()
        self.print_switch = ft.Switch(value=True, on_change=self._on_parts_change,
                                      tooltip=theme.tip("В заказе есть 3D-печать"))
        self.electronics_switch = ft.Switch(value=False, on_change=self._on_parts_change,
                                            tooltip=theme.tip("В заказе есть электроника"))
        self.components_editor = ComponentsEditor(on_change=lambda: self._recalc(None), live=True)
        self.markup_field = theme.field("Наценка на компоненты", third, suffix_text="%",
                                        value=pricing.fmt_number(settings["components_markup"]),
                                        on_change=self._recalc)
        self.soldering_field = theme.field("Пайка и сборка", third, suffix_text="₽", on_change=self._recalc)
        self.firmware_field = theme.field("Программирование (прошивка)", third, suffix_text="₽",
                                          on_change=self._recalc)
        self.print_body = ft.Column([
            theme.grid([self.material_dd, self.color_field, self.weight_field, self.hours_field,
                        self.qty_field, self.defect_field]),
            self.reverse_checkbox,
        ], spacing=14)
        self.electronics_body = ft.Column([
            ft.Text("На весь заказ: если устройств несколько — укажите компоненты на все.",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            self.components_editor,
            theme.grid([self.markup_field, self.soldering_field, self.firmware_field]),
        ], spacing=14, visible=False)
```

(Срок `deadline_field` уходит из секции «Печать» в секцию «Клиент» — он общий для заказа: сетка клиента `[client, contact, description, deadline]`, у `deadline_field` `col=half`.)

Секции формы:

```python
            theme.section("Клиент", [theme.grid([self.client_field, self.contact_field, self.description_field,
                                                 self.deadline_field])], icon=ft.Icons.PERSON_OUTLINE),
            theme.section("Печать", [self.print_body], icon=ft.Icons.PRECISION_MANUFACTURING,
                          actions=[self.print_switch]),
            theme.section("Электроника", [self.electronics_body], icon=ft.Icons.MEMORY,
                          actions=[self.electronics_switch]),
```

`deadline_field` создать с `col=half` вместо `third`.

Подзаголовок: `theme.page_header("Новый заказ", "Печать и/или электроника — цена считается сама")`.

В `did_mount` после подстановки брака:

```python
            self.markup_field.value = pricing.fmt_number(settings["components_markup"])
        self.components_editor.load_catalog()
```

Новые методы и замена `_recalc`:

```python
    def _on_parts_change(self, e) -> None:
        self.print_body.visible = bool(self.print_switch.value)
        self.electronics_body.visible = bool(self.electronics_switch.value)
        self._recalc(None)

    def _calc(self, components: list[dict]) -> dict:
        weight = (input_hints.check_weight(self.weight_field) or 0) if self.print_switch.value else 0
        hours = (input_hints.check_hours(self.hours_field) or 0) if self.print_switch.value else 0
        return pricing.calc_price(
            self.material_dd.value, weight, hours, int(pricing.parse_number(self.qty_field.value) or 1),
            bool(self.reverse_checkbox.value), pricing.parse_number(self.defect_field.value) or 0,
            has_print=bool(self.print_switch.value), has_electronics=bool(self.electronics_switch.value),
            components=components, markup=pricing.parse_number(self.markup_field.value) or 0,
            soldering=pricing.parse_number(self.soldering_field.value) or 0,
            firmware=pricing.parse_number(self.firmware_field.value) or 0,
        )

    def _recalc(self, e: ft.ControlEvent | None) -> None:
        result = self._calc(self.components_editor.preview())
        defect = pricing.parse_number(self.defect_field.value) or 0
        custom_price = pricing.parse_number(self.custom_price_field.value)
        self.breakdown_column.controls = price_view.breakdown_rows(result, defect, total=custom_price)
        self.profit_column.controls = price_view.profit_rows(result, self.material_dd.value, total=custom_price)
        if self.page:
            self.update()
```

`_on_save` — после проверки клиента:

```python
        has_print, has_el = bool(self.print_switch.value), bool(self.electronics_switch.value)
        if not (has_print or has_el):
            self.error_text.value = "Включите «Печать» или «Электронику»."
            self.update()
            return
        weight = input_hints.check_weight(self.weight_field) if has_print else 0
        hours = input_hints.check_hours(self.hours_field) if has_print else 0
        if weight is None or hours is None:
            ... (как сейчас)
        components = self.components_editor.get_components() if has_el else []
        money_fields = [(self.markup_field, "Наценка"), (self.soldering_field, "Пайка"),
                        (self.firmware_field, "Прошивка")] if has_el else []
        bad = [label for f, label in money_fields
               if (f.value or "").strip() and pricing.parse_number(f.value) is None]
        if components is None or bad:
            self.error_text.value = "Проверьте электронику: " + (", ".join(bad) if bad else "кол-во и цены компонентов") \
                                    + " — нужны числа."
            self.update()
            return
```

Расчёт: `calc = self._calc(components)` вместо прежнего `pricing.calc_price(...)`. В `db.add_order({...})`:

```python
            "material": self.material_dd.value if has_print else None,
            "color": (self.color_field.value or "") if has_print else "",
            "weight_g": weight,
            "print_hours": hours,
            ...
            "reverse_engineering": 1 if reverse and has_print else 0,
            "has_print": 1 if has_print else 0,
            "has_electronics": 1 if has_el else 0,
            "components_markup": pricing.parse_number(self.markup_field.value) or 0 if has_el else 0,
            "soldering_price": pricing.parse_number(self.soldering_field.value) or 0 if has_el else 0,
            "firmware_price": pricing.parse_number(self.firmware_field.value) or 0 if has_el else 0,
```

сразу после — `if components: db.set_components(order_id, components)`.

`_reset_form` — добавить:

```python
        self.print_switch.value = True
        self.electronics_switch.value = False
        self.print_body.visible, self.electronics_body.visible = True, False
        self.components_editor.set_components([])
        self.markup_field.value = pricing.fmt_number(db.get_settings()["components_markup"])
        self.soldering_field.value = ""
        self.firmware_field.value = ""
```

- [ ] **Step 4: Run tests** — `.venv\Scripts\python.exe -m pytest -q` → зелёное (включая старые тесты нового заказа).

- [ ] **Step 5: Commit**

```bash
git add app/screens/new_order.py tests/test_new_order_electronics.py
git commit -m "feat: electronics section in the new order form"
```

---

### Task 5: Карточка заказа — переключатели и электроника

**Files:**
- Modify: `app/screens/order_detail.py`
- Test: `tests/test_order_detail_electronics.py` (создать)

**Interfaces:**
- Consumes: `ComponentsEditor(on_change, live=False)`, `pricing.calc_order`, `pricing.recalc_order_price`, `db.set_components`, `db.list_components`.
- Produces: атрибуты `print_switch`, `electronics_switch`, `components_editor`, `markup_field`, `soldering_field`, `firmware_field`, `print_body`, `electronics_body`; методы `_on_parts_change(e)`, `_on_electronics_commit(e=None)`.

- [ ] **Step 1: Write the failing tests** — `tests/test_order_detail_electronics.py`:

```python
"""Карточка заказа с электроникой (без запуска окна)."""
import db
from app.screens.order_detail import OrderDetailScreen


def _screen(monkeypatch, **extra):
    db.set_setting("materials", {"PLA": 4})
    db.set_setting("purchase_prices", {"PLA": 2})
    db.set_setting("hour_rate", 50)
    oid = db.add_order({"client": "К", "contact": "", "material": "PLA", "weight_g": 100, "print_hours": 2,
                        "qty": 1, "cost": 200, "price": 500, **extra})
    screen = OrderDetailScreen(oid, on_back=lambda: None)
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.components_editor.update = lambda: None
    screen.refresh()
    return screen, oid


def test_enable_electronics_and_save_components(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch)
    screen.electronics_switch.value = True
    screen._on_parts_change(None)
    assert db.get_order(oid)["has_electronics"] == 1
    screen.components_editor.add_row("ESP32", 2, 450)
    screen.markup_field.value = "0"
    screen.soldering_field.value = "500"
    screen._on_electronics_commit()
    o = db.get_order(oid)
    assert o["price"] == 500 + 900 + 500 and o["cost"] == 200 + 900 and o["soldering_price"] == 500
    assert [r["name"] for r in db.list_components(oid)] == ["ESP32"]


def test_bad_number_does_not_save(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch, has_electronics=1)
    screen.components_editor.add_row("ESP32", 1, 450)
    screen.components_editor.rows[0].qty.value = "два"
    screen._on_electronics_commit()
    assert db.list_components(oid) == []
    screen.soldering_field.value = "много"
    screen.components_editor.rows[0].qty.value = "1"
    screen._on_electronics_commit()
    assert screen.soldering_field.error_text and db.list_components(oid) == []


def test_disable_print_hides_usage_and_drops_print_price(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch, has_electronics=1, soldering_price=700)
    screen.print_switch.value = False
    screen._on_parts_change(None)
    o = db.get_order(oid)
    assert o["has_print"] == 0 and o["price"] == 700 and o["weight_g"] == 100  # поля печати сохранены
    assert not screen.print_body.visible and not screen.usage_row.visible


def test_cannot_disable_both_parts(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch)
    screen.print_switch.value = False
    screen._on_parts_change(None)
    assert db.get_order(oid)["has_print"] == 1 and screen.print_switch.value is True


def test_refresh_loads_components(temp_db, monkeypatch):
    screen, oid = _screen(monkeypatch, has_electronics=1)
    db.set_components(oid, [{"name": "Экран", "qty": 1, "unit_cost": 700}])
    screen.refresh()
    assert [r.name.value for r in screen.components_editor.rows] == ["Экран"]
```

- [ ] **Step 2: Run to verify failure** — `.venv\Scripts\python.exe -m pytest tests/test_order_detail_electronics.py -q` → FAIL.

- [ ] **Step 3: Implement in `app/screens/order_detail.py`**

Импорт `from app.components_editor import ComponentsEditor`.

В `__init__` после `deadline_field` / `notes_field`:

```python
        self.print_switch = ft.Switch(on_change=self._on_parts_change, tooltip=theme.tip("В заказе есть 3D-печать"))
        self.electronics_switch = ft.Switch(on_change=self._on_parts_change,
                                            tooltip=theme.tip("В заказе есть электроника"))
        self.components_editor = ComponentsEditor(on_change=self._on_electronics_commit, live=False)
        self.markup_field = theme.field("Наценка на компоненты", third, suffix_text="%",
                                        on_blur=self._on_electronics_commit)
        self.soldering_field = theme.field("Пайка и сборка", third, suffix_text="₽",
                                           on_blur=self._on_electronics_commit)
        self.firmware_field = theme.field("Программирование (прошивка)", third, suffix_text="₽",
                                          on_blur=self._on_electronics_commit)
        self.print_body = ft.Column([theme.grid([
            self.material_field, self.color_field, self.weight_field, self.hours_field,
            self.qty_field, self.defect_field,
        ]), ft.Divider(height=4), self.usage_row], spacing=14)
        self.electronics_body = ft.Column([
            ft.Text("На весь заказ: «Кол-во, шт» умножает только печать.", size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT),
            self.components_editor,
            theme.grid([self.markup_field, self.soldering_field, self.firmware_field]),
        ], spacing=14)
```

`left`:

```python
        left = ft.Column([
            theme.section("Клиент", [theme.grid([self.client_field, self.contact_field, self.deadline_field,
                                                 self.notes_field, theme.in_col(self.customer_dd, {"xs": 12})])],
                          icon=ft.Icons.PERSON_OUTLINE),
            theme.section("Печать", [self.print_body], icon=ft.Icons.PRECISION_MANUFACTURING,
                          actions=[self.print_switch]),
            theme.section("Электроника", [self.electronics_body], icon=ft.Icons.MEMORY,
                          actions=[self.electronics_switch]),
        ], spacing=theme.SPACING, col={"xs": 12, "lg": 7})
```

(`deadline_field` — `col=half`.)

В `refresh()`:
- внутри `if not from_sync:` добавить

```python
            self.components_editor.set_components(db.list_components(self.order_id))
            self.markup_field.value = pricing.fmt_number(order["components_markup"])
            self.soldering_field.value = pricing.fmt_number(order["soldering_price"]) if order["soldering_price"] else ""
            self.firmware_field.value = pricing.fmt_number(order["firmware_price"]) if order["firmware_price"] else ""
            for f in (self.markup_field, self.soldering_field, self.firmware_field):
                f.error_text = None
```

- после `self.paid_switch.value = ...`:

```python
        self.print_switch.value = bool(order["has_print"])
        self.electronics_switch.value = bool(order["has_electronics"])
        self.print_body.visible = self.print_switch.value
        self.electronics_body.visible = self.electronics_switch.value
```

- `calc = pricing.calc_order(order)` вместо прежнего `pricing.calc_price(...)`.
- после `self._render_usage(order)`: `self.usage_row.visible = bool(order["has_print"])`.

Новые методы:

```python
    # ---------- части заказа: печать / электроника ----------

    def _on_parts_change(self, e) -> None:
        if not (self.print_switch.value or self.electronics_switch.value):
            self.page and self.page.open(ft.SnackBar(ft.Text("В заказе должна остаться печать или электроника.")))
            self.refresh()
            return
        db.update_order(self.order_id, has_print=1 if self.print_switch.value else 0,
                        has_electronics=1 if self.electronics_switch.value else 0)
        pricing.recalc_order_price(self.order_id)
        self.refresh()

    def _on_electronics_commit(self, e=None) -> None:
        components = self.components_editor.get_components()
        values = {}
        for f, key in ((self.markup_field, "components_markup"), (self.soldering_field, "soldering_price"),
                       (self.firmware_field, "firmware_price")):
            text = (f.value or "").strip()
            value = pricing.parse_number(text) if text else 0
            f.error_text = None if value is not None else "Число"
            values[key] = value
        if components is None or None in values.values():
            self.update()
            return
        db.set_components(self.order_id, components)
        db.update_order(self.order_id, **values)
        pricing.recalc_order_price(self.order_id)
        self.refresh()
```

- [ ] **Step 4: Run tests** — `.venv\Scripts\python.exe -m pytest -q` → зелёное.

- [ ] **Step 5: Commit**

```bash
git add app/screens/order_detail.py tests/test_order_detail_electronics.py
git commit -m "feat: electronics section in the order card"
```

---

### Task 6: Список заказов, «Цены», статистика, заставка

**Files:**
- Modify: `app/screens/orders_screen.py`, `app/screens/prices_screen.py`, `app/screens/stats_screen.py`, `app/main.py`
- Test: `tests/test_orders_list_electronics.py` (создать)

**Interfaces:**
- Consumes: `db.components_by_order()`, настройка `components_markup`.
- Produces: `orders_screen.order_parts(order, components) -> tuple[list[str], str]` — (иконки частей, подзаголовок); `PricesScreen.components_markup_field`.

- [ ] **Step 1: Write the failing tests** — `tests/test_orders_list_electronics.py`:

```python
"""Список заказов и «Цены» с электроникой."""
import flet as ft

import db
from app.screens import orders_screen
from app.screens.prices_screen import PricesScreen


def test_order_parts_icons_and_subtitle(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0, "material": "PLA",
                        "has_electronics": 1})
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 1}, {"name": "Экран", "qty": 1, "unit_cost": 1},
                            {"name": "Лента", "qty": 1, "unit_cost": 1}])
    icons, subtitle = orders_screen.order_parts(db.get_order(oid), db.list_components(oid))
    assert icons == [ft.Icons.PRECISION_MANUFACTURING, ft.Icons.MEMORY]
    assert subtitle == "PLA · ESP32, Экран…"


def test_order_parts_print_only_keeps_old_subtitle(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0, "description": "Крепление",
                        "material": "PETG"})
    icons, subtitle = orders_screen.order_parts(db.get_order(oid), [])
    assert icons == [ft.Icons.PRECISION_MANUFACTURING] and subtitle == "Крепление · PETG"


def test_orders_screen_renders_with_components(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 0, "price": 0, "has_print": 0, "has_electronics": 1})
    db.set_components(oid, [{"name": "ESP32", "qty": 1, "unit_cost": 1}])
    screen = orders_screen.OrdersScreen(on_open_order=lambda i: None)
    assert len(screen.list_view.controls) == 1


def test_prices_screen_saves_components_markup(temp_db, monkeypatch):
    screen = PricesScreen()
    monkeypatch.setattr(screen, "update", lambda: None)
    screen.refresh()
    assert screen.components_markup_field.value == "20"
    screen.components_markup_field.value = "30"
    screen._save_scalars(None)
    assert db.get_settings()["components_markup"] == 30
```

- [ ] **Step 2: Run to verify failure** — FAIL (`no attribute 'order_parts'`).

- [ ] **Step 3: Implement**

`orders_screen.py` — новая функция перед классом:

```python
def order_parts(order, components) -> tuple[list[str], str]:
    """Иконки частей заказа (печать / электроника) и подзаголовок: описание, материал печати
    или первые компоненты электроники."""
    icons = []
    parts = [order["description"]]
    if order["has_print"]:
        icons.append(ft.Icons.PRECISION_MANUFACTURING)
        parts.append(order["material"])
    if order["has_electronics"]:
        icons.append(ft.Icons.MEMORY)
        names = [c["name"] for c in components]
        parts.append(", ".join(names[:2]) + ("…" if len(names) > 2 else "") if names else "электроника")
    return icons, " · ".join(p for p in parts if p)
```

В `_render`: `components = db.components_by_order()` и `self._order_row(o, components.get(o["id"], []))`.

В `_order_row(self, o, components)`:

```python
        icons, subtitle_text = order_parts(o, components)
        title = ft.Row([
            ft.Text(f"#{o['id']}  {o['client']}", size=15, weight=ft.FontWeight.W_600,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
            *[ft.Icon(i, size=15, color=ft.Colors.ON_SURFACE_VARIANT,
                      tooltip=theme.tip("Печать" if i == ft.Icons.PRECISION_MANUFACTURING else "Электроника"))
              for i in icons],
        ], spacing=6)
        subtitle = ft.Text(subtitle_text or "без описания", size=12,
                           color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
```

Подсказка поиска: `"Поиск: клиент, контакт, описание, компонент"`.

`prices_screen.py`:

```python
        self.components_markup_field = theme.field(
            "Наценка на компоненты", {"xs": 12, "sm": 6}, suffix_text="%", on_blur=self._save_scalars,
            helper_text="Электроника: к закупке компонентов; подставляется в новые заказы",
        )
```

добавить в `theme.grid([...])` настроек после `self.defect_field`; в `refresh()` —
`self.components_markup_field.value = pricing.fmt_number(settings["components_markup"])`; в `_save_scalars()` —

```python
        markup = pricing.parse_number(self.components_markup_field.value)
        if markup is not None:
            db.set_setting("components_markup", markup)
```

Текст «Как считается прибыль» →
`"Прибыль = цена заказа − пластик и компоненты по закупке. Часы печати, наценки, брак, реверс-моделирование, пайка, прошивка и ручная цена — всё это прибыль."`; подзаголовок экрана → `"Закупка пластика, наценка на компоненты и параметры расчёта"`.

`stats_screen.py` `_w_profit`: `self._label("пластик по закупке")` → `self._label("закупка: пластик + компоненты")`.

`app/main.py`: `Splash(APP_NAME, "заказы 3D-печати")` → `Splash(APP_NAME, "заказы: печать и электроника")`; докстринг модуля — «…панели управления заказами: 3D-печать и электроника».

- [ ] **Step 4: Run tests** — `.venv\Scripts\python.exe -m pytest -q` → зелёное.

- [ ] **Step 5: Commit**

```bash
git add app/screens/orders_screen.py app/screens/prices_screen.py app/screens/stats_screen.py app/main.py tests/test_orders_list_electronics.py
git commit -m "feat: electronics in the orders list, prices, stats and splash"
```

---

### Task 7: PDF для клиента

**Files:**
- Modify: `app/client_pdf.py`
- Test: `tests/test_client_pdf.py` (дополнить)

**Interfaces:**
- Consumes: `pricing.calc_order`, `db.list_components`.
- Produces: `client_pdf.price_lines(order)` со строками компонентов, «Пайка и сборка», «Программирование (прошивка)»; `client_pdf.detail_rows(order) -> list[tuple[str, str]]`.

- [ ] **Step 1: Write the failing tests** — в конец `tests/test_client_pdf.py`:

```python
def _electronics_order(price=None, **extra) -> int:
    oid = db.add_order({"client": "Пётр", "contact": "", "description": "Лампа", "material": "PLA",
                        "weight_g": 50, "print_hours": 1, "qty": 1, "cost": 0, "price": 0,
                        "has_electronics": 1, "components_markup": 20, "soldering_price": 500,
                        "firmware_price": 1500, **extra})
    db.set_components(oid, [{"name": "ESP32-WROOM", "qty": 2, "unit_cost": 450},
                            {"name": "Лента WS2812", "qty": 1, "unit_cost": 333}])
    pricing.recalc_order_price(oid)
    if price is not None:
        db.update_order(oid, price=price)
    return oid


def test_price_lines_list_each_component_and_work(temp_db):
    _setup()
    oid = _electronics_order()
    lines = client_pdf.price_lines(db.get_order(oid))
    names = [n for n, _, _ in lines]
    assert names == ["Материал", "Время печати", "ESP32-WROOM", "Лента WS2812", "Пайка и сборка",
                     "Программирование (прошивка)"]
    esp = lines[2]
    assert esp[1] == "2 шт × 540 ₽" and esp[2] == 1080
    assert sum(v for _, _, v in lines) == round(db.get_order(oid)["price"])


def test_electronics_pdf_hides_purchase_and_markup(temp_db):
    _setup()
    oid = _electronics_order()
    text = " ".join(f"{n} {how}" for n, how, _ in client_pdf.price_lines(db.get_order(oid))).lower()
    assert "450" not in text and "наценк" not in text and "закуп" not in text


def test_electronics_only_details_skip_print_rows(temp_db, tmp_path):
    _setup()
    oid = _electronics_order(has_print=0)
    pricing.recalc_order_price(oid)
    labels = [label for label, _ in client_pdf.detail_rows(db.get_order(oid))]
    assert "Материал" not in labels and "Вес" not in labels and "Количество" not in labels
    assert ("Электроника", "ESP32-WROOM × 2, Лента WS2812") in client_pdf.detail_rows(db.get_order(oid))
    assert client_pdf.build_order_pdf(oid, tmp_path).read_bytes().startswith(b"%PDF")


def test_electronics_manual_price_gets_discount_row(temp_db):
    _setup()
    oid = _electronics_order(price=3000)
    lines = client_pdf.price_lines(db.get_order(oid))
    assert lines[-1][0] == "Скидка" and sum(v for _, _, v in lines) == 3000
```

- [ ] **Step 2: Run to verify failure** — `.venv\Scripts\python.exe -m pytest tests/test_client_pdf.py -q` → FAIL.

- [ ] **Step 3: Implement in `app/client_pdf.py`**

Докстринг модуля: «Внутренние цифры (закупка пластика и компонентов, наценка, себестоимость, прибыль) в документ не попадают.»

`price_lines` — расчёт через `calc_order`, после строки реверса:

```python
    calc = pricing.calc_order(order)
    ...
    if calc["has_electronics"]:
        factor = 1 + (order["components_markup"] or 0) / 100
        for part in db.list_components(order["id"]):
            value = (part["qty"] or 0) * (part["unit_cost"] or 0) * factor
            if value:
                lines.append((part["name"], f"{pricing.fmt_number(part['qty'])} шт × "
                                            f"{_rate(part['unit_cost'] * factor)} {cur}", value))
        if calc["soldering_cost"]:
            lines.append(("Пайка и сборка", "сборка и пайка устройства", calc["soldering_cost"]))
        if calc["firmware_cost"]:
            lines.append(("Программирование (прошивка)", "написание и загрузка прошивки", calc["firmware_cost"]))
```

(убрать прежние `weight, hours, defect, reverse` → `calc_price(...)`; переменные `qty`, `weight`, `hours`, `defect` остаются для текстов строк печати.)

Новая функция `detail_rows(order)` и использование в `build_order_pdf` вместо списка `details`:

```python
def detail_rows(order) -> list[tuple[str, str]]:
    """«Детали заказа»: строки печати — только если она есть, электроника — списком компонентов."""
    qty = order["qty"] or 1
    rows = [("Клиент", order["client"]), ("Контакт", order["contact"]), ("Описание", order["description"])]
    if order["has_print"]:
        weight = f"{pricing.fmt_number(order['weight_g'])} г" + (" за 1 шт" if qty > 1 else "")
        hours = pricing.fmt_hours(order["print_hours"]) + (" за 1 шт" if qty > 1 else "")
        defect = order["defect_percent"] or 0
        rows += [
            ("Материал", order["material"]),
            ("Цвет", order["color"]),
            ("Вес", weight if order["weight_g"] else ""),
            ("Время печати", hours if order["print_hours"] else ""),
            ("Количество", f"{qty} шт"),
            ("Брак", f"{pricing.fmt_number(defect)}% от стоимости печати" if defect else "не учитывается"),
        ]
    if order["has_electronics"]:
        parts = [p["name"] + (f" × {pricing.fmt_number(p['qty'])}" if p["qty"] != 1 else "")
                 for p in db.list_components(order["id"])]
        rows.append(("Электроника", ", ".join(parts)))
    rows.append(("Срок", pricing.fmt_date(order["deadline"]) if order["deadline"] else "по договорённости"))
    return rows
```

В `build_order_pdf`: `for label, value in detail_rows(order): _detail_row(pdf, label, value or "—", width)`.

- [ ] **Step 4: Run tests** — `.venv\Scripts\python.exe -m pytest -q` → зелёное.

- [ ] **Step 5: Commit**

```bash
git add app/client_pdf.py tests/test_client_pdf.py
git commit -m "feat: electronics components and work in the client PDF"
```

---

### Task 8: Смета и выгрузка

**Files:**
- Modify: `app/report.py`, `app/export.py`
- Test: `tests/test_report_and_dates.py`, `tests/test_export.py` (дополнить)

**Interfaces:**
- Consumes: `pricing.calc_order`, `db.components_by_order()`.
- Produces: в `report_rows` ключи `components, soldering, firmware`; колонки сметы «Компоненты (закупка)», «Пайка», «Прошивка» между «Долг» и «Себестоимость»; в выгрузке — «Электроника», «Компоненты (закупка)», «Пайка», «Прошивка» перед «Себестоимость».

- [ ] **Step 1: Write the failing tests**

В `tests/test_report_and_dates.py`:

```python
def test_report_counts_electronics(temp_db):
    from datetime import date
    from app import report
    db.set_setting("purchase_prices", {"PLA": 2})
    oid = db.add_order({"client": "К", "contact": "", "material": "PLA", "weight_g": 100, "qty": 1,
                        "cost": 0, "price": 5000, "has_electronics": 1, "soldering_price": 500,
                        "firmware_price": 1500})
    db.set_components(oid, [{"name": "ESP32", "qty": 2, "unit_cost": 450}])
    today = date.today()
    rows = report.report_rows(today, today)
    r = rows[0]
    assert (r["components"], r["soldering"], r["firmware"], r["cost"]) == (900, 500, 1500, 1100)
    assert r["profit"] == 5000 - 1100
    names = [c[0] for c in report.COLUMNS]
    assert names[9] == "Цена"
    assert names.index("Компоненты (закупка)") < names.index("Себестоимость")
```

В `tests/test_export.py`:

```python
def test_orders_sheet_has_electronics_columns(temp_db):
    oid = db.add_order({"client": "К", "contact": "", "cost": 900, "price": 3000, "has_electronics": 1,
                        "soldering_price": 500})
    db.set_components(oid, [{"name": "ESP32", "qty": 2, "unit_cost": 450}])
    rows = export.build_orders_sheet()
    row = dict(zip(rows[0], rows[1]))
    assert row["Электроника"] == "Да" and row["Компоненты (закупка)"] == 900 and row["Пайка"] == 500
    assert row["Прошивка"] == 0
```

- [ ] **Step 2: Run to verify failure** — FAIL (`KeyError: 'components'`).

- [ ] **Step 3: Implement**

`app/report.py`:
- докстринг: «…себестоимость (пластик и компоненты по закупке), пайка и прошивка, прибыль…»;
- `COLUMNS`: после `("Долг", 12, "#,##0", True),` вставить

```python
    ("Компоненты (закупка)", 13, "#,##0", True),
    ("Пайка", 10, "#,##0", True),
    ("Прошивка", 11, "#,##0", True),
```

а `("Себестоимость (пластик)", 15, ...)` → `("Себестоимость", 15, "#,##0", True)`;
- `report_rows`:

```python
    rows = []
    for o in db.orders_between(start.isoformat(), end.isoformat()):
        qty = o["qty"] or 1
        calc = pricing.calc_order(o)
        printed = bool(o["has_print"])
        price = o["price"] or 0
        prepayment = o["prepayment"] or 0
        received = price if o["paid"] else prepayment
        rows.append({
            "id": o["id"], "date": o["created_at"][:10], "client": o["client"] or "",
            "description": o["description"] or "", "material": (o["material"] or "") if printed else "",
            "grams": (o["weight_g"] or 0) * qty if printed else 0,
            "hours": (o["print_hours"] or 0) * qty if printed else 0, "qty": qty,
            "status": db.STATUSES.get(o["status"], o["status"]).split(" ", 1)[-1],
            "price": price, "prepayment": prepayment, "paid": bool(o["paid"]),
            "received": received, "debt": max(price - received, 0),
            "components": calc["components_purchase"], "soldering": calc["soldering_cost"],
            "firmware": calc["firmware_cost"],
            "cost": calc["cost"],
            "profit": price - calc["cost"],
        })
    return rows
```

(убрать неиспользуемую `settings`);
- `summary`: суммировать также `"components", "soldering", "firmware"`; `by_material` — только строки с `r["grams"]`;
- `keys` в `write_report`: `..., "debt", "components", "soldering", "firmware", "cost", "profit"]`;
- лист «Итоги»: после «Ждём доплату» вставить

```python
        ("Компоненты по закупке", total["components"], "#,##0"),
        ("Пайка", total["soldering"], "#,##0"),
        ("Прошивка", total["firmware"], "#,##0"),
```

и «Себестоимость (пластик по закупке)» → «Себестоимость (пластик + компоненты)».

`app/export.py`:
- `ORDER_COLUMNS`: перед `"Себестоимость"` вставить `"Электроника", "Компоненты (закупка)", "Пайка", "Прошивка",`;
- в `build_orders_sheet`: `components = db.components_by_order()` перед циклом; после `o["prepayment"] or 0,`:

```python
            "Да" if o["has_electronics"] else "Нет",
            round(sum(c["qty"] * c["unit_cost"] for c in components.get(o["id"], [])), 2)
            if o["has_electronics"] else 0,
            o["soldering_price"] or 0 if o["has_electronics"] else 0,
            o["firmware_price"] or 0 if o["has_electronics"] else 0,
```

- `build_prices_sheet`: после «Реверс-моделирование» — `rows.append(["Наценка на компоненты, %", settings["components_markup"]])`.

- [ ] **Step 4: Run tests** — `.venv\Scripts\python.exe -m pytest -q` → зелёное.

- [ ] **Step 5: Commit**

```bash
git add app/report.py app/export.py tests/test_report_and_dates.py tests/test_export.py
git commit -m "feat: electronics columns in the period estimate and export"
```

---

### Task 9: Проверка в окне, сборка 1.10.0, установка

**Files:**
- Modify: `build_exe.bat` (версия)

- [ ] **Step 1: Ручная проверка из исходников на копии данных** — скопировать `orders.db` из папки «Студии» во временную папку, запустить приложение с `DATA_DIR` на неё и без Google Таблицы (переменные `.env` не подставлять), открыть: «Новый заказ» (печать + электроника, только электроника), карточку, список, «Цены», статистику, PDF. Проверить, что старые заказы показывают прежние цены.

- [ ] **Step 2: Версия** — в `build_exe.bat` `--product-version 1.9.0 --file-version 1.9.0.0` → `1.10.0` / `1.10.0.0`. Полный прогон `pytest`.

- [ ] **Step 3: Сборка** — команда `flet pack` из `build_exe.bat` (без завершающего `pause`), результат в `dist\`.

- [ ] **Step 4: Установка** — в папке «Студии»: `orders.db` → `orders.backup-before-1.10.0.db`; текущий exe → `Студия Паулюкевичуса (старая 1.9.0).exe` (прежнюю «старая 1.8.3» не трогать); новый exe из `dist\` — на место.

- [ ] **Step 5: Commit**

```bash
git add build_exe.bat
git commit -m "chore: version 1.10.0"
```
