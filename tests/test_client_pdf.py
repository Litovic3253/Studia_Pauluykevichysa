"""PDF для клиента: файл создаётся, разбивка цены сходится с итогом до рубля."""
import db
import pricing
from app import client_pdf


def _setup():
    db.set_setting("materials", {"PLA": 4, "ABS": 10})
    db.set_setting("purchase_prices", {"PLA": 1.5})
    db.set_setting("hour_rate", 50)
    db.set_setting("reverse_price", 1500)


def _order(price=None, **extra) -> int:
    data = {"client": "Александр Петров", "contact": "+7 900", "description": "Крепление", "material": "PLA",
            "color": "Чёрный", "weight_g": 123.45, "print_hours": 2.5, "qty": 3, "deadline": "2026-10-02",
            "cost": 0, "reverse_engineering": 0, "defect_percent": 10, **extra}
    calc = pricing.calc_price(data["material"], data["weight_g"], data["print_hours"], data["qty"],
                              bool(data["reverse_engineering"]), data["defect_percent"])
    data["price"] = calc["price"] if price is None else price
    return db.add_order(data)


def test_price_lines_sum_exactly_to_order_price(temp_db):
    _setup()
    oid = _order()
    lines = client_pdf.price_lines(db.get_order(oid))
    assert [name for name, _, _ in lines] == ["Материал", "Время печати", "Брак 10%"]
    assert sum(v for _, _, v in lines) == round(db.get_order(oid)["price"])


def test_manual_price_adds_discount_row(temp_db):
    _setup()
    oid = _order(price=1000, reverse_engineering=1)
    lines = client_pdf.price_lines(db.get_order(oid))
    assert lines[-2][0] == "Реверс-моделирование"
    assert lines[-1][0] == "Скидка" and lines[-1][2] < 0
    assert sum(v for _, _, v in lines) == 1000


def test_manual_price_above_calc_is_a_correction(temp_db):
    _setup()
    oid = _order(price=99999)
    assert client_pdf.price_lines(db.get_order(oid))[-1][0] == "Корректировка цены"


def test_build_pdf_writes_file_named_after_order(temp_db, tmp_path):
    _setup()
    oid = _order(prepayment=500)
    path = client_pdf.build_order_pdf(oid, tmp_path)
    assert path.name == f"Заказ_{oid}_Александр_Петров.pdf"
    data = path.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 1000


def test_pdf_has_no_internal_numbers(temp_db):
    """Закупка и прибыль — внутренние цифры, в разбивку для клиента они не попадают."""
    _setup()
    oid = _order()
    text = " ".join(f"{n} {how}" for n, how, _ in client_pdf.price_lines(db.get_order(oid))).lower()
    assert "закуп" not in text and "прибыл" not in text and "себестоим" not in text


def test_file_name_strips_unsafe_characters():
    assert client_pdf.file_name({"id": 7, "client": 'ИП "Рога/Копыта"'}) == "Заказ_7_ИП_Рога_Копыта.pdf"
    assert client_pdf.file_name({"id": 8, "client": ""}) == "Заказ_8.pdf"


def test_bottom_block_gets_payment_and_signer_from_settings(temp_db, tmp_path, monkeypatch):
    _setup()
    oid = _order()
    calls = []
    monkeypatch.setattr(client_pdf, "_bottom_block", lambda pdf, payment, signer, width: calls.append((payment, signer)))
    client_pdf.build_order_pdf(oid, tmp_path)
    db.set_setting("payment_text", "+79001234567\nИван Иванович\nСбербанк")
    db.set_setting("signer_name", "Иван Иванович И.")
    client_pdf.build_order_pdf(oid, tmp_path)
    assert calls == [("", ""), ("+79001234567\nИван Иванович\nСбербанк", "Иван Иванович И.")]


def test_signature_image_is_drawn_when_file_exists(temp_db, tmp_path, monkeypatch):
    from PIL import Image
    _setup()
    sig = tmp_path / "signature.png"
    Image.new("RGBA", (200, 80), (0, 0, 0, 0)).save(sig)
    monkeypatch.setattr(client_pdf, "SIGNATURE", sig)
    db.set_setting("signer_name", "Иван Иванович И.")
    drawn = []
    real_image = client_pdf.FPDF.image
    monkeypatch.setattr(client_pdf.FPDF, "image", lambda self, name, *a, **k: (drawn.append(str(name)),
                                                                                 real_image(self, name, *a, **k)))
    path = client_pdf.build_order_pdf(_order(), tmp_path)
    assert str(sig) in drawn and path.read_bytes().startswith(b"%PDF")


def test_payment_box_renders_long_text(temp_db, tmp_path):
    _setup()
    db.set_setting("payment_text", "89001234567 Иван Иванович банк: Сбер " * 4)
    path = client_pdf.build_order_pdf(_order(), tmp_path)
    assert path.read_bytes().startswith(b"%PDF")


def test_prepayment_due_is_half_by_default(temp_db):
    _setup()
    assert client_pdf.prepayment_due(db.get_order(_order(price=7601))) == 3800  # 50%, округлено до рубля


def test_prepayment_due_zero_when_paid_prepaid_or_disabled(temp_db):
    _setup()
    assert client_pdf.prepayment_due(db.get_order(_order(price=1000, prepayment=300))) == 0
    paid = _order(price=1000)
    db.update_order(paid, paid=1)
    assert client_pdf.prepayment_due(db.get_order(paid)) == 0
    db.set_setting("prepayment_percent", 0)
    assert client_pdf.prepayment_due(db.get_order(_order(price=1000))) == 0
    db.set_setting("prepayment_percent", 30)
    assert client_pdf.prepayment_due(db.get_order(_order(price=1000))) == 300
