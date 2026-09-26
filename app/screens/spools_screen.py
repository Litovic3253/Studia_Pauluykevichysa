"""Экран «Калькулятор пластика»: катушки, сколько загружено / потрачено / осталось,
списание и сверка остатка, история списаний."""
import flet as ft

import db
import pricing
from app import plastics, theme
from app.dialogs import grams_dialog

LOW_STOCK_G = 100  # меньше — катушка «заканчивается»


def grams(value: float) -> str:
    return f"{value:,.0f} г".replace(",", " ")


class SpoolsScreen(ft.Column):
    def __init__(self):
        super().__init__(expand=True, spacing=theme.SPACING, scroll=ft.ScrollMode.AUTO)
        self.show_archive = False

        self.header = ft.Container()
        self.kpi_grid = theme.grid([])
        self.spools_column = ft.Column(spacing=10)
        self.by_plastic_column = ft.Column(spacing=10)
        self.history_column = ft.Column(spacing=4)
        self.archive_switch = ft.Switch(label="Показать архив", on_change=self._on_archive_toggle)

        self.plastic_dd = theme.dropdown("Пластик", width=260,
                                         options=[ft.dropdown.Option(n) for n in plastics.names()])
        self.color_field = theme.field("Цвет", {"xs": 12, "sm": 6}, hint_text="белый, чёрный…")
        self.weight_field = theme.field("Вес пластика", {"xs": 12, "sm": 6}, value="1000", suffix_text="г",
                                        helper_text="Без веса пустой катушки")
        self.add_error = ft.Text("", color=theme.ERR, visible=False)

        spools = theme.section("Катушки", [self.archive_switch, self.spools_column],
                               icon=ft.Icons.ALBUM_OUTLINED)
        add = theme.section("Добавить катушку", [
            self.plastic_dd,
            theme.grid([self.color_field, self.weight_field]),
            self.add_error,
            ft.FilledButton("Загрузить катушку", icon=ft.Icons.ADD, on_click=self._on_add),
        ], icon=ft.Icons.ADD_CIRCLE_OUTLINE)

        self.controls = [
            self.header,
            self.kpi_grid,
            theme.grid([
                ft.Column([spools], col={"xs": 12, "lg": 7}),
                ft.Column([
                    add,
                    theme.section("Остаток по пластикам", [self.by_plastic_column], icon=ft.Icons.INVENTORY_2_OUTLINED),
                    theme.section("История списаний", [self.history_column], icon=ft.Icons.HISTORY),
                ], spacing=theme.SPACING, col={"xs": 12, "lg": 5}),
            ]),
        ]
        self.refresh()

    def preselect(self, plastic: str) -> None:
        """Открыть форму добавления с уже выбранным пластиком (кнопка «Катушка» на вкладке информации)."""
        self.plastic_dd.value = plastic
        if self.page:
            self.update()

    # ---------- отрисовка ----------

    def refresh(self) -> None:
        totals = db.spool_totals()
        stock = db.stock_by_plastic()
        self.header.content = theme.page_header(
            "Калькулятор пластика",
            f"В наличии {len(stock)} видов пластика · осталось {grams(totals['remaining_g'])}",
        )
        self.kpi_grid.controls = [
            self._kpi("Загружено", grams(totals["loaded_g"]), ft.Icons.DOWNLOAD, theme.DATA),
            self._kpi("Осталось", grams(totals["remaining_g"]), ft.Icons.INVENTORY_2_OUTLINED, theme.OK),
            self._kpi("Израсходовано", grams(totals["used_g"]), ft.Icons.LOCAL_FIRE_DEPARTMENT_OUTLINED,
                      theme.WARN),
            self._kpi("Катушек", str(totals["spools"]), ft.Icons.ALBUM_OUTLINED, theme.VIOLET),
        ]

        spools = db.list_spools(include_archived=self.show_archive)
        self.spools_column.controls = [self._spool_row(s) for s in spools] or [
            theme.empty_state("Катушек пока нет — добавьте первую справа.", ft.Icons.ALBUM_OUTLINED)
        ]

        biggest = max((v["remaining_g"] for v in stock.values()), default=0)
        self.by_plastic_column.controls = [
            ft.Column([
                ft.Row([ft.Text(name, expand=True, weight=ft.FontWeight.W_600),
                        ft.Text(f"{grams(v['remaining_g'])} · {v['spools']} кат.", size=13)]),
                ft.ProgressBar(value=v["remaining_g"] / biggest if biggest else 0, bar_height=8, border_radius=4),
            ], spacing=4)
            for name, v in sorted(stock.items(), key=lambda kv: -kv[1]["remaining_g"])
        ] or [ft.Text("Пластика нет.", color=ft.Colors.ON_SURFACE_VARIANT)]

        usage = db.list_usage(15)
        self.history_column.controls = [self._usage_row(u) for u in usage] or [
            ft.Text("Списаний пока не было.", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        ]
        if self.page:
            self.update()

    def _kpi(self, label: str, value: str, icon, color) -> ft.Control:
        return theme.card(ft.Row([
            ft.Container(ft.Icon(icon, color=color), padding=10, border_radius=12,
                         bgcolor=ft.Colors.with_opacity(0.12, color)),
            ft.Column([ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                       ft.Text(value, size=20, weight=ft.FontWeight.W_700)], spacing=2, tight=True, expand=True),
        ], spacing=12), col={"xs": 12, "sm": 6, "xl": 3})

    def _spool_row(self, s) -> ft.Control:
        remaining = max(s["remaining_g"], 0)
        share = remaining / s["initial_g"] if s["initial_g"] else 0
        low = remaining < LOW_STOCK_G
        title = s["plastic"] + (f" · {s['color']}" if s["color"] else "")
        pills = []
        if s["archived"]:
            pills.append(theme.pill("в архиве", ft.Colors.OUTLINE))
        elif remaining <= 0:
            pills.append(theme.pill("пустая", theme.ERR, ft.Icons.ERROR_OUTLINE))
        elif low:
            pills.append(theme.pill("заканчивается", theme.WARN, ft.Icons.WARNING_AMBER))

        if s["archived"]:
            actions = [
                ft.TextButton("Вернуть", icon=ft.Icons.UNARCHIVE_OUTLINED,
                              on_click=lambda e, sid=s["id"]: self._archive(sid, False)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip=theme.tip("Удалить навсегда"),
                              on_click=lambda e, sid=s["id"]: self._confirm_delete(sid, title)),
            ]
        else:
            actions = [
                ft.FilledTonalButton("Списать", icon=ft.Icons.REMOVE, on_click=lambda e, sp=s: self._ask_use(sp)),
                ft.TextButton("Сверить", icon=ft.Icons.SCALE_OUTLINED, on_click=lambda e, sp=s: self._ask_weigh(sp)),
                ft.IconButton(ft.Icons.ARCHIVE_OUTLINED, tooltip=theme.tip("В архив (катушка закончилась)"),
                              on_click=lambda e, sid=s["id"]: self._archive(sid, True)),
            ]
        color = theme.ERR if remaining <= 0 else theme.WARN if low else theme.OK
        return ft.Container(ft.Column([
            ft.Row([ft.Text(title, weight=ft.FontWeight.W_600, expand=True), *pills]),
            ft.Row([ft.Text(f"осталось {grams(remaining)} из {grams(s['initial_g'])}", size=13, expand=True),
                    ft.Text(f"{share:.0%}", size=12, color=ft.Colors.ON_SURFACE_VARIANT)]),
            ft.ProgressBar(value=share, color=color, bgcolor=ft.Colors.with_opacity(0.12, color),
                           bar_height=8, border_radius=4),
            ft.Row(actions, alignment=ft.MainAxisAlignment.END, wrap=True, spacing=4),
        ], spacing=6), padding=12, border_radius=12, bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.SURFACE_CONTAINER_HIGHEST),
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT))

    def _usage_row(self, u) -> ft.Control:
        what = u["plastic"] + (f" · {u['color']}" if u["color"] else "")
        reason = f"заказ #{u['order_id']}" if u["order_id"] else (u["note"] or "вручную")
        sign = "−" if u["grams"] >= 0 else "+"
        return ft.Row([
            ft.Text(pricing.fmt_date(u["created_at"][:10]), size=12, width=80, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Column([ft.Text(what, size=13), ft.Text(reason, size=11, color=ft.Colors.ON_SURFACE_VARIANT)],
                      spacing=0, tight=True, expand=True),
            ft.Text(f"{sign}{grams(abs(u['grams']))}", weight=ft.FontWeight.W_600),
            ft.IconButton(ft.Icons.UNDO, tooltip=theme.tip("Отменить списание (вернуть граммы на катушку)"),
                          on_click=lambda e, uid=u["id"]: self._undo(uid)),
        ], spacing=8)

    # ---------- действия ----------

    def _on_archive_toggle(self, e: ft.ControlEvent) -> None:
        self.show_archive = bool(self.archive_switch.value)
        self.refresh()

    def _on_add(self, e: ft.ControlEvent) -> None:
        weight = pricing.parse_weight(self.weight_field.value)
        if not self.plastic_dd.value or not weight:
            self.add_error.value = "Выберите пластик и укажите вес больше нуля."
            self.add_error.visible = True
            self.update()
            return
        db.add_spool(self.plastic_dd.value, self.color_field.value, weight)
        self.add_error.visible = False
        self.color_field.value = ""
        self.weight_field.value = "1000"
        self.refresh()

    def _archive(self, spool_id: int, archived: bool) -> None:
        db.archive_spool(spool_id, archived)
        self.refresh()

    def _undo(self, usage_id: int) -> None:
        db.undo_usage(usage_id)
        self.refresh()

    def _ask_use(self, spool) -> None:
        def ok(value: float) -> None:
            db.use_spool(spool["id"], value, note="вручную")
            self.refresh()
        grams_dialog(self.page, f"Списать с {spool['plastic']}", "Сколько граммов списать", "", ok)

    def _ask_weigh(self, spool) -> None:
        def ok(value: float) -> None:
            db.set_spool_remaining(spool["id"], value)
            self.refresh()
        grams_dialog(self.page, f"Сверить остаток: {spool['plastic']}", "Сколько пластика осталось на самом деле",
                     pricing.fmt_number(max(spool["remaining_g"], 0)), ok,
                     helper="Взвесьте катушку и вычтите вес пустой катушки", allow_zero=True)

    def _confirm_delete(self, spool_id: int, title: str) -> None:
        def confirm(e: ft.ControlEvent) -> None:
            self.page.close(dialog)
            db.delete_spool(spool_id)
            self.refresh()
        dialog = ft.AlertDialog(
            title=ft.Text(f"Удалить катушку «{title}»?"),
            content=ft.Text("Вместе с ней удалится история её списаний."),
            actions=[ft.TextButton("Отмена", on_click=lambda e: self.page.close(dialog)),
                     ft.TextButton("Удалить", on_click=confirm, style=ft.ButtonStyle(color=theme.ERR))],
        )
        self.page.open(dialog)

