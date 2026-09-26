"""PDF для клиента: детали заказа, итоговая сумма и из чего она складывается.

Файл кладётся в «PDF для клиентов» рядом с программой — его можно сразу отправить заказчику.
Внутренние цифры (закупка пластика, себестоимость, прибыль) в документ не попадают."""
import os
import re
import sys
from datetime import date
from pathlib import Path

import flet as ft
from fpdf import FPDF

import db
import pricing
from paths import DATA_DIR

PDF_DIR = DATA_DIR / "PDF для клиентов"
STUDIO = "Студия Паулюкевичуса"
FONTS_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets" / "fonts"

INK = (24, 24, 27)       # основной текст
MUTED = (113, 113, 122)  # подписи
LINE = (228, 228, 231)   # тонкие линии
ACCENT = (250, 189, 47)  # жёлтый, как значок приложения
SOFT = (254, 247, 224)   # подложка итоговой суммы


def file_name(order) -> str:
    client = re.sub(r'[<>:"/\\|?*\s]+', "_", (order["client"] or "").strip()).strip("_")
    return f"Заказ_{order['id']}{'_' + client if client else ''}.pdf"


def _money(value: float) -> str:
    return pricing.money(value).replace(" ", " ")


def _rate(value: float) -> str:
    """Расценка с разрядами: 10000 → «10 000», 12.5 → «12,5»."""
    whole, _, frac = pricing.fmt_number(value).partition(",")
    return f"{int(whole):,}".replace(",", " ") + (f",{frac}" if frac else "")


def price_lines(order) -> list[tuple[str, str, float]]:
    """[(позиция, как посчитано, сумма в целых рублях)] — сумма строк ровно равна цене заказа.
    Ручная цена или сменившиеся расценки дают строку «Скидка» / «Корректировка цены»,
    иначе копеечное расхождение округления уходит в самую крупную строку."""
    s = db.get_settings()
    qty = order["qty"] or 1
    weight, hours = order["weight_g"] or 0, order["print_hours"] or 0
    defect = order["defect_percent"] or 0
    reverse = bool(order["reverse_engineering"])
    calc = pricing.calc_price(order["material"], weight, hours, qty, reverse, defect)
    per_kg = s["materials"].get(order["material"] or "", 0)
    cur = s["currency"]

    lines = []
    if calc["material_cost"]:
        lines.append(("Материал", f"{order['material']}: {pricing.fmt_number(weight)} г × {qty} шт × "
                                  f"{_rate(per_kg)} {cur}/кг", calc["material_cost"]))
    if calc["time_cost"]:
        lines.append(("Время печати", f"{pricing.fmt_number(hours)} ч × {qty} шт × "
                                      f"{_rate(s['hour_rate'])} {cur}/ч", calc["time_cost"]))
    if calc["defect_cost"]:
        lines.append((f"Брак {pricing.fmt_number(defect)}%", "запас на неудачную печать: "
                                                             f"{pricing.fmt_number(defect)}% от материала и времени",
                      calc["defect_cost"]))
    if calc["reverse_cost"]:
        lines.append(("Реверс-моделирование", "создание 3D-модели по образцу", calc["reverse_cost"]))

    total = round(order["price"] or 0)
    rounded = [(name, how, round(value)) for name, how, value in lines]
    diff = total - sum(v for _, _, v in rounded)
    if abs((order["price"] or 0) - calc["price"]) >= 1 or not rounded:
        if diff:
            rounded.append(("Скидка" if diff < 0 else "Корректировка цены", "итоговая цена согласована вручную", diff))
    elif diff:
        i = max(range(len(rounded)), key=lambda k: rounded[k][2])
        name, how, value = rounded[i]
        rounded[i] = (name, how, value + diff)
    return rounded


class _Doc(FPDF):
    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("mono", size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"{STUDIO} · документ сформирован {date.today().strftime('%d.%m.%Y')}", align="C")


def build_order_pdf(order_id: int, folder: Path | None = None) -> Path:
    """Собирает PDF по заказу и возвращает путь к файлу (перезаписывает прежний)."""
    order = db.get_order(order_id)
    if not order:
        raise ValueError(f"Заказа #{order_id} нет")
    qty = order["qty"] or 1

    pdf = _Doc(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_font("mono", "", str(FONTS_DIR / "JetBrainsMono-Regular.ttf"))
    pdf.add_font("mono", "B", str(FONTS_DIR / "JetBrainsMono-Medium.ttf"))
    pdf.add_page()
    width = pdf.epw

    # Шапка: студия, номер и дата заказа.
    pdf.set_fill_color(*ACCENT)
    pdf.rect(18, 18, 4, 17, style="F")
    pdf.set_x(26)
    pdf.set_font("mono", "B", 11)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, STUDIO.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(26)
    pdf.set_font("mono", "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(width / 2, 11, f"Заказ №{order['id']}")
    pdf.set_font("mono", size=10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 11, f"от {pricing.fmt_date(order['created_at'][:10])}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    _heading(pdf, "Детали заказа")
    weight = f"{pricing.fmt_number(order['weight_g'])} г" + (" за 1 шт" if qty > 1 else "")
    hours = pricing.fmt_hours(order["print_hours"]) + (" за 1 шт" if qty > 1 else "")
    defect = order["defect_percent"] or 0
    details = [
        ("Клиент", order["client"]),
        ("Контакт", order["contact"]),
        ("Описание", order["description"]),
        ("Материал", order["material"]),
        ("Цвет", order["color"]),
        ("Вес", weight if order["weight_g"] else ""),
        ("Время печати", hours if order["print_hours"] else ""),
        ("Количество", f"{qty} шт"),
        ("Брак", f"{pricing.fmt_number(defect)}% от стоимости печати" if defect else "не учитывается"),
        ("Срок", pricing.fmt_date(order["deadline"]) if order["deadline"] else "по договорённости"),
    ]
    for label, value in details:
        _detail_row(pdf, label, value or "—", width)
    pdf.ln(7)

    # Итоговая сумма — крупно, на жёлтой подложке.
    total = order["price"] or 0
    prepayment = order["prepayment"] or 0
    box_h = 22 if order["paid"] or prepayment else 16
    y = pdf.get_y()
    pdf.set_fill_color(*SOFT)
    pdf.set_draw_color(*ACCENT)
    pdf.rect(18, y, width, box_h, style="DF", round_corners=True, corner_radius=3)
    pdf.set_xy(24, y + 3)
    pdf.set_font("mono", "B", 11)
    pdf.set_text_color(*INK)
    pdf.cell(width / 2 - 6, 10, "Итого к оплате")
    pdf.set_font("mono", "B", 18)
    pdf.cell(width / 2 - 6, 10, _money(total), align="R", new_x="LMARGIN", new_y="NEXT")
    if order["paid"] or prepayment:
        pdf.set_x(24)
        pdf.set_font("mono", size=9)
        pdf.set_text_color(*MUTED)
        note = ("Оплачено полностью" if order["paid"] else
                f"Внесена предоплата {_money(prepayment)} · осталось оплатить {_money(pricing.remaining_to_pay(order))}")
        pdf.cell(width - 12, 6, note, align="R")
    pdf.set_y(y + box_h + 9)

    _heading(pdf, "Из чего складывается цена")
    lines = price_lines(order)
    for name, how, value in lines:
        _price_row(pdf, name, how, _money(value), width)
    pdf.set_draw_color(*INK)
    pdf.line(18, pdf.get_y() + 1, 18 + width, pdf.get_y() + 1)
    pdf.ln(3)
    pdf.set_font("mono", "B", 11)
    pdf.set_text_color(*INK)
    pdf.cell(width - 40, 8, "Итого")
    pdf.cell(40, 8, _money(total), align="R", new_x="LMARGIN", new_y="NEXT")

    folder = folder or PDF_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / file_name(order)
    pdf.output(str(path))
    return path


def _heading(pdf: FPDF, text: str) -> None:
    pdf.set_font("mono", "B", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, text.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _detail_row(pdf: FPDF, label: str, value: str, width: float) -> None:
    label_w = 42
    pdf.set_font("mono", size=9)
    pdf.set_text_color(*MUTED)
    pdf.cell(label_w, 7, label)
    pdf.set_font("mono", size=10)
    pdf.set_text_color(*INK)
    pdf.multi_cell(width - label_w, 7, str(value), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.line(18, pdf.get_y(), 18 + width, pdf.get_y())


def _price_row(pdf: FPDF, name: str, how: str, amount: str, width: float) -> None:
    amount_w = 40
    pdf.set_font("mono", "B", 10)
    pdf.set_text_color(*INK)
    pdf.cell(width - amount_w, 6, name)
    pdf.cell(amount_w, 6, amount, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("mono", size=8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(width - amount_w, 5, how, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.line(18, pdf.get_y() + 1, 18 + width, pdf.get_y() + 1)
    pdf.ln(3)


def open_file(path: Path) -> None:
    """Открывает PDF программой по умолчанию (Windows)."""
    if hasattr(os, "startfile"):
        os.startfile(str(path))


def notify_saved(page, path: Path, prefix: str = "PDF для клиента сохранён") -> None:
    """Сообщение внизу окна с кнопкой «Открыть»."""
    page.open(ft.SnackBar(ft.Text(f"{prefix}: «{PDF_DIR.name}» → {path.name}"), action="Открыть",
                          on_action=lambda e: open_file(path), duration=6000))
