"""
Tests for ConversationStorage: session rotation ownership migration
and conversation deletion with child rows.
"""

import pytest

from app.core.storage import ConversationStorage

CONV_ID = "test-conv-001"
OLD_SESSION = "old-session-abc"
NEW_SESSION = "new-session-xyz"


@pytest.fixture
async def storage(tmp_path):
    db_path = str(tmp_path / "test_storage.db")
    s = ConversationStorage(db_path=db_path)
    await s.initialize()
    yield s
    await s.close()


class TestSessionRotationMigratesOwnership:
    """rotate_web_session must transfer conversation ownership to the new session."""

    async def test_conversations_owned_by_new_session_after_rotation(self, storage):
        # Create a conversation owned by the old session
        await storage.create_conversation(
            id=CONV_ID, title="Test", web_owner_session_id=OLD_SESSION
        )

        # Create the old web session
        import time

        now = int(time.time())
        await storage.db.execute(
            "INSERT INTO web_sessions (session_id, ua_hash, ip_prefix, created_at, last_seen_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (OLD_SESSION, "hash", "127.0", now, now, now + 86400),
        )
        await storage.db.commit()

        # Rotate session
        await storage.rotate_web_session(
            old_session_id=OLD_SESSION,
            new_session_id=NEW_SESSION,
            ua_hash="hash",
            ip_prefix="127.0",
            expires_at=now + 86400,
        )

        # Conversation should now be owned by the new session
        convs = await storage.list_conversations_by_web_owner(NEW_SESSION)
        assert len(convs) == 1
        assert convs[0]["id"] == CONV_ID

        # Old session should have no conversations
        old_convs = await storage.list_conversations_by_web_owner(OLD_SESSION)
        assert len(old_convs) == 0


class TestDeleteConversationWithChildRows:
    """delete_conversation must succeed even when child rows exist."""

    async def test_delete_with_messages(self, storage):
        await storage.create_conversation(
            id=CONV_ID, title="Test", web_owner_session_id="sess"
        )
        await storage.add_message(
            conversation_id=CONV_ID, role="user", content="hello", source="web"
        )
        await storage.add_message(
            conversation_id=CONV_ID, role="assistant", content="hi", source="web"
        )

        deleted = await storage.delete_conversation(CONV_ID)
        assert deleted is True

        # Verify conversation is gone
        conv = await storage.get_conversation(CONV_ID)
        assert conv is None

    async def test_delete_with_link_codes(self, storage):
        await storage.create_conversation(
            id=CONV_ID, title="Test", web_owner_session_id="sess"
        )
        # Create a telegram link code for this conversation
        await storage.create_telegram_link_code(CONV_ID, "sess")

        deleted = await storage.delete_conversation(CONV_ID)
        assert deleted is True

        conv = await storage.get_conversation(CONV_ID)
        assert conv is None

    async def test_delete_with_messages_and_link_codes(self, storage):
        await storage.create_conversation(
            id=CONV_ID, title="Test", web_owner_session_id="sess"
        )
        await storage.add_message(
            conversation_id=CONV_ID, role="user", content="test", source="web"
        )
        await storage.create_telegram_link_code(CONV_ID, "sess")

        deleted = await storage.delete_conversation(CONV_ID)
        assert deleted is True

        conv = await storage.get_conversation(CONV_ID)
        assert conv is None


class TestSessionTelegramChatId:
    """web_sessions should store telegram_chat_id."""

    async def test_new_session_has_null_telegram_chat_id(self, storage):
        import time

        now = int(time.time())
        await storage.create_web_session(
            session_id="sess-1",
            ua_hash="h",
            ip_prefix="127.0",
            expires_at=now + 86400,
        )
        session = await storage.get_web_session("sess-1")
        assert session is not None
        assert session["telegram_chat_id"] is None


class TestSessionRotationPreservesTelegramLink:
    """rotate_web_session must copy telegram_chat_id to the new session."""

    async def test_telegram_chat_id_carried_to_new_session(self, storage):
        import time

        now = int(time.time())

        # Create old session and manually set telegram_chat_id
        await storage.create_web_session(
            session_id="old-sess",
            ua_hash="h",
            ip_prefix="127.0",
            expires_at=now + 86400,
        )
        await storage.db.execute(
            "UPDATE web_sessions SET telegram_chat_id = ? WHERE session_id = ?",
            (55555, "old-sess"),
        )
        await storage.db.commit()

        await storage.rotate_web_session(
            old_session_id="old-sess",
            new_session_id="new-sess",
            ua_hash="h",
            ip_prefix="127.0",
            expires_at=now + 86400,
        )

        new_session = await storage.get_web_session("new-sess")
        assert new_session["telegram_chat_id"] == 55555


class TestLinkCodeUpdatesSession:
    """consume_telegram_link_code must set telegram_chat_id on session and ALL conversations."""

    async def test_consume_sets_session_and_all_conversations(self, storage):
        import time

        now = int(time.time())

        # Create session
        await storage.create_web_session(
            session_id="web-sess",
            ua_hash="h",
            ip_prefix="127.0",
            expires_at=now + 86400,
        )

        # Create two conversations owned by same session
        await storage.create_conversation(
            id="conv-a", title="Chat A", web_owner_session_id="web-sess",
        )
        await storage.create_conversation(
            id="conv-b", title="Chat B", web_owner_session_id="web-sess",
        )

        # Create link code for conv-a
        code = await storage.create_telegram_link_code("conv-a", "web-sess")

        # Consume the code
        result = await storage.consume_telegram_link_code(code, telegram_chat_id=77777)
        assert result is not None

        # Session should have telegram_chat_id
        session = await storage.get_web_session("web-sess")
        assert session["telegram_chat_id"] == 77777

        # Both conversations should be linked
        conv_a = await storage.get_conversation("conv-a")
        assert conv_a["telegram_chat_id"] == 77777
        conv_b = await storage.get_conversation("conv-b")
        assert conv_b["telegram_chat_id"] == 77777


class TestUnlinkTelegramSession:
    """unlink_telegram_session clears session and all its conversations."""

    async def test_unlink_clears_session_and_conversations(self, storage):
        import time

        now = int(time.time())

        await storage.create_web_session(
            session_id="s1",
            ua_hash="h",
            ip_prefix="127.0",
            expires_at=now + 86400,
        )
        await storage.db.execute(
            "UPDATE web_sessions SET telegram_chat_id = ? WHERE session_id = ?",
            (88888, "s1"),
        )
        await storage.create_conversation(
            id="c1", title="A", web_owner_session_id="s1", telegram_chat_id=88888,
        )
        await storage.create_conversation(
            id="c2", title="B", web_owner_session_id="s1", telegram_chat_id=88888,
        )
        await storage.db.commit()

        await storage.unlink_telegram_session("s1")

        session = await storage.get_web_session("s1")
        assert session["telegram_chat_id"] is None
        assert (await storage.get_conversation("c1"))["telegram_chat_id"] is None
        assert (await storage.get_conversation("c2"))["telegram_chat_id"] is None
