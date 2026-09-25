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


def test_every_status_has_plain_label_and_color():
    for code in db.STATUSES:
        label, color = theme.status_style(code)
        assert label and not any(ord(ch) > 0x2000 for ch in label)  # без эмодзи
        assert color


def test_status_style_unknown_code_falls_back_to_code():
    label, _ = theme.status_style("weird")
    assert label == "weird"


def test_status_chip_shows_plain_label():
    chip = theme.status_chip("printing")
    texts = [c.value for c in chip.content.controls if isinstance(c, ft.Text)]
    assert "Печатается" in texts


def test_grid_is_responsive_row_aligned_to_top():
    g = theme.grid([ft.Text("a")])
    assert isinstance(g, ft.ResponsiveRow)
    assert g.vertical_alignment == ft.CrossAxisAlignment.START


def test_page_header_contains_title_and_actions():
    btn = ft.FilledButton("x")
    header = theme.page_header("Заказы", "14 всего", [btn])
    assert "Заказы" in _texts(header)
    assert "14 всего" in _texts(header)
    assert btn in _walk(header)


def test_content_padding_centers_content_on_wide_screens():
    assert theme.content_padding(800) == theme.PAGE_PADDING
    wide = theme.content_padding(2000)
    assert wide > theme.PAGE_PADDING
    assert 2000 - 2 * wide == theme.MAX_CONTENT_WIDTH


def _walk(control):
    yield control
    for attr in ("content", "controls"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for c in child:
                yield from _walk(c)
        elif isinstance(child, ft.Control):
            yield from _walk(child)


def _texts(control):
    return [c.value for c in _walk(control) if isinstance(c, ft.Text)]
