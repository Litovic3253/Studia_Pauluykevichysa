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
