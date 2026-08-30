from app.payments.cryptobot import CryptoBotProvider
from app.payments.yookassa import YooKassaProvider


def test_yookassa_parse():
    provider = YooKassaProvider("shop", "secret")
    result = provider.parse_webhook(
        {
            "object": {
                "id": "pay1",
                "status": "succeeded",
                "amount": {"value": "100.00", "currency": "RUB"},
            }
        }
    )
    assert result.provider_payment_id == "pay1"
    assert result.status == "succeeded"
    assert result.amount == 10000
    assert result.currency == "RUB"


def test_cryptobot_parse():
    provider = CryptoBotProvider("token")
    result = provider.parse_webhook(
        {"payload": {"invoice_id": "123", "status": "paid"}}
    )
    assert result.provider_payment_id == "123"
    assert result.status == "succeeded"
