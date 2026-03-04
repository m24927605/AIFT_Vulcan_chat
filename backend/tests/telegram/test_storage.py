import pytest
from app.telegram.storage import SubscriptionStorage


@pytest.fixture
async def storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SubscriptionStorage(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_add_subscription(storage):
    await storage.add(chat_id=123, topic="科技新聞", frequency="daily", time="09:00")
    subs = await storage.list(chat_id=123)
    assert len(subs) == 1
    assert subs[0]["topic"] == "科技新聞"
    assert subs[0]["frequency"] == "daily"
    assert subs[0]["time"] == "09:00"


@pytest.mark.asyncio
async def test_add_duplicate_subscription_raises(storage):
    await storage.add(chat_id=123, topic="科技新聞", frequency="daily", time="09:00")
    with pytest.raises(ValueError, match="already subscribed"):
        await storage.add(chat_id=123, topic="科技新聞", frequency="daily", time="09:00")


@pytest.mark.asyncio
async def test_remove_subscription(storage):
    await storage.add(chat_id=123, topic="科技新聞", frequency="daily", time="09:00")
    removed = await storage.remove(chat_id=123, topic="科技新聞")
    assert removed is True
    subs = await storage.list(chat_id=123)
    assert len(subs) == 0


@pytest.mark.asyncio
async def test_remove_nonexistent_subscription(storage):
    removed = await storage.remove(chat_id=123, topic="不存在")
    assert removed is False


@pytest.mark.asyncio
async def test_list_empty_subscriptions(storage):
    subs = await storage.list(chat_id=999)
    assert subs == []


@pytest.mark.asyncio
async def test_list_all_subscriptions(storage):
    await storage.add(chat_id=123, topic="科技", frequency="daily", time="09:00")
    await storage.add(chat_id=456, topic="財經", frequency="weekly", time="10:00")
    all_subs = await storage.list_all()
    assert len(all_subs) == 2


@pytest.mark.asyncio
async def test_get_all_chat_ids(storage):
    await storage.add(chat_id=123, topic="科技", frequency="daily", time="09:00")
    await storage.add(chat_id=456, topic="財經", frequency="daily", time="10:00")
    await storage.add(chat_id=123, topic="財經", frequency="weekly", time="10:00")
    chat_ids = await storage.get_all_chat_ids()
    assert set(chat_ids) == {123, 456}


@pytest.mark.asyncio
async def test_get_subscriber_chat_ids(storage):
    await storage.add(chat_id=123, topic="科技", frequency="daily", time="09:00")
    await storage.add(chat_id=456, topic="財經", frequency="daily", time="10:00")
    chat_ids = await storage.get_subscriber_chat_ids()
    assert set(chat_ids) == {123, 456}
