from app.db.models import PromoCode
from app.services.promo import compute_discount


def test_percent():
    promo = PromoCode(discount_type="percent", discount_value=10)
    price, discount = compute_discount(15000, promo)
    assert price == 13500
    assert discount == 1500


def test_fixed():
    promo = PromoCode(discount_type="fixed", discount_value=5000)
    price, discount = compute_discount(15000, promo)
    assert price == 10000
    assert discount == 5000


def test_fixed_capped_at_price():
    promo = PromoCode(discount_type="fixed", discount_value=999999)
    price, discount = compute_discount(15000, promo)
    assert price == 0
    assert discount == 15000
