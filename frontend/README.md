# Vulcan Frontend

Web UI for the Web Search Chatbot, built with Next.js 16, React 19, TypeScript, and Tailwind CSS.

## Setup

```bash
npm install
cp .env.example .env.local
# BACKEND_URL defaults to http://localhost:8000 (server-side only, used by Next.js rewrites)
npm run dev
```

Open http://localhost:3000

## Structure

```
app/                    # Next.js App Router (layout, page, globals.css)
src/
├── components/         # React components
│   ├── ChatLayout.tsx  # Overall layout: sidebar + chat area
│   ├── ChatPanel.tsx   # Message list + empty state
│   ├── ChatInput.tsx   # Input box (Enter to send)
│   ├── Sidebar.tsx     # Conversations + Telegram settings
│   ├── MessageBubble.tsx
│   ├── StreamingText.tsx
│   ├── AgentThinking.tsx
│   ├── SearchProgress.tsx
│   ├── CitationList.tsx / CitationCard.tsx
│   ├── SearchBadge.tsx
│   └── OnboardingTour.tsx  # 4-step onboarding for new users
├── hooks/
│   ├── useChat.ts      # Chat state + conversation management
│   └── useSSE.ts       # SSE streaming connection
├── i18n/
│   └── translations.ts # en + zh-TW translations
└── lib/
    └── types.ts        # TypeScript type definitions
```

## Key Features

- SSE streaming with real-time token rendering
- Agent thinking process visualization
- Clickable citation sources
- Multi-conversation persistence (API-backed)
- Telegram linking via bot button flow (`/start` -> `Start Linking` -> inline numpad) or direct code entry (`/link <code>`)
- 4-step onboarding tour (localStorage-based)
- i18n (English / 繁體中文)
- Responsive mobile design
- Dark mode
