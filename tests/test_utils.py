from app.utils import fmt_bytes, fmt_money, gb_to_bytes, generate_referral_code


def test_fmt_money():
    assert fmt_money(14900) == "149.00 ₽"
    assert fmt_money(50) == "0.50 ₽"
    assert fmt_money(0) == "0.00 ₽"
    assert fmt_money(-50) == "-0.50 ₽"


def test_gb_to_bytes():
    assert gb_to_bytes(1) == 1073741824
    assert gb_to_bytes(0) == 0


def test_fmt_bytes():
    assert fmt_bytes(1073741824) == "1.00 ГБ"


def test_generate_referral_code():
    code = generate_referral_code()
    assert len(code) == 10
    assert code.isalnum()
