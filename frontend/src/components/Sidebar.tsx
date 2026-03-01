"use client";

import type { Conversation } from "@/lib/types";
import { useLocale } from "@/i18n";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onNewChat: () => void;
  onSelect: (conv: Conversation) => void;
  onDelete: (id: string) => void;
  onClose?: () => void;
}

export function Sidebar({
  conversations,
  activeId,
  onNewChat,
  onSelect,
  onDelete,
  onClose,
}: SidebarProps) {
  const { t } = useLocale();

  return (
    <div className="flex flex-col h-full bg-gray-900 text-white">
      <div className="p-3">
        <button
          onClick={() => {
            onNewChat();
            onClose?.();
          }}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-gray-600 hover:bg-gray-700 transition-colors text-sm"
        >
          <span>+</span>
          <span>{t.newChat}</span>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`group flex items-center gap-1 px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
              activeId === conv.id
                ? "bg-gray-700"
                : "hover:bg-gray-800"
            }`}
            onClick={() => {
              onSelect(conv);
              onClose?.();
            }}
          >
            <span className="flex-1 truncate text-gray-300">
              {conv.title}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity text-xs"
            >
              &#10005;
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
