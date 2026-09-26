"""Экран «Статистика»: дашборд из виджетов, которые можно переставлять мышью.

Как в Draggable Widget Grid: виджеты разного размера (обычный и широкий), перетаскивание
с «подъёмом» и глубокой тенью, подсветка места, куда упадёт виджет, и рамка на месте
приземления. Без мыши — меню у ручки ⋮⋮ («Сдвинуть влево/вправо»). Порядок сохраняется
в настройках (stats_layout)."""
import threading
from datetime import date, timedelta

import flet as ft

import db
import pricing
from app import theme

# id → (подпись, размер). «wide» занимает две колонки из четырёх.
WIDGETS = {
    "activity": ("Заказы по дням", "wide"),
    "money": ("Получено", "sm"),
    "profit": ("Прибыль", "sm"),
    "debt": ("Ждём доплату", "sm"),
    "deadlines": ("Сроки", "sm"),
    "statuses": ("Статусы заказов", "wide"),
    "plastic": ("Расход пластика", "wide"),
    "stock": ("Склад пластика", "sm"),
    "average": ("Средний заказ", "sm"),
}
DEFAULT_ORDER = list(WIDGETS)

COLS = {"sm": {"xs": 12, "sm": 6, "lg": 3}, "wide": {"xs": 12, "lg": 6}}
FEEDBACK_WIDTH = {"sm": 280, "wide": 570}
TILE_HEIGHT = 252
LANDED_MS = 620
HEAT_WEEKS = 16
WEEKDAYS = ["пн", "", "ср", "", "пт", "", ""]
MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

# Уровни теплокарты: пусто → самый загруженный день.
HEAT = [
    ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
    ft.Colors.with_opacity(0.22, theme.DATA),
    ft.Colors.with_opacity(0.4, theme.DATA),
    ft.Colors.with_opacity(0.62, theme.DATA),
    ft.Colors.with_opacity(0.9, theme.DATA),
]


def load_order() -> list[str]:
    """Сохранённый порядок виджетов: неизвестные id выкидываются, новые виджеты — в конец."""
    saved = [w for w in db.get_settings().get("stats_layout", []) if w in WIDGETS]
    return saved + [w for w in DEFAULT_ORDER if w not in saved]


def move(order: list[str], widget_id: str, target_id: str) -> list[str]:
    """Ставит widget_id на место target_id (остальные сдвигаются), как при перетаскивании."""
    if widget_id == target_id or widget_id not in order or target_id not in order:
        return order
    result = [w for w in order if w != widget_id]
    to = order.index(target_id)
    result.insert(to, widget_id)
    return result


def shift(order: list[str], widget_id: str, delta: int) -> list[str]:
    i = order.index(widget_id)
    j = max(0, min(len(order) - 1, i + delta))
    return move(order, widget_id, order[j]) if j != i else order


class StatsScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING, scroll=ft.ScrollMode.AUTO)
        self.order = load_order()
        self.landed: str | None = None
        self.hover_target: str | None = None
        self.header = ft.Container()
        self.board = theme.grid([], spacing=theme.SPACING, run_spacing=theme.SPACING)
        self.hint = ft.Text("Перетащите виджет мышью, чтобы поменять раскладку. Без мыши — меню у ⋮⋮.",
                            size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.controls = [self.header, self.hint, self.board]
        self._data: dict = {}
        self.refresh()

    # ---------- жизненный цикл ----------

    def did_mount(self) -> None:
        # Появление лесенкой при каждом открытии экрана.
        tiles = list(self.board.controls)
        theme.appear(tiles)
        self.update()

        def show() -> None:
            theme.show_appeared(tiles)
            if self.page:
                self.update()

        threading.Timer(0.06, show).start()

    def refresh(self) -> None:
        self._data = self._collect()
        s = self._data["stats"]
        self.header.content = theme.page_header(
            "Статистика",
            f"В этом месяце: {s['month_orders']} заказов, получено {pricing.money(s['month_revenue'])}",
            [ft.TextButton("Сбросить раскладку", icon=ft.Icons.RESTART_ALT, on_click=self._reset_layout)],
        )
        self._render()
        if self.page:
            self.update()

    def _collect(self) -> dict:
        return {
            "stats": db.stats(),
            "per_day": db.orders_per_day(HEAT_WEEKS * 7 + 7),
            "per_month": db.money_per_month(6),
            "orders": db.list_orders("all", limit=100000),
            "stock": db.stock_by_plastic(),
        }

    # ---------- раскладка и перетаскивание ----------

    def _render(self) -> None:
        self.board.controls = [self._slot(w) for w in self.order]

    def _slot(self, widget_id: str) -> ft.Control:
        title, size = WIDGETS[widget_id]
        tile = self._tile(widget_id)
        placeholder = ft.Container(
            height=TILE_HEIGHT, border_radius=theme.CARD_RADIUS,
            border=ft.border.all(1.5, ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
        )
        feedback = ft.Container(
            self._tile(widget_id, lifted=True), width=FEEDBACK_WIDTH[size], height=TILE_HEIGHT,
            scale=1.04, opacity=0.97, rotate=ft.Rotate(-0.012),
        )
        draggable = ft.Draggable(group="stats-widgets", content=tile, content_when_dragging=placeholder,
                                 content_feedback=feedback, data=widget_id)
        target = ft.DragTarget(
            group="stats-widgets", content=draggable, data=widget_id,
            on_will_accept=lambda e, wid=widget_id: self._on_will_accept(e, wid),
            on_leave=lambda e, wid=widget_id: self._on_leave(wid),
            on_accept=lambda e, wid=widget_id: self._on_accept(e, wid),
        )
        return ft.Container(target, col=COLS[size], key=widget_id)

    def _on_will_accept(self, e: ft.ControlEvent, target_id: str) -> None:
        if e.data == "true":
            self._set_highlight(target_id)

    def _on_leave(self, target_id: str) -> None:
        if self.hover_target == target_id:
            self._set_highlight(None)

    def _set_highlight(self, target_id: str | None) -> None:
        self.hover_target = target_id
        for slot in self.board.controls:
            wid = slot.key
            tile = slot.content.content.content  # Container → DragTarget → Draggable → карточка
            tile.border = self._tile_border(wid)
        if self.page:
            self.board.update()

    def _on_accept(self, e: ft.DragTargetEvent, target_id: str) -> None:
        src = self.page.get_control(e.src_id) if self.page else None
        widget_id = getattr(src, "data", None)
        self.hover_target = None
        if widget_id:
            self._apply_order(move(self.order, widget_id, target_id), landed=widget_id)

    def _apply_order(self, order: list[str], landed: str | None = None) -> None:
        self.order = order
        db.set_setting("stats_layout", order)
        self.landed = landed
        self._render()
        if self.page:
            self.update()
        if landed:
            def clear() -> None:
                if self.landed == landed:
                    self.landed = None
                    self._set_highlight(None)
            threading.Timer(LANDED_MS / 1000, clear).start()

    def _reset_layout(self, e: ft.ControlEvent) -> None:
        self._apply_order(list(DEFAULT_ORDER))

    def _tile_border(self, widget_id: str) -> ft.Border:
        if widget_id == self.hover_target:
            return ft.border.all(2, ft.Colors.with_opacity(0.45, theme.DATA))
        if widget_id == self.landed:
            return ft.border.all(2, ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE))
        return ft.border.all(1, ft.Colors.OUTLINE_VARIANT)

    # ---------- виджет-обёртка ----------

    def _tile(self, widget_id: str, lifted: bool = False) -> ft.Container:
        title, _ = WIDGETS[widget_id]
        meta, body = getattr(self, f"_w_{widget_id}")()
        menu = ft.PopupMenuButton(
            icon=ft.Icons.DRAG_INDICATOR, icon_size=16, icon_color=ft.Colors.ON_SURFACE_VARIANT,
            tooltip="Переместить виджет", menu_position=ft.PopupMenuPosition.UNDER,
            items=[
                ft.PopupMenuItem(text="Сдвинуть влево", icon=ft.Icons.ARROW_BACK,
                                 on_click=lambda e: self._apply_order(shift(self.order, widget_id, -1), widget_id)),
                ft.PopupMenuItem(text="Сдвинуть вправо", icon=ft.Icons.ARROW_FORWARD,
                                 on_click=lambda e: self._apply_order(shift(self.order, widget_id, 1), widget_id)),
                ft.PopupMenuItem(text="В начало", icon=ft.Icons.FIRST_PAGE,
                                 on_click=lambda e: self._apply_order(move(self.order, widget_id, self.order[0]),
                                                                      widget_id)),
            ],
        )
        head = ft.Row([ft.Container(theme.eyebrow(title), expand=True)]
                      + ([meta] if meta is not None else []) + [menu],
                      spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER, height=24)
        content = ft.Column([head, *body], spacing=10, expand=True)
        if lifted:
            return ft.Container(content, padding=ft.padding.only(left=20, right=8, top=14, bottom=18),
                                border_radius=theme.CARD_RADIUS, bgcolor=ft.Colors.SURFACE,
                                border=ft.border.all(1, ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)),
                                shadow=theme.SHADOW_LIFTED, height=TILE_HEIGHT)
        return theme.card(content, hover="lift", height=TILE_HEIGHT,
                          padding=ft.padding.only(left=20, right=8, top=14, bottom=18),
                          border=self._tile_border(widget_id))

    @staticmethod
    def _muted(text: str, size: int = 12) -> ft.Text:
        return ft.Text(text, size=size, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1,
                       overflow=ft.TextOverflow.ELLIPSIS)

    @staticmethod
    def _row(lead: list[ft.Control], value: str, strong: bool = False) -> ft.Row:
        """Строка «подпись … значение» в одну тихую линию."""
        return ft.Row([
            ft.Row(lead, spacing=8, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(value, size=12, color=ft.Colors.ON_SURFACE if strong else ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _label(self, text: str, strong: bool = False) -> ft.Text:
        return ft.Text(text, size=12, color=ft.Colors.ON_SURFACE if strong else ft.Colors.ON_SURFACE_VARIANT,
                       max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)

    @staticmethod
    def _spacer() -> ft.Container:
        return ft.Container(expand=True)

    # ---------- сами виджеты: каждый возвращает (meta справа от заголовка, тело) ----------

    def _w_activity(self):
        per_day = self._data["per_day"]
        today = date.today()
        start = today - timedelta(days=today.weekday() + 7 * (HEAT_WEEKS - 1))
        peak = max(per_day.values(), default=0)
        month_key = today.strftime("%Y-%m")
        prev = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        this_month = sum(n for d, n in per_day.items() if d.startswith(month_key))
        prev_month = sum(n for d, n in per_day.items() if d.startswith(prev))

        rows = []
        for wd in range(7):
            cells = []
            for week in range(HEAT_WEEKS):
                day = start + timedelta(days=week * 7 + wd)
                if day > today:
                    cells.append(ft.Container(expand=1, height=11))
                    continue
                n = per_day.get(day.isoformat(), 0)
                level = 0 if not n else max(1, -(-n * 4 // max(peak, 1)))
                # Цвет — только по числу заказов; «сегодня» отмечено рамкой, а не заливкой,
                # иначе пустой сегодняшний день не отличить от самого загруженного.
                cells.append(ft.Container(
                    expand=1, height=11, border_radius=3, bgcolor=HEAT[min(level, 4)],
                    border=ft.border.all(1.5, ft.Colors.ON_SURFACE) if day == today else None,
                    tooltip=f"{'сегодня' if day == today else day.strftime('%d.%m')} · {n} зак.",
                ))
            rows.append(ft.Row([ft.Text(WEEKDAYS[wd], size=9, width=18, color=ft.Colors.ON_SURFACE_VARIANT), *cells],
                               spacing=3))
        legend = ft.Row(
            [self._muted("меньше", 10), *[ft.Container(width=10, height=10, border_radius=3, bgcolor=c) for c in HEAT],
             self._muted("больше", 10)],
            spacing=3, alignment=ft.MainAxisAlignment.END,
        )
        meta = (theme.delta_text((this_month - prev_month) / prev_month * 100, suffix="к прошл. мес.")
                if prev_month else self._muted(f"{HEAT_WEEKS} нед."))
        body = [
            theme.big_number(str(this_month), "в этом месяце"),
            self._spacer(),
            ft.Column(rows, spacing=3),
            legend,
        ]
        return meta, body

    def _w_money(self):
        s = self._data["stats"]
        months = self._data["per_month"]
        peak = max((v for _, v in months), default=0) or 1
        bars = []
        for i, (ym, value) in enumerate(months):
            last = i == len(months) - 1
            bars.append(ft.Container(
                expand=1, height=max(4, 44 * value / peak), border_radius=6,
                bgcolor=theme.DATA if last else ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
                tooltip=f"{MONTHS[int(ym[5:]) - 1]} {ym[:4]}: {pricing.money(value)}",
                animate_size=ft.animation.Animation(600, ft.AnimationCurve.EASE_OUT_CUBIC),
            ))
        labels = ft.Row([ft.Text(MONTHS[int(ym[5:]) - 1], size=9, expand=1, text_align=ft.TextAlign.CENTER,
                                 color=ft.Colors.ON_SURFACE_VARIANT) for ym, _ in months], spacing=4)
        body = [
            theme.big_number(pricing.money(s["revenue"])),
            self._muted("оплаты + предоплаты"),
            self._spacer(),
            ft.Row(bars, spacing=4, height=44, vertical_alignment=ft.CrossAxisAlignment.END),
            labels,
        ]
        return self._muted("6 мес."), body

    def _w_profit(self):
        s = self._data["stats"]
        paid_revenue = s["profit"] + s["expense"]
        margin = s["profit"] / paid_revenue * 100 if paid_revenue else 0
        body = [
            theme.big_number(pricing.money(s["profit"]), color=theme.OK if s["profit"] > 0 else None),
            self._muted(f"маржа {margin:.0f}%"),
            self._spacer(),
            self._row([self._label("оплачено", True)], pricing.money(paid_revenue), strong=True),
            self._row([self._label("пластик по закупке")], f"−{pricing.money(s['expense'])}"),
            theme.thin_bar(margin / 100, theme.OK),
        ]
        return None, body

    def _w_debt(self):
        s = self._data["stats"]
        unpaid = [o for o in self._data["orders"] if not o["paid"] and o["status"] != "cancelled"]
        with_prepay = sum(1 for o in unpaid if o["prepayment"])
        body = [
            theme.big_number(pricing.money(s["unpaid"]), color=theme.ERR if s["unpaid"] else None),
            self._muted("за вычетом предоплат"),
            self._spacer(),
            self._row([theme.dot(theme.WARN), self._label("предоплаты", True)], pricing.money(s["prepaid"]), True),
            self._row([theme.dot(theme.ERR), self._label("не оплачено")], f"{len(unpaid)} зак."),
            self._row([theme.dot(theme.IDLE), self._label("из них с предоплатой")], f"{with_prepay} зак."),
        ]
        return None, body

    def _w_deadlines(self):
        today = date.today()
        active = [o for o in self._data["orders"] if o["status"] in db.ACTIVE_STATUSES]
        overdue = soon = later = none = 0
        for o in active:
            if not o["deadline"]:
                none += 1
                continue
            days = (date.fromisoformat(o["deadline"]) - today).days
            if days < 0:
                overdue += 1
            elif days <= 1:
                soon += 1
            else:
                later += 1
        meta = ft.Row([theme.dot(theme.ERR if overdue else theme.OK),
                       self._muted("есть просрочка" if overdue else "всё в срок")], spacing=6, tight=True)
        body = [
            theme.big_number(str(len(active)), "в работе"),
            self._spacer(),
            self._row([theme.dot(theme.ERR), self._label("просрочено", bool(overdue))], str(overdue), bool(overdue)),
            self._row([theme.dot(theme.WARN), self._label("сегодня / завтра")], str(soon)),
            self._row([theme.dot(theme.OK), self._label("позже")], str(later)),
            self._row([theme.dot(theme.IDLE), self._label("без срока")], str(none)),
        ]
        return meta, body

    def _w_statuses(self):
        by_status = self._data["stats"]["by_status"]
        total = sum(by_status.values())
        codes = sorted((c for c in db.STATUSES if by_status.get(c)), key=lambda c: -by_status[c])
        peak = max((by_status[c] for c in codes), default=1)
        rows = []
        for i, code in enumerate(codes[:5]):
            label, color = theme.status_style(code)
            rows.append(ft.Row([
                theme.dot(color),
                ft.Text(label, size=12, width=130, color=ft.Colors.ON_SURFACE if i == 0 else ft.Colors.ON_SURFACE_VARIANT),
                ft.Container(theme.thin_bar(by_status[code] / peak, theme.DATA if i == 0 else None), expand=True),
                ft.Text(str(by_status[code]), size=12, width=36, text_align=ft.TextAlign.RIGHT,
                        color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        body = [theme.big_number(str(total), "заказов всего"), self._spacer(),
                *(rows or [self._muted("Заказов пока нет.")])]
        return self._muted("всё время"), body

    def _w_plastic(self):
        materials = self._data["stats"]["materials"]
        grams = self._data["stats"]["grams"] or 0
        swatches = [theme.DATA, ft.Colors.with_opacity(0.55, theme.DATA), ft.Colors.with_opacity(0.3, theme.DATA),
                    ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)]
        top = materials[:3]
        rest = sum(g for _, g in materials[3:])
        parts = [(name or "—", g) for name, g in top] + ([("другие", rest)] if rest else [])
        items = [
            ft.Container(self._row([theme.dot(swatches[i], 6), self._label(name, i == 0)],
                                   f"{g / grams:.0%}" if grams else "0%"), col=6)
            for i, (name, g) in enumerate(parts)
        ]
        segments = ft.Row([
            ft.Container(expand=max(1, round(g / grams * 100)) if grams else 1, height=3, border_radius=3,
                         bgcolor=swatches[i], tooltip=f"{name}: {g / 1000:.2f} кг")
            for i, (name, g) in enumerate(parts)
        ], spacing=3)
        body = [theme.big_number(f"{grams / 1000:.2f}", "кг напечатано"), self._spacer(),
                ft.ResponsiveRow(items, spacing=24, run_spacing=6) if items else self._muted("Пока ничего не напечатано."),
                segments if parts else ft.Container()]
        return self._muted("по материалам"), body

    def _w_stock(self):
        stock = self._data["stock"]
        total = sum(v["remaining_g"] for v in stock.values())
        rows = [
            self._row([theme.dot(theme.ERR if v["remaining_g"] < 200 else theme.OK), self._label(name, i == 0)],
                      f"{v['remaining_g'] / 1000:.2f} кг", i == 0)
            for i, (name, v) in enumerate(sorted(stock.items(), key=lambda kv: -kv[1]["remaining_g"])[:3])
        ]
        body = [theme.big_number(f"{total / 1000:.2f}", "кг"), self._spacer(),
                *(rows or [self._muted("Катушек нет — добавьте в «Калькуляторе пластика».")])]
        return self._muted(f"{sum(v['spools'] for v in stock.values())} кат."), body

    def _w_average(self):
        orders = [o for o in self._data["orders"] if o["status"] != "cancelled"]
        n = len(orders) or 1
        avg_price = sum(o["price"] or 0 for o in orders) / n
        avg_profit = sum((o["price"] or 0) - (o["cost"] or 0) for o in orders) / n
        avg_weight = sum((o["weight_g"] or 0) * (o["qty"] or 1) for o in orders) / n
        avg_hours = sum((o["print_hours"] or 0) * (o["qty"] or 1) for o in orders) / n
        body = [
            theme.big_number(pricing.money(avg_price)),
            self._muted("средний чек"),
            self._spacer(),
            self._row([self._label("прибыль", True)], pricing.money(avg_profit), True),
            self._row([self._label("пластик")], f"{avg_weight:.0f} г"),
            self._row([self._label("печать")], pricing.fmt_hours(avg_hours)),
        ]
        return None, body
