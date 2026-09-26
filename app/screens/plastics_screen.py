"""Экран «Информация о пластике»: быстрый выбор под задачу, фильтры и карточки пластиков
с шкалами свойств и отметкой «в наличии» (по катушкам из калькулятора)."""
from typing import Callable

import flet as ft

import db
from app import plastics, theme

YES_WORDS = ("да", "обязательно")


def _grams(value: float) -> str:
    return f"{value:,.0f} г".replace(",", " ")


class PlasticsScreen(ft.Column):
    def __init__(self, on_add_spool: Callable[[str], None] | None = None):
        super().__init__(expand=True, spacing=theme.SPACING, scroll=ft.ScrollMode.AUTO)
        self.on_add_spool = on_add_spool
        self.need: dict | None = None
        self.group: str | None = None
        self.only_in_stock = False
        self.search_text = ""
        self.expanded: set[str] = set()

        self.header = ft.Container()
        self.need_chips = ft.Row(wrap=True, spacing=8, run_spacing=8)
        self.need_hint = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        self.group_chips = ft.Row(wrap=True, spacing=8, run_spacing=8)
        self.stock_switch = ft.Switch(label="Только в наличии", on_change=self._on_stock_toggle)
        self.search_field = ft.TextField(
            hint_text="Поиск: название, применение…", prefix_icon=ft.Icons.SEARCH, dense=True,
            border_radius=theme.FIELD_RADIUS, on_change=self._on_search, col={"xs": 12, "md": 5},
        )
        self.cards = theme.grid([])

        self.controls = [
            self.header,
            theme.section("Что нужно напечатать?", [self.need_chips, self.need_hint], icon=ft.Icons.LIGHTBULB_OUTLINE),
            theme.grid([
                ft.Container(self.group_chips, col={"xs": 12, "md": 7}),
                self.search_field,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.stock_switch,
            self.cards,
        ]
        self.refresh()

    # ---------- события ----------

    def _on_need(self, need: dict) -> None:
        self.need = None if self.need is need else need
        self.refresh()

    def _on_group(self, group: str | None) -> None:
        self.group = group
        self.refresh()

    def _on_stock_toggle(self, e: ft.ControlEvent) -> None:
        self.only_in_stock = bool(self.stock_switch.value)
        self.refresh()

    def _on_search(self, e: ft.ControlEvent) -> None:
        self.search_text = (self.search_field.value or "").strip().lower()
        self.refresh()

    def _toggle_details(self, name: str) -> None:
        self.expanded ^= {name}
        self.refresh()

    # ---------- отрисовка ----------

    def visible_plastics(self, stock: dict) -> list[dict]:
        """Пластики после фильтров; при выбранной задаче — только подходящие, в наличии — первыми."""
        items = plastics.PLASTICS
        if self.need:
            wanted = plastics.matching(self.need)
            items = sorted((p for p in items if p["name"] in wanted),
                           key=lambda p: (p["name"] not in stock, wanted.index(p["name"])))
        if self.group:
            items = [p for p in items if p["group"] == self.group]
        if self.only_in_stock:
            items = [p for p in items if p["name"] in stock]
        if self.search_text:
            items = [p for p in items if self.search_text in " ".join(str(v) for v in p.values()).lower()]
        return list(items)

    def refresh(self) -> None:
        stock = db.stock_by_plastic()
        in_stock = [n for n in plastics.names() if n in stock]
        self.header.content = theme.page_header(
            "Информация о пластике",
            f"{len(plastics.PLASTICS)} пластиков · в наличии {len(in_stock)}"
            + (f": {', '.join(in_stock)}" if 0 < len(in_stock) <= 4 else ""),
        )

        self.need_chips.controls = [
            ft.Chip(label=ft.Text(q["need"]), selected=q is self.need, show_checkmark=False,
                    on_select=lambda e, q=q: self._on_need(q))
            for q in plastics.QUICK_CHOICE
        ]
        if self.need:
            self.need_hint.visible = True
            self.need_hint.value = f"Подходят: {', '.join(self.need['materials'])} — {self.need['why'].lower()}."
        else:
            self.need_hint.visible = False

        self.group_chips.controls = [
            ft.Chip(label=ft.Text(label), selected=self.group == value, show_checkmark=False,
                    on_select=lambda e, v=value: self._on_group(v))
            for value, label in [(None, "Все")] + [(g, g) for g in plastics.GROUPS]
        ]

        items = self.visible_plastics(stock)
        self.cards.controls = [self._card(p, stock.get(p["name"])) for p in items] or [
            theme.empty_state("Ничего не подходит под фильтры.", ft.Icons.SEARCH_OFF)
        ]
        if self.page:
            self.update()

    def _card(self, p: dict, stock_entry: dict | None) -> ft.Control:
        if stock_entry:
            stock_pill = theme.pill(f"есть {_grams(stock_entry['remaining_g'])}", theme.OK, ft.Icons.CHECK_CIRCLE)
        else:
            stock_pill = theme.pill("нет в наличии", ft.Colors.OUTLINE, ft.Icons.REMOVE_CIRCLE_OUTLINE)

        drying_color = theme.WARN if p["drying"].lower() in YES_WORDS else theme.IDLE
        nozzle_color = theme.ERR if p["hardened_nozzle"].lower() == "да" else theme.IDLE
        badges = ft.Row([
            theme.pill(f"Печать: {p['difficulty'].lower()}", ft.Colors.PRIMARY, ft.Icons.PRECISION_MANUFACTURING),
            theme.pill(f"Сушка: {p['drying'].lower()}", drying_color, ft.Icons.AIR),
            theme.pill("Закалённое сопло" if p["hardened_nozzle"].lower() == "да" else "Обычное сопло",
                       nozzle_color, ft.Icons.HARDWARE),
        ], wrap=True, spacing=6, run_spacing=6)

        bars = [self._rating(label, p[key]) for key, label in plastics.RATED_FIELDS]
        expanded = p["name"] in self.expanded
        details = [
            self._detail("Плюсы", p["pros"], ft.Icons.ADD_CIRCLE_OUTLINE, theme.OK),
            self._detail("Минусы", p["cons"], ft.Icons.REMOVE_CIRCLE_OUTLINE, theme.ERR),
            self._detail("Лучшее применение", p["best_use"], ft.Icons.STAR_OUTLINE, ft.Colors.PRIMARY),
            self._detail("Когда выбирать", p["when"], ft.Icons.CHECK, ft.Colors.PRIMARY),
            self._detail("Сильная / слабая сторона", f"{p['strong']} / {p['weak']}", ft.Icons.BALANCE,
                         ft.Colors.ON_SURFACE_VARIANT),
        ] if expanded else []

        actions = [ft.TextButton("Скрыть" if expanded else "Подробнее",
                                 icon=ft.Icons.EXPAND_LESS if expanded else ft.Icons.EXPAND_MORE,
                                 on_click=lambda e, n=p["name"]: self._toggle_details(n))]
        if self.on_add_spool:
            actions.append(ft.OutlinedButton("Катушка", icon=ft.Icons.ADD,
                                             on_click=lambda e, n=p["name"]: self.on_add_spool(n)))

        return theme.card(ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(p["name"], size=17, weight=ft.FontWeight.W_700),
                    ft.Text(f"{p['category']} · {p['purpose']}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=2, tight=True, expand=True),
                stock_pill,
            ], vertical_alignment=ft.CrossAxisAlignment.START),
            *bars,
            badges,
            ft.Text(p["best_use"], size=13, italic=True, color=ft.Colors.ON_SURFACE_VARIANT) if not expanded else ft.Container(),
            *details,
            ft.Row(actions, alignment=ft.MainAxisAlignment.END, spacing=8),
        ], spacing=8), col={"xs": 12, "md": 6, "xl": 4})

    def _rating(self, label: str, text: str) -> ft.Control:
        value = plastics.level(text)
        return ft.Row([
            ft.Text(label, size=12, width=110, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Container(ft.ProgressBar(value=value / 5, bar_height=6, border_radius=3), expand=True),
            ft.Text(text, size=12, width=120, text_align=ft.TextAlign.RIGHT,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=text),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _detail(self, label: str, text: str, icon, color) -> ft.Control:
        return ft.Row([
            ft.Icon(icon, size=16, color=color),
            ft.Column([ft.Text(label, size=12, weight=ft.FontWeight.W_600),
                       ft.Text(text, size=13)], spacing=0, tight=True, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.START, spacing=8)
