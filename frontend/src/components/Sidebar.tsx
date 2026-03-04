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
  activeTelegramChatId: number | null;
  onRequestTelegramLink: () => void;
  onUnlinkTelegram: () => void;
}

export function Sidebar({
  conversations,
  activeId,
  onNewChat,
  onSelect,
  onDelete,
  onClose,
  activeTelegramChatId,
  onRequestTelegramLink,
  onUnlinkTelegram,
}: SidebarProps) {
  const { t } = useLocale();

  return (
    <div className="flex flex-col h-full bg-gray-900 text-white">
      <div className="flex-none p-3 bg-gray-900 border-b border-gray-700">
        <button
          onClick={() => {
            onNewChat();
            onClose?.();
          }}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-gray-800 border border-gray-600 hover:bg-gray-700 transition-colors text-sm text-white font-medium"
        >
          <span>+</span>
          <span>{t.newChat}</span>
        </button>
      </div>
      <div data-tour="conversation-list" className="flex-1 min-h-0 overflow-y-auto px-2 pt-2 pb-2 space-y-0.5">
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

      {/* Telegram section */}
      <div data-tour="telegram-setup" className="flex-none p-3 border-t border-gray-700">
        <a
          href="https://t.me/michaelvulcanchatbot?start=link"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors mb-2"
        >
          <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 fill-current" aria-hidden="true">
            <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
          </svg>
          {t.telegramBotLink}
        </a>

        <label className="block text-xs text-gray-400 mb-1">
          {t.telegramLinking}
        </label>

        {activeTelegramChatId ? (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-green-400">
                {t.telegramLinked} {activeTelegramChatId}
              </span>
              <button
                onClick={onUnlinkTelegram}
                className="text-[10px] text-gray-500 hover:text-red-400 transition-colors"
              >
                {t.telegramUnlink}
              </button>
            </div>
            <p className="text-[10px] text-green-400/70 mt-0.5">
              {t.telegramAutoSync}
            </p>
          </div>
        ) : (
          <div>
            <button
              onClick={onRequestTelegramLink}
              className="text-xs px-2.5 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              {t.telegramRequestCode}
            </button>
            <p className="text-[10px] text-gray-500 mt-1">
              {t.telegramHint}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
