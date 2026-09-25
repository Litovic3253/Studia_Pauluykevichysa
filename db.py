"""Хранилище заказов и настроек (SQLite)."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from paths import DATA_DIR

DB_PATH = DATA_DIR / "orders.db"

STATUSES = {
    "new": "🆕 Новый",
    "queued": "⏳ В очереди",
    "printing": "🖨 Печатается",
    "post": "🛠 Постобработка",
    "ready": "✅ Готов",
    "delivered": "📦 Выдан",
    "cancelled": "❌ Отменён",
}
ACTIVE_STATUSES = ("new", "queued", "printing", "post", "ready")

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


@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        with c:  # коммит или откат
            yield c
    finally:
        c.close()


def init() -> None:
    with _conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                client TEXT NOT NULL,
                contact TEXT,
                description TEXT,
                file_id TEXT,
                file_type TEXT,
                material TEXT,
                color TEXT,
                weight_g REAL DEFAULT 0,
                print_hours REAL DEFAULT 0,
                qty INTEGER DEFAULT 1,
                deadline TEXT,
                cost REAL DEFAULT 0,
                price REAL DEFAULT 0,
                status TEXT DEFAULT 'new',
                paid INTEGER DEFAULT 0,
                notes TEXT,
                reverse_engineering INTEGER DEFAULT 0
            )"""
        )
        cols = {r["name"] for r in c.execute("PRAGMA table_info(orders)")}
        if "reverse_engineering" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN reverse_engineering INTEGER DEFAULT 0")
        if "updated_at" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN updated_at TEXT")
            c.execute("UPDATE orders SET updated_at = created_at WHERE updated_at IS NULL")
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


def _migrate_pricing_v2(c) -> None:
    """Разовый переход на прямой расчёт цены: новые ставки материалов/часа, без наценки."""
    if c.execute("SELECT 1 FROM settings WHERE key = 'pricing_v2'").fetchone():
        return
    c.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('materials', ?)",
        (json.dumps(DEFAULT_SETTINGS["materials"], ensure_ascii=False),),
    )
    c.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('hour_rate', ?)",
        (json.dumps(DEFAULT_SETTINGS["hour_rate"]),),
    )
    c.execute("DELETE FROM settings WHERE key IN ('markup', 'min_price')")
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('pricing_v2', 'true')")


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


# ---------- настройки ----------

def get_settings() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT key, value FROM settings").fetchall()
    settings = dict(DEFAULT_SETTINGS)
    settings.update({r["key"]: json.loads(r["value"]) for r in rows})
    return settings


def set_setting(key: str, value) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )


# ---------- клиенты ----------

def find_or_create_customer(name: str, contact: str | None) -> int:
    name = (name or "").strip()
    contact = (contact or "").strip()
    name_lower = name.lower()
    contact_lower = contact.lower()
    with _conn() as c:
        # Fetch all customers and do case-insensitive comparison in Python
        # (LOWER() in SQLite doesn't handle Cyrillic correctly)
        for row in c.execute("SELECT id, name, contact FROM customers"):
            if row["name"].lower() == name_lower and (row["contact"] or "").lower() == contact_lower:
                return row["id"]
        # No match found, create a new customer
        cur = c.execute(
            "INSERT INTO customers (name, contact, notes, created_at) VALUES (?, ?, '', ?)",
            (name, contact, datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def get_customer(customer_id: int):
    with _conn() as c:
        return c.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()


def list_customers(search: str = ""):
    search_lower = search.lower()
    with _conn() as c:
        all_customers = c.execute(
            """SELECT c.*,
                COUNT(o.id) AS orders_count,
                COALESCE(SUM(CASE WHEN o.paid = 1 THEN o.price END), 0) AS paid_total,
                COALESCE(SUM(CASE WHEN o.paid = 0 AND o.status != 'cancelled' THEN o.price END), 0) AS debt_total
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.id
            GROUP BY c.id
            ORDER BY c.name COLLATE NOCASE""",
        ).fetchall()

    if not search_lower:
        return all_customers

    # Filter results in Python for case-insensitive search with Cyrillic support
    filtered = []
    for row in all_customers:
        if (search_lower in row["name"].lower() or
            (row["contact"] and search_lower in row["contact"].lower())):
            filtered.append(row)
    return filtered


def update_customer(customer_id: int, **fields) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE customers SET {sets} WHERE id = ?", [*fields.values(), customer_id])


def rename_customer(customer_id: int, name: str, contact: str | None) -> None:
    """Меняет имя/контакт клиента и копирует их во все его заказы (там они хранятся копией)."""
    name = (name or "").strip()
    contact = (contact or "").strip()
    if not name:
        raise ValueError("Имя клиента не может быть пустым")
    with _conn() as c:
        c.execute("UPDATE customers SET name = ?, contact = ? WHERE id = ?", (name, contact, customer_id))
        c.execute("UPDATE orders SET client = ?, contact = ? WHERE customer_id = ?", (name, contact, customer_id))


def delete_customer(customer_id: int, delete_orders: bool = False) -> None:
    """Удаляет клиента. Его заказы либо остаются (отвязываются, имя в заказе сохраняется),
    либо удаляются вместе с вложениями."""
    with _conn() as c:
        if delete_orders:
            c.execute(
                "DELETE FROM attachments WHERE order_id IN (SELECT id FROM orders WHERE customer_id = ?)",
                (customer_id,),
            )
            c.execute("DELETE FROM orders WHERE customer_id = ?", (customer_id,))
        else:
            c.execute("UPDATE orders SET customer_id = NULL WHERE customer_id = ?", (customer_id,))
        c.execute("DELETE FROM customers WHERE id = ?", (customer_id,))


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
        now = datetime.now().isoformat(timespec="seconds")
        cur = c.execute(
            f"INSERT INTO orders (created_at, updated_at, {', '.join(fields)}) "
            f"VALUES (?, ?, {', '.join('?' * len(fields))})",
            [now, now, *values],
        )
        return cur.lastrowid


def get_order(order_id: int):
    with _conn() as c:
        return c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def update_order(order_id: int, **fields) -> None:
    if not fields:
        return
    # Полное разрешение (с микросекундами), чтобы обновление сразу после создания
    # заказа (в течение той же секунды) тоже меняло change_fingerprint().
    fields = {**fields, "updated_at": datetime.now().isoformat()}
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE orders SET {sets} WHERE id = ?", [*fields.values(), order_id])


def delete_order(order_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM orders WHERE id = ?", (order_id,))


def list_orders(kind: str = "active", limit: int = 40):
    order_by = "CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline, id"
    with _conn() as c:
        if kind == "active":
            q = f"SELECT * FROM orders WHERE status IN ({','.join('?' * len(ACTIVE_STATUSES))}) ORDER BY {order_by} LIMIT ?"
            return c.execute(q, (*ACTIVE_STATUSES, limit)).fetchall()
        if kind == "done":
            return c.execute(
                "SELECT * FROM orders WHERE status IN ('delivered', 'cancelled') ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        if kind == "unpaid":
            return c.execute(
                "SELECT * FROM orders WHERE paid = 0 AND status != 'cancelled' ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def list_orders_all():
    """Все заказы без ограничения — используется для экспорта/синхронизации."""
    with _conn() as c:
        return c.execute("SELECT * FROM orders ORDER BY id").fetchall()


def search_orders(text: str, limit: int = 40):
    like = f"%{text}%"
    with _conn() as c:
        return c.execute(
            "SELECT * FROM orders WHERE client LIKE ? OR contact LIKE ? OR description LIKE ? "
            "OR notes LIKE ? ORDER BY id DESC LIMIT ?",
            (like, like, like, like, limit),
        ).fetchall()


def stats() -> dict:
    with _conn() as c:
        by_status = {
            r["status"]: r["n"]
            for r in c.execute("SELECT status, COUNT(*) n FROM orders GROUP BY status")
        }
        month = datetime.now().strftime("%Y-%m")
        row = c.execute(
            """SELECT
                COALESCE(SUM(CASE WHEN paid = 1 THEN price END), 0) AS revenue,
                COALESCE(SUM(CASE WHEN paid = 1 THEN price - cost END), 0) AS profit,
                COALESCE(SUM(CASE WHEN paid = 0 AND status != 'cancelled' THEN price END), 0) AS unpaid,
                COALESCE(SUM(CASE WHEN status != 'cancelled' THEN weight_g * qty END), 0) AS grams
            FROM orders"""
        ).fetchone()
        month_row = c.execute(
            """SELECT COUNT(*) AS n,
                COALESCE(SUM(CASE WHEN paid = 1 THEN price END), 0) AS revenue
            FROM orders WHERE substr(created_at, 1, 7) = ? AND status != 'cancelled'""",
            (month,),
        ).fetchone()
        materials = c.execute(
            """SELECT material, SUM(weight_g * qty) AS grams FROM orders
            WHERE status != 'cancelled' AND material IS NOT NULL
            GROUP BY material ORDER BY grams DESC"""
        ).fetchall()
    return {
        "by_status": by_status,
        "revenue": row["revenue"],
        "profit": row["profit"],
        "unpaid": row["unpaid"],
        "grams": row["grams"],
        "month_orders": month_row["n"],
        "month_revenue": month_row["revenue"],
        "materials": [(m["material"], m["grams"]) for m in materials],
    }


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


def list_attachments(order_id: int) -> list[sqlite3.Row]:
    with _conn() as c:
        return c.execute(
            "SELECT * FROM attachments WHERE order_id = ? ORDER BY id", (order_id,)
        ).fetchall()


def get_attachment(attachment_id: int) -> sqlite3.Row | None:
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
            "(SELECT COALESCE(MAX(updated_at), '') FROM orders) AS max_updated_at, "
            "(SELECT COUNT(*) FROM customers) AS customers_count, "
            "(SELECT COUNT(*) FROM attachments) AS attachments_count, "
            # Цены и карточки клиентов не имеют updated_at — берём их содержимое целиком
            # (десятки строк). theme_mode исключён: смена темы — не изменение данных.
            "(SELECT group_concat(key || '=' || value, ';') FROM "
            "(SELECT key, value FROM settings WHERE key != 'theme_mode' ORDER BY key)) AS settings_sig, "
            "(SELECT group_concat(id || '|' || name || '|' || COALESCE(contact, '') || '|' "
            "|| COALESCE(notes, ''), ';') FROM (SELECT * FROM customers ORDER BY id)) AS customers_sig"
        ).fetchone()
    return (
        row["orders_count"], row["max_order_id"], row["max_updated_at"],
        row["customers_count"], row["attachments_count"],
        row["settings_sig"], row["customers_sig"],
    )
