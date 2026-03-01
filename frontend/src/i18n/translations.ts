export type Locale = "en" | "zh-TW";

export const translations = {
  en: {
    // ChatInput
    inputPlaceholder: "Ask anything...",
    send: "Send",
    // ChatPanel empty state
    emptyTitle: "Web Search Chatbot",
    emptySubtitle: "Ask me anything. I can search the web for the latest info.",
    // Sidebar
    newChat: "New Chat",
    // AgentThinking
    searchingWeb: "Searching the web",
    answeringDirectly: "Answering directly",
    // SearchProgress
    results: "results",
    // CitationList
    sources: "Sources",
    // ChatLayout
    appTitle: "Web Search Chatbot",
  },
  "zh-TW": {
    inputPlaceholder: "輸入任何問題...",
    send: "傳送",
    emptyTitle: "網路搜尋聊天機器人",
    emptySubtitle: "問我任何問題，我可以搜尋網路取得最新資訊。",
    newChat: "新對話",
    searchingWeb: "正在搜尋網路",
    answeringDirectly: "直接回答",
    results: "筆結果",
    sources: "參考來源",
    appTitle: "網路搜尋聊天機器人",
  },
} as const;

export type TranslationKeys = keyof typeof translations.en;
