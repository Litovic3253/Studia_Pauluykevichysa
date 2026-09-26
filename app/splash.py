"""Экран загрузки: логотип-кубик переворачивается, за ним пульсирует ореол, внизу —
полоска и проценты. Проценты догоняют реальные шаги запуска плавно, по 1% за тик,
поэтому даже быстрый запуск успевает показать анимацию, а не мелькнуть."""
import math
import threading
import time

import flet as ft

from app import theme

TICK = 0.018          # секунд на 1% — полный путь 0→100% не быстрее ~1,8 с
FLIP_EVERY = 0.75     # секунд между переворотами кубика
LOGO_SIZE = 88


class Splash(ft.Container):
    def __init__(self, title: str, subtitle: str):
        self.target = 0
        self.shown = 0
        self._running = False
        self._lock = threading.Lock()
        self._steps: list[tuple[int, str]] = []  # (до какого %, подпись) — подпись идёт вместе с процентами

        self.halo = ft.Container(
            width=LOGO_SIZE, height=LOGO_SIZE, border_radius=LOGO_SIZE,
            bgcolor=ft.Colors.PRIMARY, opacity=0.25, scale=1,
            animate_scale=ft.animation.Animation(700, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.animation.Animation(700, ft.AnimationCurve.EASE_OUT),
        )
        self.logo = ft.Container(
            ft.Icon(ft.Icons.VIEW_IN_AR, color=ft.Colors.ON_PRIMARY, size=44),
            width=LOGO_SIZE, height=LOGO_SIZE, border_radius=26, bgcolor=ft.Colors.PRIMARY,
            alignment=ft.alignment.center, rotate=ft.Rotate(0), scale=1,
            animate_rotation=ft.animation.Animation(650, ft.AnimationCurve.EASE_IN_OUT_BACK),
            animate_scale=ft.animation.Animation(325, ft.AnimationCurve.EASE_OUT),
            shadow=theme.SHADOW_HOVER,
        )
        self.bar = theme.thin_bar(0, color=ft.Colors.PRIMARY, height=4)
        self.percent = ft.Text("0%", size=30, font_family=theme.FONT_FAMILY_MEDIUM,
                               style=ft.TextStyle(letter_spacing=-0.8))
        self.label = ft.Text("Запуск…", size=12, color=ft.Colors.ON_SURFACE_VARIANT)

        super().__init__(
            ft.Column([
                ft.Stack([ft.Container(self.halo, alignment=ft.alignment.center),
                          ft.Container(self.logo, alignment=ft.alignment.center)],
                         width=LOGO_SIZE * 2, height=LOGO_SIZE * 2),
                ft.Text(title, size=20, font_family=theme.FONT_FAMILY_MEDIUM,
                        style=ft.TextStyle(letter_spacing=-0.4)),
                ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Container(height=18),
                self.percent,
                ft.Container(self.bar, width=280),
                self.label,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, tight=True),
            expand=True, alignment=ft.alignment.center, opacity=1,
            animate_opacity=ft.animation.Animation(350, ft.AnimationCurve.EASE_IN),
        )

    # ---------- управление ----------

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._animate, daemon=True).start()

    def step(self, percent: int, label: str) -> None:
        """Следующий шаг запуска: проценты поедут к percent. Подпись сменится, когда проценты
        дойдут до этого шага, — иначе на быстром запуске «Готово» висело бы уже на 50%."""
        with self._lock:
            self.target = max(self.target, min(percent, 100))
            self._steps.append((self.target, label))
            self.label.value = self._label_for(self.shown)
            self._safe_update()

    def _label_for(self, shown: int) -> str:
        return next((label for pct, label in self._steps if pct >= shown), self.label.value)

    def finish(self, timeout: float = 4.0) -> None:
        """Догоняет до 100%, плавно гаснет и останавливает анимацию."""
        self.step(100, "Готово")
        deadline = time.monotonic() + timeout
        while self.shown < 100 and time.monotonic() < deadline:
            time.sleep(TICK)
        time.sleep(0.25)
        with self._lock:
            self.opacity = 0
            self._safe_update()
        time.sleep(0.35)
        self._running = False

    # ---------- анимация ----------

    def _animate(self) -> None:
        flips = 0
        next_flip = time.monotonic()
        while self._running:
            now = time.monotonic()
            with self._lock:
                if self.shown < self.target:
                    self.shown += 1
                    self.percent.value = f"{self.shown}%"
                    self.bar.value = self.shown / 100
                    self.label.value = self._label_for(self.shown)
                if now >= next_flip:
                    flips += 1
                    # Кубик поворачивается на четверть оборота, «вдыхая» на полпути;
                    # ореол то расходится и гаснет, то возвращается.
                    self.logo.rotate = ft.Rotate(flips * math.pi / 2)
                    self.logo.scale = 0.9 if flips % 2 else 1
                    self.halo.scale = 1.6 if flips % 2 else 1
                    self.halo.opacity = 0 if flips % 2 else 0.25
                    next_flip = now + FLIP_EVERY
                self._safe_update()
            time.sleep(TICK)

    def _safe_update(self) -> None:
        if self.page:
            try:
                self.update()
            except Exception:  # noqa: BLE001 - окно закрыли во время загрузки
                self._running = False
