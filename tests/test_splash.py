"""Экран загрузки: проценты доходят до 100, экран гаснет, анимация останавливается."""
from app.splash import Splash


def test_splash_counts_to_100_and_fades_out():
    splash = Splash("Студия", "заказы")
    splash.start()
    splash.step(40, "Загружаю заказы…")
    assert splash.label.value == "Загружаю заказы…"
    splash.step(20, "назад не едет")
    assert splash.target == 40
    splash.finish()
    assert splash.shown == 100
    assert splash.percent.value == "100%"
    assert splash.opacity == 0
    assert not splash._running


def test_splash_label_follows_percent_not_latest_step():
    splash = Splash("Студия", "заказы")
    splash.step(30, "Шаг 1")
    splash.step(100, "Готово")
    assert splash.label.value == "Шаг 1"  # проценты ещё на 0 — «Готово» рано
    assert splash._label_for(31) == "Готово"
