"""Тесты для pricing.py (используется и ботом, и приложением)."""
import db
import pricing


def test_money_formats_with_currency(temp_db):
    db.set_setting("currency", "₽")
    assert pricing.money(1234) == "1 234 ₽"


def test_parse_number_accepts_comma_decimal():
    assert pricing.parse_number("12,5") == 12.5


def test_parse_number_rejects_negative():
    assert pricing.parse_number("-5") is None


def test_parse_hours_accepts_colon_format():
    assert pricing.parse_hours("2:30") == 2.5


def test_parse_hours_accepts_ru_short_format():
    assert pricing.parse_hours("2ч 30м") == 2.5


def test_parse_date_accepts_relative_words():
    assert pricing.parse_date("сегодня") is not None
    assert pricing.parse_date("завтра") is not None


def test_parse_date_rejects_garbage():
    assert pricing.parse_date("не дата") is None


def test_calc_price_matches_formula(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 50)
    db.set_setting("reverse_price", 1000)
    result = pricing.calc_price("PLA", weight_g=100, hours=2, qty=1)
    assert result["material_cost"] == 100 * 1 * 4000 / 1000
    assert result["time_cost"] == 2 * 1 * 50
    assert result["reverse_cost"] == 0
    assert result["price"] == result["material_cost"] + result["time_cost"]


def test_calc_price_adds_reverse_engineering_cost(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 50)
    db.set_setting("reverse_price", 1000)
    result = pricing.calc_price("PLA", weight_g=0, hours=0, qty=1, reverse=True)
    assert result["reverse_cost"] == 1000
    assert result["price"] == 1000


def test_recalc_order_price_updates_stored_values(temp_db):
    db.set_setting("materials", {"PLA": 4000})
    db.set_setting("hour_rate", 50)
    order_id = db.add_order({
        "client": "Тест", "contact": "", "material": "PLA",
        "weight_g": 100, "print_hours": 1, "qty": 1, "cost": 0, "price": 0,
    })
    pricing.recalc_order_price(order_id)
    order = db.get_order(order_id)
    assert order["price"] == 100 * 4000 / 1000 + 1 * 50


def test_parse_weight_accepts_comma_and_dot_fractions():
    assert pricing.parse_weight("454,28") == 454.28
    assert pricing.parse_weight("454.28") == 454.28


def test_parse_weight_accepts_gram_suffix():
    assert pricing.parse_weight("454,28 г") == 454.28
    assert pricing.parse_weight("454.28гр") == 454.28
    assert pricing.parse_weight("12 грамм") == 12


def test_parse_weight_rejects_garbage():
    assert pricing.parse_weight("много") is None
    assert pricing.parse_weight("") is None


def test_parse_hours_accepts_days_hours_minutes():
    assert round(pricing.parse_hours("1д 6ч 46м"), 4) == round(30 + 46 / 60, 4)
    assert round(pricing.parse_hours("1д 6часов 46 мин"), 4) == round(30 + 46 / 60, 4)
    assert pricing.parse_hours("1д") == 24


def test_parse_hours_accepts_minutes_with_space_and_full_words():
    assert pricing.parse_hours("2ч 30 мин") == 2.5
    assert pricing.parse_hours("2 часа 30 минут") == 2.5
    assert pricing.parse_hours("150 мин") == 2.5
    assert pricing.parse_hours("2,5") == 2.5


def test_parse_hours_rejects_garbage():
    assert pricing.parse_hours("долго") is None
    assert pricing.parse_hours("2ч 30м abc") is None


def test_fmt_hours_renders_days_hours_minutes():
    assert pricing.fmt_hours(2.5) == "2ч 30м"
    assert pricing.fmt_hours(30 + 46 / 60) == "1д 6ч 46м"
    assert pricing.fmt_hours(24) == "1д"
    assert pricing.fmt_hours(0) == "0ч"


def test_fmt_hours_round_trips_through_parse_hours():
    for text in ["2ч 30м", "1д 6ч 46м", "45м", "3ч"]:
        assert pricing.fmt_hours(pricing.parse_hours(text)) == text


def test_fmt_number_uses_comma_decimal():
    assert pricing.fmt_number(454.28) == "454,28"
    assert pricing.fmt_number(30.766666) == "30,77"
    assert pricing.fmt_number(50.0) == "50"


def test_fmt_number_never_uses_exponent():
    assert pricing.fmt_number(1234567.5) == "1234567,5"
