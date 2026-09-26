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


def test_normalize_theme_keeps_known_values_and_falls_back_to_system():
    assert theme.normalize_theme("system") == "system"
    assert theme.normalize_theme("dracula") == "dracula"
    assert theme.normalize_theme("corrupted-value") == "system"
    assert theme.normalize_theme(None) == "system"


def test_every_palette_has_hex_colors_and_names():
    for key, p in theme.PALETTES.items():
        assert p.name
        for color in (p.bg, p.card, p.fg, p.muted, p.border, p.subtle, p.line, p.accent, *p.syntax):
            assert color.startswith("#") and len(color) == 7, (key, color)
    assert {"light", "dark"} <= set(theme.PALETTES)
    assert any(not p.dark for p in theme.PALETTES.values())


class _FakePage:
    theme = dark_theme = theme_mode = None


def test_apply_theme_system_uses_light_and_dark():
    page = _FakePage()
    theme.apply_theme(page, "system")
    assert page.theme_mode == ft.ThemeMode.SYSTEM
    assert page.theme is theme.LIGHT_THEME and page.dark_theme is theme.DARK_THEME


def test_apply_theme_palette_sets_mode_and_colors():
    page = _FakePage()
    theme.apply_theme(page, "dracula")
    assert page.theme_mode == ft.ThemeMode.DARK
    assert page.theme.color_scheme.primary == theme.PALETTES["dracula"].accent
    assert page.theme.scaffold_bgcolor == theme.PALETTES["dracula"].bg
    theme.apply_theme(page, "github_light")
    assert page.theme_mode == ft.ThemeMode.LIGHT


def test_theme_stored_in_settings_round_trips(temp_db):
    db.set_setting("theme_mode", "nord")
    assert theme.normalize_theme(db.get_settings()["theme_mode"]) == "nord"
    assert theme.theme_name("nord") == "Nord"


def test_theme_dialog_renders_all_themes_and_picks(monkeypatch):
    from app.theme_dialog import ThemeDialog
    picked = []
    dialog = ThemeDialog(page=None, on_pick=picked.append)
    monkeypatch.setattr(dialog.dialog, "update", lambda: None)
    dialog.current = "system"
    dialog._render()
    names = _texts(dialog.body)
    for key in theme.PALETTES:
        assert theme.PALETTES[key].name in names
    dialog._pick("monokai")
    assert picked == ["monokai"] and dialog.current == "monokai"


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
