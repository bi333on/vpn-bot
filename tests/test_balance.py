from app.db.models import User
from app.services.balance import add_balance, spend_balance


async def test_add_and_spend(db_session):
    user = User(telegram_id=123, balance=0)
    db_session.add(user)
    await db_session.flush()

    await add_balance(db_session, user, 1000, "manual", "тест")
    assert user.balance == 1000

    ok = await spend_balance(db_session, user, 400, "покупка")
    assert ok is True
    assert user.balance == 600

    ok = await spend_balance(db_session, user, 999999)
    assert ok is False
    assert user.balance == 600


async def test_add_ignores_non_positive(db_session):
    user = User(telegram_id=124, balance=0)
    db_session.add(user)
    await db_session.flush()
    await add_balance(db_session, user, 0, "manual")
    await add_balance(db_session, user, -50, "manual")
    assert user.balance == 0
