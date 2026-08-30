from app.db.models import Plan, User
from app.services.subscription import create_subscription


class FakeRemnawave:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create_user(self, **kw):
        self.created.append(kw)
        return {"uuid": "uuid-1", "shortUuid": "abcd1234"}

    async def get_subscription(self, short_uuid: str):
        return ["vless://uuid-1@host:443?security=reality#VPN"]

    async def get_inbounds(self):
        return []

    async def get_hosts(self):
        return []


async def test_devices_limit_passed_to_remnawave(db_session):
    user = User(telegram_id=111)
    plan = Plan(
        name="Test",
        price=100,
        duration_days=30,
        traffic_gb=50,
        devices_limit=3,
    )
    db_session.add_all([user, plan])
    await db_session.flush()

    fake = FakeRemnawave()
    sub = await create_subscription(
        db_session,
        fake,
        user,
        plan=plan,
        duration_days=plan.duration_days,
        traffic_gb=plan.traffic_gb,
        devices_limit=plan.devices_limit,
    )

    assert fake.created[0]["devices_limit"] == 3
    assert fake.created[0]["tg_id"] == 111
    assert fake.created[0]["traffic_limit_bytes"] == 50 * 1024**3
    assert sub.devices_limit == 3
    assert sub.config_link == "vless://uuid-1@host:443?security=reality#VPN"
    assert sub.remnawave_short_uuid == "abcd1234"
