# Persistent Telegram Identity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move Telegram identity from individual conversations to the web session, so deleting conversations never loses the Telegram link.

**Architecture:** Add `telegram_chat_id` column to `web_sessions` table. Session owns the Telegram identity; conversations inherit it on creation. Link code consumption updates the session + all conversations. Unlinking is session-wide. `GET /api/conversations` response changes from array to `{ session_telegram_chat_id, conversations }` wrapper.

**Tech Stack:** Python/FastAPI/aiosqlite (backend), Next.js/TypeScript/React (frontend), pytest + vitest (tests)

---

### Task 1: Storage — Add `telegram_chat_id` column to `web_sessions`

**Files:**
- Modify: `backend/app/core/storage.py:26-101` (initialize method)
- Modify: `backend/app/core/storage.py:308-326` (get_web_session)
- Test: `backend/tests/core/test_storage.py`

**Step 1: Write the failing test**

Add to `backend/tests/core/test_storage.py`:

```python
class TestSessionTelegramChatId:
    """web_sessions should store telegram_chat_id."""

    async def test_new_session_has_null_telegram_chat_id(self, storage):
        import time
        now = int(time.time())
        await storage.create_web_session(
            session_id="sess-1", ua_hash="h", ip_prefix="127.0",
            expires_at=now + 86400,
        )
        session = await storage.get_web_session("sess-1")
        assert session is not None
        assert session["telegram_chat_id"] is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/core/test_storage.py::TestSessionTelegramChatId -v`
Expected: FAIL — `KeyError: 'telegram_chat_id'` (get_web_session doesn't select it)

**Step 3: Write minimal implementation**

In `backend/app/core/storage.py`, add migration after the existing `web_sessions` migration block (after line 101):

```python
# Migration: add telegram_chat_id to web_sessions
cursor = await self._db.execute("PRAGMA table_info(web_sessions)")
ws_columns = [row[1] for row in await cursor.fetchall()]
if "telegram_chat_id" not in ws_columns:
    await self._db.execute(
        "ALTER TABLE web_sessions ADD COLUMN telegram_chat_id INTEGER"
    )
    await self._db.commit()
```

Update `get_web_session` (line 309) — add `telegram_chat_id` to SELECT and return dict:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/core/test_storage.py::TestSessionTelegramChatId -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/storage.py backend/tests/core/test_storage.py
git commit -m "feat: add telegram_chat_id column to web_sessions table"
```

---

### Task 2: Storage — Session rotation copies `telegram_chat_id`

**Files:**
- Modify: `backend/app/core/storage.py:336-359` (rotate_web_session)
- Test: `backend/tests/core/test_storage.py`

**Step 1: Write the failing test**

Add to `backend/tests/core/test_storage.py`:

```python
class TestSessionRotationPreservesTelegramLink:
    """rotate_web_session must copy telegram_chat_id to the new session."""

    async def test_telegram_chat_id_carried_to_new_session(self, storage):
        import time
        now = int(time.time())

        # Create old session and manually set telegram_chat_id
        await storage.create_web_session(
            session_id="old-sess", ua_hash="h", ip_prefix="127.0",
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/core/test_storage.py::TestSessionRotationPreservesTelegramLink -v`
Expected: FAIL — `assert None == 55555`

**Step 3: Write minimal implementation**

Update `rotate_web_session` in `backend/app/core/storage.py` (lines 336-359):

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/core/test_storage.py::TestSessionRotationPreservesTelegramLink -v`
Expected: PASS

**Step 5: Run all storage tests to check for regressions**

Run: `cd backend && python -m pytest tests/core/test_storage.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/app/core/storage.py backend/tests/core/test_storage.py
git commit -m "feat: copy telegram_chat_id during session rotation"
```

---

### Task 3: Storage — Link code consumption updates session + all conversations

**Files:**
- Modify: `backend/app/core/storage.py:384-420` (consume_telegram_link_code)
- Test: `backend/tests/core/test_storage.py`

**Step 1: Write the failing test**

Add to `backend/tests/core/test_storage.py`:

```python
class TestLinkCodeUpdatesSession:
    """consume_telegram_link_code must set telegram_chat_id on session and ALL conversations."""

    async def test_consume_sets_session_and_all_conversations(self, storage):
        import time
        now = int(time.time())

        # Create session
        await storage.create_web_session(
            session_id="web-sess", ua_hash="h", ip_prefix="127.0",
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/core/test_storage.py::TestLinkCodeUpdatesSession -v`
Expected: FAIL — session `telegram_chat_id` is None, conv-b `telegram_chat_id` is None

**Step 3: Write minimal implementation**

Update `consume_telegram_link_code` in `backend/app/core/storage.py` (lines 384-420):

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/core/test_storage.py::TestLinkCodeUpdatesSession -v`
Expected: PASS

**Step 5: Run all tests to check for regressions**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All PASS (existing link handler tests should still pass since `consume_telegram_link_code` returns the same thing)

**Step 6: Commit**

```bash
git add backend/app/core/storage.py backend/tests/core/test_storage.py
git commit -m "feat: link code consumption updates session and all conversations"
```

---

### Task 4: Storage — Session-level unlink

**Files:**
- Modify: `backend/app/core/storage.py` (add method after `unlink_telegram`)
- Test: `backend/tests/core/test_storage.py`

**Step 1: Write the failing test**

Add to `backend/tests/core/test_storage.py`:

```python
class TestUnlinkTelegramSession:
    """unlink_telegram_session clears session and all its conversations."""

    async def test_unlink_clears_session_and_conversations(self, storage):
        import time
        now = int(time.time())

        await storage.create_web_session(
            session_id="s1", ua_hash="h", ip_prefix="127.0",
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/core/test_storage.py::TestUnlinkTelegramSession -v`
Expected: FAIL — `AttributeError: 'ConversationStorage' object has no attribute 'unlink_telegram_session'`

**Step 3: Write minimal implementation**

Add after `unlink_telegram` method in `backend/app/core/storage.py` (after line 243):

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/core/test_storage.py::TestUnlinkTelegramSession -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/storage.py backend/tests/core/test_storage.py
git commit -m "feat: add session-level unlink_telegram_session method"
```

---

### Task 5: Routes — `list_conversations` returns `session_telegram_chat_id`

**Files:**
- Modify: `backend/app/web/routes/conversations.py:38-60` (list_conversations)
- Test: `backend/tests/web/test_conversations.py`

**Step 1: Write the failing test**

Add to `backend/tests/web/test_conversations.py`:

```python
def test_list_returns_session_telegram_chat_id(client):
    c, storage = client
    storage.get_web_session.return_value = {
        "session_id": "s1", "ua_hash": "h", "ip_prefix": "127.0",
        "created_at": 0, "last_seen_at": 0, "expires_at": 999999999999,
        "rotated_to": None, "revoked_at": None, "telegram_chat_id": 12345,
    }
    storage.list_conversations_by_web_owner.return_value = [
        {"id": "conv-1", "title": "First", "telegram_chat_id": 12345, "created_at": "2026-03-04"},
    ]
    r = c.get("/api/conversations")
    assert r.status_code == 200
    data = r.json()
    assert data["session_telegram_chat_id"] == 12345
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["id"] == "conv-1"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/web/test_conversations.py::test_list_returns_session_telegram_chat_id -v`
Expected: FAIL — response is a list, not a dict

**Step 3: Write minimal implementation**

Update `list_conversations` in `backend/app/web/routes/conversations.py` (lines 38-60):

```python
@router.get("")
async def list_conversations(
    request: Request,
    response: Response,
    ids: str | None = Query(None, description="Comma-separated conversation IDs to filter"),
):
    storage = _get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    session = await storage.get_web_session(session_id)
    session_tg = session.get("telegram_chat_id") if session else None
    all_convs = await storage.list_conversations_by_web_owner(session_id)
    if ids:
        id_set = {i.strip() for i in ids.split(",") if i.strip()}
        matched = [c for c in all_convs if c["id"] in id_set]
    else:
        matched = all_convs
    return {
        "session_telegram_chat_id": session_tg,
        "conversations": [
            {
                "id": c["id"],
                "title": c["title"],
                "telegram_chat_id": c["telegram_chat_id"],
                "created_at": c["created_at"],
            }
            for c in matched
        ],
    }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/web/test_conversations.py::test_list_returns_session_telegram_chat_id -v`
Expected: PASS

**Step 5: Fix broken existing tests**

The existing tests `test_list_without_ids_returns_all_for_session` and `test_list_with_ids_filters_for_session` will break because they expect a list response. Update them:

In `test_list_without_ids_returns_all_for_session`:
```python
def test_list_without_ids_returns_all_for_session(client):
    c, storage = client
    storage.list_conversations_by_web_owner.return_value = [
        {"id": "conv-1", "title": "First", "telegram_chat_id": None, "created_at": "2026-03-03"},
        {"id": "conv-2", "title": "Second", "telegram_chat_id": 123, "created_at": "2026-03-03"},
    ]
    r = c.get("/api/conversations")
    assert r.status_code == 200
    data = r.json()
    assert len(data["conversations"]) == 2
```

In `test_list_with_ids_filters_for_session`:
```python
def test_list_with_ids_filters_for_session(client):
    c, storage = client
    storage.list_conversations_by_web_owner.return_value = [
        {"id": "conv-1", "title": "First", "telegram_chat_id": None, "created_at": "2026-03-03"},
        {"id": "conv-2", "title": "Second", "telegram_chat_id": 123, "created_at": "2026-03-03"},
    ]
    r = c.get("/api/conversations?ids=conv-2")
    assert r.status_code == 200
    data = r.json()
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["id"] == "conv-2"
```

**Step 6: Run all conversations tests**

Run: `cd backend && python -m pytest tests/web/test_conversations.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add backend/app/web/routes/conversations.py backend/tests/web/test_conversations.py
git commit -m "feat: list_conversations returns session_telegram_chat_id"
```

---

### Task 6: Routes — Create conversation auto-links from session

**Files:**
- Modify: `backend/app/web/routes/conversations.py:63-77` (create_conversation)
- Test: `backend/tests/web/test_conversations.py`

**Step 1: Write the failing test**

Add to `backend/tests/web/test_conversations.py`:

```python
def test_create_auto_links_telegram_from_session(client):
    c, storage = client
    storage.get_web_session.return_value = {
        "session_id": "s1", "ua_hash": "h", "ip_prefix": "127.0",
        "created_at": 0, "last_seen_at": 0, "expires_at": 999999999999,
        "rotated_to": None, "revoked_at": None, "telegram_chat_id": 44444,
    }
    storage.create_conversation.return_value = {
        "id": "new-conv", "title": "Test", "telegram_chat_id": 44444,
    }
    r = c.post("/api/conversations", json={"id": "new-conv", "title": "Test"})
    assert r.status_code == 200
    # Verify create_conversation was called with session's telegram_chat_id
    kwargs = storage.create_conversation.await_args.kwargs
    assert kwargs["telegram_chat_id"] == 44444
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/web/test_conversations.py::test_create_auto_links_telegram_from_session -v`
Expected: FAIL — `telegram_chat_id` not in kwargs (create_conversation not called with it)

**Step 3: Write minimal implementation**

Update `create_conversation` route in `backend/app/web/routes/conversations.py` (lines 63-77):

```python
@router.post("")
async def create_conversation(request: Request, response: Response, body: CreateConversationRequest):
    storage = _get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    session = await storage.get_web_session(session_id)
    session_tg = session.get("telegram_chat_id") if session else None
    conv_id = body.id or str(uuid4())
    conv = await storage.create_conversation(
        id=conv_id,
        title=body.title,
        web_owner_session_id=session_id,
        telegram_chat_id=session_tg,
    )
    return {
        "id": conv["id"],
        "title": conv["title"],
        "telegram_chat_id": conv["telegram_chat_id"],
    }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/web/test_conversations.py::test_create_auto_links_telegram_from_session -v`
Expected: PASS

**Step 5: Run all conversations tests**

Run: `cd backend && python -m pytest tests/web/test_conversations.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/app/web/routes/conversations.py backend/tests/web/test_conversations.py
git commit -m "feat: new conversations auto-link telegram from session"
```

---

### Task 7: Routes — Unlink endpoint uses session-level unlink

**Files:**
- Modify: `backend/app/web/routes/conversations.py:145-155` (unlink_telegram)
- Test: `backend/tests/web/test_conversations.py`

**Step 1: Write the failing test**

Add to `backend/tests/web/test_conversations.py`:

```python
def test_unlink_calls_session_level_unlink(client):
    c, storage = client
    c.cookies.set("vulcan_session", "my-sess")
    storage.get_web_session.return_value = {
        "session_id": "my-sess", "ua_hash": "h", "ip_prefix": "127.0",
        "created_at": 0, "last_seen_at": 0, "expires_at": 999999999999,
        "rotated_to": None, "revoked_at": None, "telegram_chat_id": 55555,
    }
    storage.get_conversation.return_value = {
        "id": "conv-1", "web_owner_session_id": "my-sess",
        "telegram_chat_id": 55555, "title": "T", "created_at": "2026-03-04",
    }
    r = c.post("/api/conversations/conv-1/unlink-telegram")
    assert r.status_code == 200
    storage.unlink_telegram_session.assert_awaited_once_with("my-sess")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/web/test_conversations.py::test_unlink_calls_session_level_unlink -v`
Expected: FAIL — `unlink_telegram_session` never called

**Step 3: Write minimal implementation**

Update unlink endpoint in `backend/app/web/routes/conversations.py` (lines 145-155):

```python
@router.post("/{conversation_id}/unlink-telegram")
async def unlink_telegram(
    request: Request,
    response: Response,
    conversation_id: str,
):
    storage = _get_storage(request)
    session_id = await ensure_web_session(request, response, storage)
    await _get_authorized_conversation(storage, conversation_id, session_id)
    await storage.unlink_telegram_session(session_id)
    return {"status": "unlinked"}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/web/test_conversations.py::test_unlink_calls_session_level_unlink -v`
Expected: PASS

**Step 5: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/app/web/routes/conversations.py backend/tests/web/test_conversations.py
git commit -m "feat: unlink endpoint uses session-level unlink"
```

---

### Task 8: Frontend — Update API client for new response format

**Files:**
- Modify: `frontend/src/lib/api.ts:1-10` (fetchConversations)
- Test: `frontend/src/__tests__/useChat.test.ts` (update mocks)

**Step 1: Update `fetchConversations` in `frontend/src/lib/api.ts`**

Change lines 1-10:

```typescript
export async function fetchConversations(ids?: string[]): Promise<{
  session_telegram_chat_id: number | null;
  conversations: { id: string; title: string; telegram_chat_id: number | null; created_at: string }[];
}> {
  const params = ids && ids.length > 0 ? `?ids=${ids.join(",")}` : "";
  const res = await fetch(`/api/conversations${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: fetchConversations returns session_telegram_chat_id"
```

---

### Task 9: Frontend — Update `useChat` hook for session-level Telegram state

**Files:**
- Modify: `frontend/src/hooks/useChat.ts`
- Test: `frontend/src/__tests__/useChat.test.ts`

**Step 1: Update test mocks**

In `frontend/src/__tests__/useChat.test.ts`, update the mock for `fetchConversations` (line 13) to return the new format:

```typescript
vi.mock("@/lib/api", () => ({
  fetchConversations: vi.fn().mockResolvedValue({
    session_telegram_chat_id: null,
    conversations: [],
  }),
  createConversation: vi.fn().mockResolvedValue({ id: "test", title: "test" }),
  fetchMessages: vi.fn().mockResolvedValue([]),
  deleteConversationApi: vi.fn().mockResolvedValue(undefined),
  linkTelegram: vi.fn().mockResolvedValue(undefined),
  unlinkTelegram: vi.fn().mockResolvedValue(undefined),
}));
```

Update the `renderUseChatHook` helper to check for the new mock shape:

```typescript
async function renderUseChatHook() {
  const hook = renderHook(() => useChat());
  await waitFor(() => {
    expect(fetchConversations).toHaveBeenCalled();
  });
  return hook;
}
```

Update the `requestTelegramLink starts polling` test — change `fetchConvsMock` return values to new format:

```typescript
// Mount returns an existing unlinked conversation (new response format)
vi.mocked(fetchConvsMock).mockResolvedValueOnce({
  session_telegram_chat_id: null,
  conversations: [
    { id: CONV_ID, title: "Test", telegram_chat_id: null, created_at: "2026-01-01" },
  ],
});

// ...

// Polling will now return the session as linked
vi.mocked(fetchConvsMock).mockResolvedValue({
  session_telegram_chat_id: 99999,
  conversations: [
    { id: CONV_ID, title: "Test", telegram_chat_id: 99999, created_at: "2026-01-01" },
  ],
});
```

**Step 2: Update `useChat.ts` — add `sessionTelegramChatId` state**

In `frontend/src/hooks/useChat.ts`, add state after `activeIdRef` (line 37):

```typescript
const [sessionTelegramChatId, setSessionTelegramChatId] = useState<number | null>(null);
```

**Step 3: Update mount effect to parse new response format**

Update the `useEffect` at line 70. Change `fetchConversations().then(async (convs) => {` to:

```typescript
fetchConversations()
  .then(async (result) => {
    const convs = result.conversations;
    setSessionTelegramChatId(result.session_telegram_chat_id);
    const mapped = convs.map((c) => ({
      id: c.id,
      title: c.title,
      messages: [],
      createdAt: c.created_at,
      telegram_chat_id: c.telegram_chat_id,
    }));
    setConversations(mapped);
    // ... rest unchanged ...
```

The rest of the mount effect (lines 82-116) stays the same — it references `convs` and `mapped` which still work.

**Step 4: Update `requestTelegramLink` polling to check session state**

Update the polling inside `requestTelegramLink` (line 173-193). Change the `fetchConversations` call to use new format:

```typescript
linkPollRef.current = setInterval(async () => {
  try {
    const result = await fetchConversations();
    if (result.session_telegram_chat_id) {
      setSessionTelegramChatId(result.session_telegram_chat_id);
      setConversations((prev) =>
        prev.map((c) => ({
          ...c,
          telegram_chat_id: result.session_telegram_chat_id,
        }))
      );
      if (linkPollRef.current) {
        clearInterval(linkPollRef.current);
        linkPollRef.current = null;
      }
    }
  } catch {
    // polling errors are non-critical
  }
}, POLL_INTERVAL);
```

**Step 5: Update `unlinkTelegramLink` to clear session state**

Update `unlinkTelegramLink` (lines 205-219):

```typescript
const unlinkTelegramLink = useCallback(() => {
  const convId = activeIdRef.current;
  if (!convId) {
    window.alert("目前沒有可取消連結的對話。");
    return;
  }
  unlinkTelegram(convId).catch((err) =>
    console.error("Telegram unlink failed:", err)
  );
  setSessionTelegramChatId(null);
  setConversations((prev) =>
    prev.map((c) => ({ ...c, telegram_chat_id: null }))
  );
}, []);
```

**Step 6: Update return value**

Change the return object (line 470-484):
- Replace `activeTelegramChatId: conversations.find(...)?.telegram_chat_id ?? null` with `activeTelegramChatId: sessionTelegramChatId`

```typescript
return {
  ...state,
  conversations,
  activeId,
  activeTelegramChatId: sessionTelegramChatId,
  requestTelegramLink,
  unlinkTelegramLink,
  sendMessage,
  newChat,
  loadConversation,
  deleteConversation,
  abort,
};
```

**Step 7: Run frontend tests**

Run: `cd frontend && npx vitest run src/__tests__/useChat.test.ts`
Expected: All PASS

**Step 8: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: All PASS

**Step 9: Commit**

```bash
git add frontend/src/hooks/useChat.ts frontend/src/lib/api.ts frontend/src/__tests__/useChat.test.ts
git commit -m "feat: useChat uses session-level telegram identity"
```

---

### Task 10: Frontend — Add test for session-level Telegram persistence

**Files:**
- Test: `frontend/src/__tests__/useChat.test.ts`

**Step 1: Write the test**

Add to `frontend/src/__tests__/useChat.test.ts`:

```typescript
it("activeTelegramChatId reflects session-level state from API", async () => {
  const { fetchConversations: fetchConvsMock } = await import("@/lib/api");

  vi.mocked(fetchConvsMock).mockResolvedValueOnce({
    session_telegram_chat_id: 12345,
    conversations: [
      { id: "c1", title: "Test", telegram_chat_id: 12345, created_at: "2026-01-01" },
    ],
  });

  const { result } = renderHook(() => useChat());
  await waitFor(() => {
    expect(fetchConvsMock).toHaveBeenCalled();
  });

  expect(result.current.activeTelegramChatId).toBe(12345);

  // Reset mock
  vi.mocked(fetchConvsMock).mockResolvedValue({
    session_telegram_chat_id: null,
    conversations: [],
  });
});
```

**Step 2: Run test**

Run: `cd frontend && npx vitest run src/__tests__/useChat.test.ts`
Expected: All PASS

**Step 3: Commit**

```bash
git add frontend/src/__tests__/useChat.test.ts
git commit -m "test: verify session-level telegram identity in useChat"
```

---

### Task 11: Run full test suite and verify

**Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All PASS

**Step 2: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: All PASS

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address test regressions from persistent telegram identity"
```
