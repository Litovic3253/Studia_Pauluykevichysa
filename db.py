"""Хранилище заказов и настроек (SQLite)."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).with_name("orders.db")

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
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        _migrate_pricing_v2(c)


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


def get_order(order_id: int):
    with _conn() as c:
        return c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def update_order(order_id: int, **fields) -> None:
    if not fields:
        return
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
