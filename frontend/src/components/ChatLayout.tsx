"use client";

import { useState } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatPanel } from "./ChatPanel";
import { Sidebar } from "./Sidebar";

export function ChatLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const {
    messages,
    isLoading,
    streamingContent,
    planner,
    searchStatus,
    citations,
    conversations,
    activeId,
    sendMessage,
    newChat,
    loadConversation,
    deleteConversation,
  } = useChat();

  return (
    <div className="flex h-screen bg-white dark:bg-gray-900">
      {/* Desktop sidebar */}
      <div className="hidden md:block w-64 flex-shrink-0 border-r border-gray-200 dark:border-gray-700">
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onNewChat={newChat}
          onSelect={loadConversation}
          onDelete={deleteConversation}
        />
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="w-64">
            <Sidebar
              conversations={conversations}
              activeId={activeId}
              onNewChat={newChat}
              onSelect={loadConversation}
              onDelete={deleteConversation}
              onClose={() => setSidebarOpen(false)}
            />
          </div>
          <div
            className="flex-1 bg-black/50"
            onClick={() => setSidebarOpen(false)}
          />
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <button
            className="md:hidden text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            onClick={() => setSidebarOpen(true)}
          >
            &#9776;
          </button>
          <h1 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
            Web Search Chatbot
          </h1>
        </div>

        <ChatPanel
          messages={messages}
          isLoading={isLoading}
          streamingContent={streamingContent}
          planner={planner}
          searchStatus={searchStatus}
          citations={citations}
          onSend={sendMessage}
        />
      </div>
    </div>
  );
}
