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


def parse_weight(text: str | None) -> float | None:
    """Принимает «454,28», «454.28», «454,28 г», «454.28гр», «12 грамм»."""
    if not text:
        return None
    t = re.sub(r"\s*(?:г|гр|грамм(?:а|ов)?)\.?$", "", text.strip().lower())
    return parse_number(t)


_HOURS_RE = re.compile(
    r"(?:(?P<d>\d+(?:[.,]\d+)?)\s*д(?:ень|ня|ней|н)?\.?)?\s*"
    r"(?:(?P<h>\d+(?:[.,]\d+)?)\s*ч(?:ас|аса|асов)?\.?)?\s*"
    r"(?:(?P<m>\d+)\s*м(?:ин(?:ут[аы]?)?)?\.?)?"
)


def parse_hours(text: str | None) -> float | None:
    """Принимает «2.5», «2,5», «2:30», «2ч 30м», «2ч 30 мин», «150 мин», «1д 6ч 46м» (1 день = 24 ч)."""
    if not text:
        return None
    t = text.strip().lower()
    if m := re.fullmatch(r"(\d+):(\d{1,2})", t):
        return int(m[1]) + int(m[2]) / 60
    if (m := _HOURS_RE.fullmatch(t)) and (m["d"] or m["h"] or m["m"]):
        days = float((m["d"] or "0").replace(",", "."))
        hours = float((m["h"] or "0").replace(",", "."))
        return days * 24 + hours + int(m["m"] or 0) / 60
    return parse_number(t)


def fmt_hours(hours: float | None) -> str:
    """30.77 → «1д 6ч 46м», 2.5 → «2ч 30м» — с точностью до минуты, читается обратно parse_hours()."""
    total_minutes = round((hours or 0) * 60)
    days, rest = divmod(total_minutes, 24 * 60)
    h, m = divmod(rest, 60)
    parts = [f"{days}д"] if days else []
    if h:
        parts.append(f"{h}ч")
    if m:
        parts.append(f"{m}м")
    return " ".join(parts) or "0ч"


def fmt_number(value: float | None) -> str:
    """454.28 → «454,28», 50.0 → «50» (не больше двух знаков после запятой)."""
    return f"{value or 0:.2f}".rstrip("0").rstrip(".").replace(".", ",")


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


_DATE_TYPING_RE = re.compile(r"\d{1,12}|\d{2}\.\d{0,2}|\d{2}\.\d{2}\.\d{0,4}")


def format_date_input(text: str | None) -> str:
    """Точки по мере набора: «27092026» → «27.09.2026», «2709» → «27.09».
    Слова («завтра») и свой формат («1.1.26») не трогает — их разберёт parse_date()."""
    t = (text or "").strip()
    if not _DATE_TYPING_RE.fullmatch(t):
        return text or ""
    digits = t.replace(".", "")[:8]
    parts = [digits[:2], digits[2:4], digits[4:8]]
    result = parts[0]
    if len(digits) > 2 or t.endswith(".") and len(digits) == 2:
        result += "." + parts[1]
    if len(digits) > 4 or t.count(".") == 2 and len(digits) == 4:
        result += "." + parts[2]
    return result


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


def calc_price(material: str | None, weight_g: float, hours: float, qty: int, reverse: bool = False,
               defect_percent: float = 0) -> dict:
    """Брак — надбавка в % от стоимости печати (материал + время); на реверс-моделирование не начисляется.
    cost — себестоимость (пластик по закупке), profit — всё, что сверх неё."""
    s = db.get_settings()
    per_kg = s["materials"].get(material or "", 0)
    material_cost = weight_g * qty * per_kg / 1000
    time_cost = hours * qty * s["hour_rate"]
    defect_cost = (material_cost + time_cost) * (defect_percent or 0) / 100
    reverse_cost = s["reverse_price"] if reverse else 0
    price = material_cost + time_cost + defect_cost + reverse_cost
    exp = db.expense(material, weight_g, hours, qty, s)
    return {
        "material_cost": material_cost, "time_cost": time_cost, "defect_cost": defect_cost,
        "reverse_cost": reverse_cost, "price": price,
        "purchase_cost": exp["plastic"], "cost": exp["total"], "profit": price - exp["total"],
        "has_purchase_price": bool(s.get("purchase_prices", {}).get(material or "")),
    }


def defect_line(defect_percent: float, defect_cost: float) -> str:
    """«Брак 10%: +100 ₽» — пустая строка, если брак 0%."""
    if not defect_percent:
        return ""
    return f"Брак {fmt_number(defect_percent)}%: +{money(defect_cost)}"


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
    p = calc_price(o["material"], o["weight_g"], o["print_hours"], o["qty"], bool(o["reverse_engineering"]),
                   o["defect_percent"] or 0)
    db.update_order(oid, cost=round(p["cost"], 2), price=p["price"])


def remaining_to_pay(order) -> float:
    """Сколько клиент ещё должен: цена минус предоплата (0, если заказ оплачен)."""
    if order["paid"]:
        return 0
    return max((order["price"] or 0) - (order["prepayment"] or 0), 0)
