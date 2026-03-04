import { getCsrfToken } from "./csrf";

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

export async function createConversation(
  id: string,
  title: string
): Promise<{ id: string; title: string; telegram_chat_id: number | null }> {
  const res = await fetch(`/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfToken() },
    body: JSON.stringify({ id, title }),
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchMessages(
  conversationId: string,
  afterId?: number
): Promise<
  {
    id: number;
    role: string;
    content: string;
    source: string;
    search_used: boolean | null;
    citations: { index: number; title: string; url: string; snippet: string }[] | null;
    created_at: string;
  }[]
> {
  const params = afterId != null ? `?after_id=${afterId}` : "";
  const res = await fetch(
    `/api/conversations/${conversationId}/messages${params}`,
    { credentials: "include" }
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteConversationApi(
  conversationId: string
): Promise<void> {
  const res = await fetch(`/api/conversations/${conversationId}`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": getCsrfToken() },
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function linkTelegram(
  conversationId: string
): Promise<{ status: string; code: string; expires_in_seconds: number }> {
  const res = await fetch(
    `/api/conversations/${conversationId}/telegram-link/request`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": getCsrfToken() },
      credentials: "include",
    }
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function unlinkTelegram(
  conversationId: string
): Promise<void> {
  const res = await fetch(
    `/api/conversations/${conversationId}/unlink-telegram`,
    { method: "POST", headers: { "X-CSRF-Token": getCsrfToken() }, credentials: "include" }
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}
