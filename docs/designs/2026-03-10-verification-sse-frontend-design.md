# Verification SSE Event Frontend Integration

## Goal

Connect the backend `verification` SSE event to the frontend chat flow so users see verification results after an assistant response completes.

## Constraints

- No backend API/DB changes — verification is session-transient (option C)
- Maintain existing UI style and component patterns
- Minimal state changes

## Data Flow

```
Backend SSE "verification" event
  → useSSE.ts: case "verification" → callbacks.onVerification(data)
  → useChat.ts: setState({ verification: data })
  → ChatLayout → ChatPanel → MessageBubble
  → VerificationBadge component (after CitationList)
```

## Types

```ts
// types.ts
export interface VerificationData {
  is_consistent: boolean;
  confidence: number;
  issues: string[];
  suggestion: string;
}
```

Added to `SSEEvent` union. Added to `ChatState` as `verification: VerificationData | null`.

## State Lifecycle

- **Reset to null**: on `sendMessage` (with planner/searchStatus), `newChat`, `loadConversation`
- **Set**: on `onVerification` callback during SSE stream
- **Not persisted**: lost on reload/conversation switch (acceptable limitation)

## UI: VerificationBadge Component

Hybrid badge/panel — adapts visual weight based on `is_consistent`:

### is_consistent = true
- Compact inline badge (green)
- Checkmark icon + "Verified consistent" + confidence percentage
- Low visual noise, no expand/collapse needed

### is_consistent = false
- Bordered panel (amber/orange)
- Warning icon + "Inconsistency detected" + confidence
- Issues listed as bullet points
- Suggestion shown as supplementary text
- Collapsible (expanded by default)

### Display Conditions
- Only on the **latest assistant message**
- Only when **not streaming** (after response completes)
- Only when `verification !== null`

### Placement
- Inside `MessageBubble`, after `<CitationList>`, before closing `</div>`

## i18n Keys

- `verificationConsistent` — "Verified consistent" / "驗證一致"
- `verificationInconsistent` — "Inconsistency detected" / "發現不一致"
- `verificationConfidence` — "Confidence" / "信心度"
- `verificationSuggestion` — "Suggestion" / "建議"

## Files Modified

1. `frontend/src/lib/types.ts` — VerificationData interface, SSEEvent union
2. `frontend/src/hooks/useSSE.ts` — onVerification callback + switch case
3. `frontend/src/hooks/useChat.ts` — verification in ChatState, callback wiring, resets
4. `frontend/src/components/ChatLayout.tsx` — pass verification prop
5. `frontend/src/components/ChatPanel.tsx` — accept + forward verification prop
6. `frontend/src/components/MessageBubble.tsx` — accept + render VerificationBadge
7. `frontend/src/components/VerificationBadge.tsx` — **new** component
8. `frontend/src/i18n/translations.ts` — verification translation keys

## Tests

1. `useSSE.test.ts` — verification event triggers onVerification callback
2. `useChat.test.ts` — verification state set on event, reset on sendMessage/newChat
3. `VerificationBadge.test.tsx` — **new**: consistent badge, inconsistent panel, null hides, issues rendered
