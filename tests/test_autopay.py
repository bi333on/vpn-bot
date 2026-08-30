from __future__ import annotations

from app.db.models import Plan, Subscription, User
from app.i18n import tr
from app.services.autopay import daily_price, try_auto_renew


class FakeClient:
    def __init__(self) -> None:
        self.updates: list[tuple] = []

    async def update_user(self, short_uuid, **fields):
        self.updates.append((short_uuid, fields))
        return {"ok": True}


def _make_sub(user_id: int, plan_id: int | None) -> Subscription:
    return Subscription(
        user_id=user_id,
        plan_id=plan_id,
        remnawave_short_uuid="abcd",
        status="active",
        auto_renew=True,
    )


def test_daily_price():
    plan = Plan(price=3000, duration_days=30)  # 30 руб / 30 дн = 1 руб/день
    assert daily_price(plan) == 100
    plan2 = Plan(price=3100, duration_days=31)
    assert daily_price(plan2) == 100  # ceil(100.0)


def test_daily_price_zero_days():
    plan = Plan(price=500, duration_days=0)
    assert daily_price(plan) == 500


async def test_autorenew_full(db_session):
    user = User(telegram_id=1, balance=3000)
    plan = Plan(name="P", price=3000, duration_days=30, traffic_gb=10, devices_limit=2)
    db_session.add_all([user, plan])
    await db_session.flush()
    sub = _make_sub(user.id, plan.id)
    db_session.add(sub)
    await db_session.flush()

    fake = FakeClient()
    result = await try_auto_renew(db_session, fake, sub, user)

    assert result == "renewed_full"
    assert user.balance == 0
    assert len(fake.updates) == 1
    assert sub.status == "active"


async def test_autorenew_day(db_session):
    user = User(telegram_id=2, balance=100)  # хватает только на 1 день
    plan = Plan(name="P", price=3000, duration_days=30, traffic_gb=10, devices_limit=1)
    db_session.add_all([user, plan])
    await db_session.flush()
    sub = _make_sub(user.id, plan.id)
    db_session.add(sub)
    await db_session.flush()

    fake = FakeClient()
    result = await try_auto_renew(db_session, fake, sub, user)

    assert result == "renewed_day"
    assert user.balance == 0
    assert len(fake.updates) == 1


async def test_autorenew_insufficient(db_session):
    user = User(telegram_id=3, balance=50)
    plan = Plan(name="P", price=3000, duration_days=30, traffic_gb=10, devices_limit=1)
    db_session.add_all([user, plan])
    await db_session.flush()
    sub = _make_sub(user.id, plan.id)
    db_session.add(sub)
    await db_session.flush()

    fake = FakeClient()
    result = await try_auto_renew(db_session, fake, sub, user)

    assert result == "insufficient"
    assert user.balance == 50
    assert len(fake.updates) == 0


async def test_autorenew_no_plan(db_session):
    user = User(telegram_id=4, balance=99999)
    db_session.add(user)
    await db_session.flush()
    sub = _make_sub(user.id, None)
    db_session.add(sub)
    await db_session.flush()

    fake = FakeClient()
    result = await try_auto_renew(db_session, fake, sub, user)
    assert result == "no_plan"


def test_tr():
    assert tr("ru", "menu_buy") == "🛒 Купить"
    assert tr("en", "menu_buy") == "🛒 Buy"
    assert tr("de", "menu_buy") == "🛒 Купить"  # fallback
    assert tr("en", "pay_total", price="149.00 ₽") == "Total: <b>149.00 ₽</b>"
