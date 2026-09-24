"""Тесты для app/theme.py — чистые функции, без side effects."""
import flet as ft

import db
from app import theme


def test_card_wraps_content_in_rounded_container():
    inner = ft.Text("hello")
    result = theme.card(inner)
    assert isinstance(result, ft.Container)
    assert result.content is inner
    assert result.border_radius == theme.CARD_RADIUS


def test_card_allows_overriding_defaults():
    inner = ft.Text("hi")
    result = theme.card(inner, padding=0, width=160)
    assert result.padding == 0
    assert result.width == 160


def test_next_theme_mode_cycles_system_light_dark():
    assert theme.next_theme_mode("system") == "light"
    assert theme.next_theme_mode("light") == "dark"
    assert theme.next_theme_mode("dark") == "system"


def test_next_theme_mode_unknown_value_falls_back_to_system():
    assert theme.next_theme_mode("bogus") == "system"


def test_flet_theme_modes_cover_every_cycle_value():
    for mode in theme.THEME_MODE_CYCLE:
        assert mode in theme.FLET_THEME_MODES
        assert mode in theme.THEME_ICONS


def test_flet_theme_mode_handles_every_stored_value_safely(temp_db):
    for mode in theme.THEME_MODE_CYCLE:
        db.set_setting("theme_mode", mode)
        stored = db.get_settings()["theme_mode"]
        assert theme.flet_theme_mode(stored) in theme.FLET_THEME_MODES.values()


def test_flet_theme_mode_falls_back_to_system_for_unknown_value():
    assert theme.flet_theme_mode("corrupted-value") == theme.FLET_THEME_MODES["system"]
