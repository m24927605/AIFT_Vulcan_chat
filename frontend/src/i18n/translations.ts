export type Locale = "en" | "zh-TW";

export const translations = {
  en: {
    // ChatInput
    inputPlaceholder: "Ask anything...",
    send: "Send",
    // ChatPanel empty state
    emptyTitle: "Web Search Chatbot",
    emptySubtitle: "Ask me anything. I'll search the web or answer directly based on your question.",
    // Sidebar
    newChat: "New Chat",
    // AgentThinking
    searchingWeb: "Searching the web",
    answeringDirectly: "Answering directly",
    // SearchBadge (past tense, for completed messages)
    searchedWeb: "Searched the web",
    answeredDirectly: "Answered directly",
    // SearchProgress
    results: "results",
    // CitationList
    sources: "Sources",
    // ChatLayout
    appTitle: "Web Search Chatbot",
    // Telegram
    telegramLinking: "Telegram Linking",
    telegramBotLink: "Open Telegram Bot",
    telegramHint: "Click \"Get Link Code\", open Telegram Bot, tap \"Start Linking\", and enter the 8-digit code within 10 minutes.",
    telegramRequestCode: "Get Link Code",
    telegramLinked: "Linked:",
    telegramAutoSync: "Auto-sync to Telegram enabled",
    telegramUnlink: "Unlink",
    viaTelegram: "via Telegram",
    // Onboarding Tour
    tourStep: "Step",
    tourOf: "of",
    tourSkip: "Skip",
    tourNext: "Next",
    tourPrev: "Back",
    tourDone: "Got it!",
    tourStep1Title: "Start a conversation",
    tourStep1Desc: "Type any question here. AI will decide whether to search the web or answer directly based on your question. Press Enter to send.",
    tourStep2Title: "Your conversations",
    tourStep2Desc: "All conversations are saved here. Click to switch, hover to delete.",
    tourStep3Title: "Sync with Telegram",
    tourStep3Desc: "Click \"Get Link Code\", open Telegram Bot, tap \"Start Linking\", and enter the 8-digit code with the numeric keypad.",
    tourStep4Title: "You're all set!",
    tourStep4Desc: "AI can search the web for real-time answers with cited sources. Your conversations sync between web and Telegram in real time.",
    // Footer disclaimer
    disclaimer: "This is a demo project for academic purposes only. Not a commercial service. AI responses may be inaccurate — please verify important information. Conversations are stored on the server for functionality; no data is shared with third parties.",
    // Verification
    verificationConsistent: "Verified consistent",
    verificationInconsistent: "Inconsistency detected",
    verificationSuggestion: "Suggestion",
  },
  "zh-TW": {
    inputPlaceholder: "輸入任何問題...",
    send: "傳送",
    emptyTitle: "網路搜尋聊天機器人",
    emptySubtitle: "問我任何問題，我會根據內容搜尋網路或直接回答。",
    newChat: "新對話",
    searchingWeb: "正在搜尋網路",
    answeringDirectly: "直接回答",
    searchedWeb: "已搜尋網路",
    answeredDirectly: "已直接回答",
    results: "筆結果",
    sources: "參考來源",
    appTitle: "網路搜尋聊天機器人",
    telegramLinking: "Telegram 連結",
    telegramBotLink: "開啟 Telegram Bot",
    telegramHint: "點擊「取得驗證碼」後，開啟 Telegram Bot 並按「開始綁定」，用數字鍵盤輸入 8 碼驗證碼（10 分鐘內有效）。",
    telegramRequestCode: "取得驗證碼",
    telegramLinked: "已連結：",
    telegramAutoSync: "已啟用自動同步到 Telegram",
    telegramUnlink: "取消連結",
    viaTelegram: "來自 Telegram",
    // Onboarding Tour
    tourStep: "步驟",
    tourOf: "/",
    tourSkip: "跳過",
    tourNext: "下一步",
    tourPrev: "上一步",
    tourDone: "開始使用！",
    tourStep1Title: "開始對話",
    tourStep1Desc: "在這裡輸入任何問題，AI 會根據內容決定搜尋網路或直接回答。按 Enter 即可送出。",
    tourStep2Title: "你的對話紀錄",
    tourStep2Desc: "所有對話都會保存在這裡，點擊切換，滑過可刪除。",
    tourStep3Title: "同步到 Telegram",
    tourStep3Desc: "先點「取得驗證碼」，再到 Telegram Bot 按「開始綁定」，用數字鍵盤輸入 8 碼驗證碼完成同步。",
    tourStep4Title: "準備就緒！",
    tourStep4Desc: "AI 可搜尋網路取得即時解答與引用來源，你的對話會在網頁和 Telegram 之間即時同步。",
    // Footer disclaimer
    disclaimer: "本網站為學術展示專案，非商業服務。AI 回覆可能不準確，重要資訊請自行查證。對話內容儲存於伺服器以提供服務功能，不會與第三方分享。",
    // Verification
    verificationConsistent: "驗證一致",
    verificationInconsistent: "發現不一致",
    verificationSuggestion: "建議",
  },
} as const;

export type TranslationKeys = keyof typeof translations.en;
