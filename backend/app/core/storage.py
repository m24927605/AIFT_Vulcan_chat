from __future__ import annotations

import json
import os
import hashlib
import hmac
import secrets
import time

import aiosqlite

from app.core.config import settings


class ConversationStorage:
    def __init__(self, db_path: str = os.path.join(settings.data_dir, "conversations.db")):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("ConversationStorage not initialized. Call initialize() first.")
        return self._db

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                web_owner_session_id TEXT,
                telegram_chat_id INTEGER,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('web', 'telegram')),
                search_used BOOLEAN,
                citations TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS web_sessions (
                session_id TEXT PRIMARY KEY,
                ua_hash TEXT NOT NULL,
                ip_prefix TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                last_seen_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                rotated_to TEXT,
                revoked_at INTEGER
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS telegram_link_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                web_owner_session_id TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id, id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_telegram_chat_id ON conversations(telegram_chat_id)"
        )
        await self._db.commit()

        # Migration: add web_owner_session_id to existing DBs.
        cursor = await self._db.execute("PRAGMA table_info(conversations)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "web_owner_session_id" not in columns:
            await self._db.execute(
                "ALTER TABLE conversations ADD COLUMN web_owner_session_id TEXT"
            )
            await self._db.commit()
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_web_owner_session_id ON conversations(web_owner_session_id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_web_sessions_expires_at ON web_sessions(expires_at)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_tg_link_code_hash ON telegram_link_codes(code_hash)"
        )
        await self._db.commit()

        # Migration: add telegram_chat_id to web_sessions
        cursor = await self._db.execute("PRAGMA table_info(web_sessions)")
        ws_columns = [row[1] for row in await cursor.fetchall()]
        if "telegram_chat_id" not in ws_columns:
            await self._db.execute(
                "ALTER TABLE web_sessions ADD COLUMN telegram_chat_id INTEGER"
            )
            await self._db.commit()

        # Migration: remove UNIQUE constraint from telegram_chat_id
        # (allows multiple conversations to link the same Telegram chat)
        cursor = await self._db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='conversations'"
        )
        row = await cursor.fetchone()
        if row and "UNIQUE" in row[0]:
            await self._db.execute("PRAGMA foreign_keys=OFF")
            await self._db.execute("""
                CREATE TABLE conversations_new (
                    id TEXT PRIMARY KEY,
                    web_owner_session_id TEXT,
                    telegram_chat_id INTEGER,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._db.execute(
                "INSERT INTO conversations_new (id, web_owner_session_id, telegram_chat_id, title, created_at) "
                "SELECT id, web_owner_session_id, telegram_chat_id, title, created_at FROM conversations"
            )
            await self._db.execute("DROP TABLE conversations")
            await self._db.execute("ALTER TABLE conversations_new RENAME TO conversations")
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_telegram_chat_id ON conversations(telegram_chat_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_web_owner_session_id ON conversations(web_owner_session_id)"
            )
            await self._db.execute("PRAGMA foreign_keys=ON")
            await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def create_conversation(
        self,
        id: str,
        title: str,
        web_owner_session_id: str | None = None,
        telegram_chat_id: int | None = None,
    ) -> dict:
        await self.db.execute(
            "INSERT INTO conversations (id, title, web_owner_session_id, telegram_chat_id) VALUES (?, ?, ?, ?)",
            (id, title, web_owner_session_id, telegram_chat_id),
        )
        await self.db.commit()
        return {
            "id": id,
            "title": title,
            "web_owner_session_id": web_owner_session_id,
            "telegram_chat_id": telegram_chat_id,
        }

    async def get_conversation(self, id: str) -> dict | None:
        cursor = await self.db.execute(
            "SELECT id, web_owner_session_id, telegram_chat_id, title, created_at FROM conversations WHERE id = ?",
            (id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "web_owner_session_id": row[1],
            "telegram_chat_id": row[2],
            "title": row[3],
            "created_at": row[4],
        }

    async def claim_conversation_owner_if_unset(
        self,
        conversation_id: str,
        web_owner_session_id: str,
    ) -> bool:
        cursor = await self.db.execute(
            "UPDATE conversations SET web_owner_session_id = ? "
            "WHERE id = ? AND web_owner_session_id IS NULL",
            (web_owner_session_id, conversation_id),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_conversations_by_telegram_chat_id(self, chat_id: int) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT id, web_owner_session_id, telegram_chat_id, title, created_at FROM conversations WHERE telegram_chat_id = ? ORDER BY created_at",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "web_owner_session_id": r[1],
                "telegram_chat_id": r[2],
                "title": r[3],
                "created_at": r[4],
            }
            for r in rows
        ]

    async def list_conversations_by_web_owner(self, web_owner_session_id: str) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT id, web_owner_session_id, telegram_chat_id, title, created_at "
            "FROM conversations WHERE web_owner_session_id = ? ORDER BY created_at DESC",
            (web_owner_session_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "web_owner_session_id": r[1],
                "telegram_chat_id": r[2],
                "title": r[3],
                "created_at": r[4],
            }
            for r in rows
        ]

    async def delete_conversation(self, id: str) -> bool:
        # Explicitly delete child rows first to avoid FK constraint errors
        # on databases where ON DELETE CASCADE may not be active.
        await self.db.execute("DELETE FROM telegram_link_codes WHERE conversation_id = ?", (id,))
        await self.db.execute("DELETE FROM messages WHERE conversation_id = ?", (id,))
        cursor = await self.db.execute("DELETE FROM conversations WHERE id = ?", (id,))
        await self.db.commit()
        return cursor.rowcount > 0

    async def link_telegram(self, conversation_id: str, telegram_chat_id: int) -> None:
        await self.db.execute(
            "UPDATE conversations SET telegram_chat_id = ? WHERE id = ?",
            (telegram_chat_id, conversation_id),
        )
        await self.db.commit()

    async def unlink_telegram(self, conversation_id: str) -> None:
        await self.db.execute(
            "UPDATE conversations SET telegram_chat_id = NULL WHERE id = ?",
            (conversation_id,),
        )
        await self.db.commit()

    async def unlink_telegram_session(self, session_id: str) -> None:
        """Clear telegram_chat_id from session and all its conversations."""
        await self.db.execute(
            "UPDATE web_sessions SET telegram_chat_id = NULL WHERE session_id = ?",
            (session_id,),
        )
        await self.db.execute(
            "UPDATE conversations SET telegram_chat_id = NULL WHERE web_owner_session_id = ?",
            (session_id,),
        )
        await self.db.commit()

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        source: str,
        search_used: bool | None = None,
        citations: list[dict] | None = None,
    ) -> int:
        citations_json = json.dumps(citations) if citations else None
        cursor = await self.db.execute(
            "INSERT INTO messages (conversation_id, role, content, source, search_used, citations) VALUES (?, ?, ?, ?, ?, ?)",
            (conversation_id, role, content, source, search_used, citations_json),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def get_messages(
        self,
        conversation_id: str,
        after_id: int | None = None,
    ) -> list[dict]:
        if after_id is not None:
            cursor = await self.db.execute(
                "SELECT id, role, content, source, search_used, citations, created_at "
                "FROM messages WHERE conversation_id = ? AND id > ? ORDER BY id",
                (conversation_id, after_id),
            )
        else:
            cursor = await self.db.execute(
                "SELECT id, role, content, source, search_used, citations, created_at "
                "FROM messages WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "role": r[1],
                "content": r[2],
                "source": r[3],
                "search_used": r[4],
                "citations": json.loads(r[5]) if r[5] else None,
                "created_at": r[6],
            }
            for r in rows
        ]

    async def create_web_session(
        self,
        session_id: str,
        ua_hash: str,
        ip_prefix: str,
        expires_at: int,
    ) -> None:
        now = int(time.time())
        await self.db.execute(
            "INSERT INTO web_sessions (session_id, ua_hash, ip_prefix, created_at, last_seen_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, ua_hash, ip_prefix, now, now, expires_at),
        )
        await self.db.commit()

    async def get_web_session(self, session_id: str) -> dict | None:
        cur = await self.db.execute(
            "SELECT session_id, ua_hash, ip_prefix, created_at, last_seen_at, expires_at, rotated_to, revoked_at, telegram_chat_id "
            "FROM web_sessions WHERE session_id = ?",
            (session_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "session_id": row[0],
            "ua_hash": row[1],
            "ip_prefix": row[2],
            "created_at": row[3],
            "last_seen_at": row[4],
            "expires_at": row[5],
            "rotated_to": row[6],
            "revoked_at": row[7],
            "telegram_chat_id": row[8],
        }

    async def touch_web_session(self, session_id: str) -> None:
        now = int(time.time())
        await self.db.execute(
            "UPDATE web_sessions SET last_seen_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        await self.db.commit()

    async def rotate_web_session(
        self,
        old_session_id: str,
        new_session_id: str,
        ua_hash: str,
        ip_prefix: str,
        expires_at: int,
    ) -> None:
        now = int(time.time())
        # Read old session's telegram_chat_id before revoking
        old_session = await self.get_web_session(old_session_id)
        old_tg = old_session["telegram_chat_id"] if old_session else None

        await self.db.execute(
            "UPDATE web_sessions SET rotated_to = ?, revoked_at = ? WHERE session_id = ?",
            (new_session_id, now, old_session_id),
        )
        await self.db.execute(
            "INSERT INTO web_sessions (session_id, ua_hash, ip_prefix, created_at, last_seen_at, expires_at, telegram_chat_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_session_id, ua_hash, ip_prefix, now, now, expires_at, old_tg),
        )
        # Migrate conversation ownership to the new session
        await self.db.execute(
            "UPDATE conversations SET web_owner_session_id = ? WHERE web_owner_session_id = ?",
            (new_session_id, old_session_id),
        )
        await self.db.commit()

    def _hash_link_code(self, code: str) -> str:
        key = settings.api_secret_key or "dev-link-code-key"
        return hmac.new(key.encode(), code.encode(), hashlib.sha256).hexdigest()

    async def create_telegram_link_code(
        self,
        conversation_id: str,
        web_owner_session_id: str,
        ttl_seconds: int = 600,
    ) -> str:
        code = f"{secrets.randbelow(100_000_000):08d}"
        now = int(time.time())
        expires_at = now + ttl_seconds
        code_hash = self._hash_link_code(code)
        await self.db.execute(
            "INSERT INTO telegram_link_codes "
            "(conversation_id, web_owner_session_id, code_hash, expires_at, used_at, attempts, created_at) "
            "VALUES (?, ?, ?, ?, NULL, 0, ?)",
            (conversation_id, web_owner_session_id, code_hash, expires_at, now),
        )
        await self.db.commit()
        return code

    async def consume_telegram_link_code(
        self,
        code: str,
        telegram_chat_id: int,
        max_attempts: int = 5,
    ) -> dict | None:
        now = int(time.time())
        code_hash = self._hash_link_code(code)
        cur = await self.db.execute(
            "SELECT id, conversation_id, web_owner_session_id, expires_at, used_at, attempts "
            "FROM telegram_link_codes "
            "WHERE code_hash = ? ORDER BY id DESC LIMIT 1",
            (code_hash,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        rec_id, conv_id, session_id, expires_at, used_at, attempts = row
        # Count every consume attempt for matched code hash.
        next_attempts = attempts + 1
        await self.db.execute(
            "UPDATE telegram_link_codes SET attempts = ? WHERE id = ?",
            (next_attempts, rec_id),
        )
        if used_at is not None or expires_at < now or next_attempts > max_attempts:
            await self.db.commit()
            return None
        await self.db.execute(
            "UPDATE telegram_link_codes SET used_at = ? WHERE id = ?",
            (now, rec_id),
        )
        # Link the session
        await self.db.execute(
            "UPDATE web_sessions SET telegram_chat_id = ? WHERE session_id = ?",
            (telegram_chat_id, session_id),
        )
        # Link ALL conversations owned by this session
        await self.db.execute(
            "UPDATE conversations SET telegram_chat_id = ? WHERE web_owner_session_id = ?",
            (telegram_chat_id, session_id),
        )
        await self.db.commit()
        conv = await self.get_conversation(conv_id)
        return conv
