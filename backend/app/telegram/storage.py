from __future__ import annotations

import aiosqlite


class SubscriptionStorage:
    def __init__(self, db_path: str = "subscriptions.db"):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id BIGINT NOT NULL,
                topic TEXT NOT NULL,
                frequency TEXT NOT NULL,
                time TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Asia/Taipei',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, topic)
            )
        """)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def add(
        self,
        chat_id: int,
        topic: str,
        frequency: str,
        time: str,
        timezone: str = "Asia/Taipei",
    ) -> None:
        try:
            await self._db.execute(
                "INSERT INTO subscriptions (chat_id, topic, frequency, time, timezone) VALUES (?, ?, ?, ?, ?)",
                (chat_id, topic, frequency, time, timezone),
            )
            await self._db.commit()
        except aiosqlite.IntegrityError:
            raise ValueError(f"already subscribed to '{topic}'")

    async def remove(self, chat_id: int, topic: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM subscriptions WHERE chat_id = ? AND topic = ?",
            (chat_id, topic),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def list(self, chat_id: int) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT topic, frequency, time, timezone FROM subscriptions WHERE chat_id = ?",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [
            {"topic": r[0], "frequency": r[1], "time": r[2], "timezone": r[3]}
            for r in rows
        ]

    async def list_all(self) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT chat_id, topic, frequency, time, timezone FROM subscriptions"
        )
        rows = await cursor.fetchall()
        return [
            {"chat_id": r[0], "topic": r[1], "frequency": r[2], "time": r[3], "timezone": r[4]}
            for r in rows
        ]

    async def get_all_chat_ids(self) -> list[int]:
        cursor = await self._db.execute(
            "SELECT DISTINCT chat_id FROM subscriptions"
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def get_subscriber_chat_ids(self) -> list[int]:
        return await self.get_all_chat_ids()
