# Verification SSE Frontend Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display backend verification SSE events in the frontend chat UI, showing consistency status after each assistant response.

**Architecture:** Add `VerificationData` type, wire through useSSE → useChat → ChatPanel → MessageBubble → new VerificationBadge component. Session-transient state only (option C) — no backend/DB changes.

**Tech Stack:** React, TypeScript, Tailwind CSS, vitest, @testing-library/react

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/src/lib/types.ts` | Add `VerificationData` interface + SSEEvent union member |
| Modify | `frontend/src/hooks/useSSE.ts` | Add `onVerification` callback + switch case |
| Modify | `frontend/src/hooks/useChat.ts` | Add `verification` to ChatState, wire callback, resets |
| Modify | `frontend/src/components/ChatLayout.tsx` | Destructure + pass `verification` prop |
| Modify | `frontend/src/components/ChatPanel.tsx` | Accept + forward `verification` prop |
| Modify | `frontend/src/components/MessageBubble.tsx` | Accept `verification`, render VerificationBadge |
| Create | `frontend/src/components/VerificationBadge.tsx` | Hybrid badge/panel display component |
| Modify | `frontend/src/i18n/translations.ts` | Add verification i18n keys |
| Modify | `frontend/src/__tests__/useSSE.test.ts` | Test verification event parsing |
| Modify | `frontend/src/__tests__/useChat.test.ts` | Test verification state + reset |
| Create | `frontend/src/__tests__/VerificationBadge.test.tsx` | Test all rendering states |

---

## Chunk 1: Types + Data Layer

### Task 1: Add VerificationData type and SSE event union member

**Files:**
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Add VerificationData interface and SSEEvent member**

Add after `CitationsData`:

```ts
export interface VerificationData {
  is_consistent: boolean;
  confidence: number;
  issues: string[];
  suggestion: string;
}
```

Add to `SSEEvent` union:

```ts
  | { event: "verification"; data: VerificationData }
```

- [ ] **Step 2: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add VerificationData type for SSE verification event"
```

---

### Task 2: Wire verification event through useSSE

**Files:**
- Modify: `frontend/src/hooks/useSSE.ts`
- Modify: `frontend/src/__tests__/useSSE.test.ts`

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/__tests__/useSSE.test.ts`:

```ts
it("parses verification event", async () => {
  const sse =
    'event: verification\ndata: {"is_consistent":true,"confidence":0.92,"issues":[],"suggestion":""}\n\nevent: done\ndata: {}\n\n';
  mockFetchSSE(sse);

  const onVerification = vi.fn();
  const onDone = vi.fn();
  const { result } = renderHook(() => useSSE());

  await act(async () => {
    await result.current.sendMessage("test", [], { onVerification, onDone });
  });

  expect(onVerification).toHaveBeenCalledWith({
    is_consistent: true,
    confidence: 0.92,
    issues: [],
    suggestion: "",
  });
  expect(onDone).toHaveBeenCalledOnce();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/useSSE.test.ts`
Expected: FAIL — `onVerification` is not a valid callback / never called

- [ ] **Step 3: Implement — add verification to useSSE**

In `frontend/src/hooks/useSSE.ts`:

1. Add `VerificationData` to imports from `@/lib/types`:
```ts
import type {
  PlannerData,
  SearchingData,
  ChunkData,
  CitationsData,
  VerificationData,
} from "@/lib/types";
```

2. Add to `SSECallbacks` interface:
```ts
  onVerification?: (data: VerificationData) => void;
```

3. Add case in switch statement (after `search_failed`, before `done`):
```ts
                  case "verification":
                    callbacks.onVerification?.(data);
                    break;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/useSSE.test.ts`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useSSE.ts frontend/src/__tests__/useSSE.test.ts
git commit -m "feat: handle verification SSE event in useSSE hook"
```

---

### Task 3: Add verification state to useChat

**Files:**
- Modify: `frontend/src/hooks/useChat.ts`
- Modify: `frontend/src/__tests__/useChat.test.ts`

- [ ] **Step 1: Write the failing tests — verification state defaults, resets on newChat and loadConversation**

Add to `frontend/src/__tests__/useChat.test.ts`:

```ts
it("verification state is null by default and resets on newChat", async () => {
  const { result } = await renderUseChatHook();

  expect(result.current.verification).toBeNull();

  act(() => {
    result.current.newChat();
  });

  expect(result.current.verification).toBeNull();
});

it("verification state resets on loadConversation", async () => {
  const { fetchMessages: fetchMsgsMock } = await import("@/lib/api");
  vi.mocked(fetchMsgsMock).mockResolvedValue([]);
  const { result } = await renderUseChatHook();

  expect(result.current.verification).toBeNull();

  await act(async () => {
    await result.current.loadConversation({
      id: "conv-1",
      title: "Test",
      messages: [],
      createdAt: "2026-01-01",
    });
  });

  expect(result.current.verification).toBeNull();

  // Reset mocks
  vi.mocked(fetchMsgsMock).mockResolvedValue([]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/useChat.test.ts`
Expected: FAIL — `verification` property doesn't exist on result.current

- [ ] **Step 3: Implement — add verification to ChatState**

In `frontend/src/hooks/useChat.ts`:

1. Add `VerificationData` to imports:
```ts
import type {
  ChatMessage,
  CitationItem,
  PlannerData,
  SearchingData,
  VerificationData,
} from "@/lib/types";
```

2. Add to `ChatState` interface:
```ts
  verification: VerificationData | null;
```

3. Add to `INITIAL_CHAT_STATE`:
```ts
  verification: null,
```

4. In `sendMessage` callback, reset verification in the initial setState (line ~336, alongside planner/searchStatus reset):
```ts
      verification: null,
```

5. Add `onVerification` callback in the SSE callbacks object (after `onCitations`):
```ts
          onVerification: (data) => {
            setState((prev) => ({ ...prev, verification: data }));
          },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/useChat.test.ts`
Expected: All PASS

- [ ] **Step 5: Verify types still compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useChat.ts frontend/src/__tests__/useChat.test.ts
git commit -m "feat: add verification state to useChat hook"
```

---

## Chunk 2: i18n + UI Component

### Task 4: Add i18n translation keys

**Files:**
- Modify: `frontend/src/i18n/translations.ts`

- [ ] **Step 1: Add English keys**

Add after `disclaimer` in the `en` object:

```ts
    // Verification
    verificationConsistent: "Verified consistent",
    verificationInconsistent: "Inconsistency detected",
    verificationSuggestion: "Suggestion",
```

- [ ] **Step 2: Add Chinese keys**

Add after `disclaimer` in the `zh-TW` object:

```ts
    // Verification
    verificationConsistent: "驗證一致",
    verificationInconsistent: "發現不一致",
    verificationSuggestion: "建議",
```

- [ ] **Step 3: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/translations.ts
git commit -m "feat: add verification i18n keys (en + zh-TW)"
```

---

### Task 5: Create VerificationBadge component

**Files:**
- Create: `frontend/src/components/VerificationBadge.tsx`
- Create: `frontend/src/__tests__/VerificationBadge.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/__tests__/VerificationBadge.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VerificationBadge } from "@/components/VerificationBadge";

describe("VerificationBadge", () => {
  it("renders nothing when verification is null", () => {
    const { container } = render(<VerificationBadge verification={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders compact badge when is_consistent is true", () => {
    render(
      <VerificationBadge
        verification={{
          is_consistent: true,
          confidence: 0.95,
          issues: [],
          suggestion: "",
        }}
      />
    );

    expect(screen.getByText(/95%/)).toBeDefined();
    // Should NOT show issues section
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("renders expanded panel when is_consistent is false", () => {
    render(
      <VerificationBadge
        verification={{
          is_consistent: false,
          confidence: 0.6,
          issues: ["Source A contradicts source B", "Date mismatch"],
          suggestion: "Cross-check with official records",
        }}
      />
    );

    expect(screen.getByText(/60%/)).toBeDefined();
    expect(screen.getByText("Source A contradicts source B")).toBeDefined();
    expect(screen.getByText("Date mismatch")).toBeDefined();
    expect(screen.getByText("Cross-check with official records")).toBeDefined();
  });

  it("does not render issues list when is_consistent is true even if issues exist", () => {
    render(
      <VerificationBadge
        verification={{
          is_consistent: true,
          confidence: 0.88,
          issues: [],
          suggestion: "",
        }}
      />
    );

    expect(screen.queryByRole("list")).toBeNull();
  });

  it("does not render suggestion text when suggestion is empty", () => {
    render(
      <VerificationBadge
        verification={{
          is_consistent: false,
          confidence: 0.5,
          issues: ["Problem found"],
          suggestion: "",
        }}
      />
    );

    expect(screen.getByText("Problem found")).toBeDefined();
    // Suggestion label should not appear
    expect(screen.queryByText(/Suggestion/i)).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/__tests__/VerificationBadge.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement VerificationBadge component**

Create `frontend/src/components/VerificationBadge.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { VerificationData } from "@/lib/types";
import { useLocale } from "@/i18n";

interface VerificationBadgeProps {
  verification: VerificationData | null;
}

export function VerificationBadge({ verification }: VerificationBadgeProps) {
  const { t } = useLocale();
  const [expanded, setExpanded] = useState(true);

  if (!verification) return null;

  const pct = `${Math.round(verification.confidence * 100)}%`;

  if (verification.is_consistent) {
    return (
      <div className="mt-3">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300">
          <span>✓</span>
          <span>{t.verificationConsistent}</span>
          <span className="text-green-500 dark:text-green-400">({pct})</span>
        </span>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
      >
        <span>⚠</span>
        <span className="font-medium">{t.verificationInconsistent}</span>
        <span className="text-amber-500 dark:text-amber-400">({pct})</span>
        <span className="ml-auto">{expanded ? "▼" : "▶"}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-2.5 text-xs text-amber-700 dark:text-amber-300 space-y-1.5">
          {verification.issues.length > 0 && (
            <ul className="list-disc list-inside space-y-0.5">
              {verification.issues.map((issue, i) => (
                <li key={i}>{issue}</li>
              ))}
            </ul>
          )}
          {verification.suggestion && (
            <p className="text-amber-600 dark:text-amber-400">
              <span className="font-medium">{t.verificationSuggestion}:</span>{" "}
              {verification.suggestion}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/__tests__/VerificationBadge.test.tsx`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/VerificationBadge.tsx frontend/src/__tests__/VerificationBadge.test.tsx
git commit -m "feat: create VerificationBadge component with tests"
```

---

## Chunk 3: Wire Through Component Tree

### Task 6: Pass verification through ChatLayout → ChatPanel → MessageBubble

**Files:**
- Modify: `frontend/src/components/ChatLayout.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`
- Modify: `frontend/src/components/MessageBubble.tsx`

- [ ] **Step 1: Update ChatLayout to pass verification**

In `frontend/src/components/ChatLayout.tsx`:

1. Add `verification` to the destructured useChat return (line ~20-36):
```ts
    verification,
```

2. Add `verification` prop to ChatPanel (line ~92-100):
```tsx
        <ChatPanel
          messages={messages}
          isLoading={isLoading}
          streamingContent={streamingContent}
          planner={planner}
          searchStatus={searchStatus}
          citations={citations}
          verification={verification}
          onSend={sendMessage}
        />
```

- [ ] **Step 2: Update ChatPanel to accept and forward verification**

In `frontend/src/components/ChatPanel.tsx`:

1. Add `VerificationData` to type imports:
```ts
import type { ChatMessage, CitationItem, PlannerData, SearchingData, VerificationData } from "@/lib/types";
```

2. Add to `ChatPanelProps`:
```ts
  verification: VerificationData | null;
```

3. Destructure `verification` in the component parameters.

4. Pass `verification` to MessageBubble — **only on the last assistant message when not streaming**. Update the `messages.map(...)` block (lines ~46-60) to add the `verification` prop. **Keep the existing streaming placeholder block (lines 62-71) unchanged.**

In the `messages.map(...)`, update the return to include `verification`:

```tsx
        {messages.map((msg, i) => {
          const isLast = i === messages.length - 1;
          const isAssistantStreaming =
            isLast && msg.role === "assistant" && isLoading;

          // Show verification only on the latest assistant message, not while streaming
          const showVerification =
            isLast && msg.role === "assistant" && !isLoading;

          return (
            <MessageBubble
              key={i}
              message={msg}
              isStreaming={isAssistantStreaming}
              streamingContent={isAssistantStreaming ? streamingContent : undefined}
              citations={msg.role === "assistant" ? (msg.citations || []) : []}
              verification={showVerification ? verification : null}
            />
          );
        })}

        {/* KEEP THIS BLOCK UNCHANGED — streaming placeholder when assistant hasn't started */}
        {isLoading && messages[messages.length - 1]?.role === "user" && (
          <MessageBubble
            message={{ role: "assistant", content: "" }}
            isStreaming={true}
            streamingContent={streamingContent}
            planner={planner}
            searchStatus={searchStatus}
            citations={[]}
          />
        )}
```

- [ ] **Step 3: Update MessageBubble to render VerificationBadge**

In `frontend/src/components/MessageBubble.tsx`:

1. Add imports:
```ts
import type { ChatMessage, CitationItem, PlannerData, SearchingData, VerificationData } from "@/lib/types";
import { VerificationBadge } from "./VerificationBadge";
```

2. Add to `MessageBubbleProps`:
```ts
  verification?: VerificationData | null;
```

3. Destructure `verification` in parameters (default to `null`):
```ts
  verification = null,
```

4. Add `<VerificationBadge>` after `<CitationList>` in the assistant branch (after line 68):
```tsx
            {!isStreaming && <CitationList citations={citations} />}
            {!isStreaming && <VerificationBadge verification={verification} />}
```

- [ ] **Step 4: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Run all existing tests to check for regressions**

Run: `cd frontend && npx vitest run`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ChatLayout.tsx frontend/src/components/ChatPanel.tsx frontend/src/components/MessageBubble.tsx
git commit -m "feat: wire verification through ChatLayout → ChatPanel → MessageBubble"
```

---

## Chunk 4: Final Verification

### Task 7: Run full test suite + type check

- [ ] **Step 1: Run full test suite**

Run: `cd frontend && npx vitest run`
Expected: All PASS

- [ ] **Step 2: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Quick visual sanity check (manual)**

Start dev server and confirm:
1. Send a message — if backend sends verification event, badge/panel appears after response
2. No verification → no empty frame rendered
3. Start new message → verification clears

---

## Summary

**Tasks:** 7 total (3 data layer, 1 i18n, 1 component, 1 wiring, 1 verification)
**New files:** 2 (`VerificationBadge.tsx`, `VerificationBadge.test.tsx`)
**Modified files:** 9
**No backend changes.**
