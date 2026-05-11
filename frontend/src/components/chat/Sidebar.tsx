"use client";

import { memo, useDeferredValue, useMemo, useState } from "react";

import type { ChatSessionSummary } from "@/lib/chat";

type SidebarProps = {
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapse: () => void;
  onCloseMobile: () => void;
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onDeleteSession: (sessionId: string) => void;
  themeMode: "dark" | "light";
  botName: string;
};

function formatSessionDate(timestamp: string | null) {
  if (!timestamp) {
    return "Just now";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

function SidebarComponent({
  sessions,
  activeSessionId,
  collapsed,
  mobileOpen,
  onToggleCollapse,
  onCloseMobile,
  onNewChat,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
  themeMode,
  botName,
}: SidebarProps) {
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState("");
  const deferredSearch = useDeferredValue(search);

  const filteredSessions = useMemo(() => {
    const query = deferredSearch.trim().toLowerCase();
    if (!query) {
      return sessions;
    }
    return sessions.filter((session) =>
      (session.title ?? "Untitled chat").toLowerCase().includes(query),
    );
  }, [deferredSearch, sessions]);

  const buttonChrome =
    themeMode === "dark"
      ? "border-white/10 text-slate-300 hover:border-white/20 hover:text-white"
      : "border-slate-200 text-slate-600 hover:border-slate-300 hover:text-slate-950";

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-slate-950/60 backdrop-blur-sm transition md:hidden ${
          mobileOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onCloseMobile}
      />

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex h-full w-[88vw] max-w-[340px] flex-col border-r transition-transform duration-300 md:static md:h-auto md:max-w-none ${
          themeMode === "dark"
            ? "border-white/10 bg-[linear-gradient(180deg,rgba(5,10,25,0.98),rgba(2,6,23,0.96))]"
            : "border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.98))]"
        } ${mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"} ${
          collapsed ? "md:w-[88px]" : "md:w-[320px]"
        }`}
      >
        <div className="flex items-center justify-between px-4 py-4">
          <button
            aria-label="Start a new chat"
            className="flex flex-1 items-center justify-center gap-2 rounded-2xl bg-[var(--chat-brand)] px-4 py-3 text-sm font-semibold text-white shadow-[0_18px_40px_color-mix(in_srgb,var(--chat-brand)_32%,transparent)] transition hover:brightness-110"
            onClick={onNewChat}
            type="button"
          >
            <span>+</span>
            {!collapsed ? <span>New chat</span> : null}
          </button>
          <button
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={`ml-2 hidden rounded-2xl border px-3 py-3 transition md:inline-flex ${buttonChrome}`}
            onClick={onToggleCollapse}
            type="button"
          >
            {collapsed ? "Expand" : "Collapse"}
          </button>
        </div>

        {!collapsed ? (
          <div className="px-4">
            <div
              className={`rounded-3xl border p-4 ${
                themeMode === "dark"
                  ? "border-white/10 bg-white/[0.04]"
                  : "border-slate-200 bg-white shadow-sm"
              }`}
            >
              <p className="text-xs uppercase tracking-[0.35em] text-slate-400">Assistant</p>
              <h2
                className={`mt-2 text-xl font-semibold ${
                  themeMode === "dark" ? "text-white" : "text-slate-950"
                }`}
              >
                {botName}
              </h2>
              <p className="mt-2 text-sm text-slate-400">
                Browse session history, reopen threads, and keep grounded answers close at hand.
              </p>
            </div>
          </div>
        ) : null}

        {!collapsed ? (
          <div className="px-4 pt-4">
            <input
              aria-label="Search chat history"
              className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition focus:border-[var(--chat-brand)]/40 ${
                themeMode === "dark"
                  ? "border-white/10 bg-white/[0.04] text-white placeholder:text-slate-500"
                  : "border-slate-200 bg-white text-slate-950 placeholder:text-slate-400"
              }`}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search chat history"
              value={search}
            />
          </div>
        ) : null}

        <div className="mt-4 flex-1 overflow-y-auto px-3 pb-4">
          {!filteredSessions.length ? (
            <div className="rounded-3xl border border-dashed border-white/10 px-4 py-6 text-center text-sm text-slate-400">
              {sessions.length
                ? "No sessions match your search."
                : "No chats yet. Start your first conversation."}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredSessions.map((session) => {
                const active = session.id === activeSessionId;
                const title = session.title ?? "Untitled chat";

                return (
                  <div
                    key={session.id}
                    className={`rounded-2xl border px-3 py-3 transition ${
                      active
                        ? "border-[var(--chat-brand)]/25 bg-[var(--chat-brand)]/12"
                        : themeMode === "dark"
                          ? "border-transparent bg-white/[0.03] hover:border-white/10 hover:bg-white/[0.05]"
                          : "border-transparent bg-slate-100/80 hover:border-slate-200 hover:bg-white"
                    }`}
                  >
                    <button
                      className="w-full text-left"
                      onClick={() => {
                        onSelectSession(session.id);
                        onCloseMobile();
                      }}
                      type="button"
                    >
                      {editingId === session.id ? (
                        <input
                          aria-label="Rename chat session"
                          autoFocus
                          className={`w-full rounded-xl border px-3 py-2 text-sm outline-none focus:border-[var(--chat-brand)]/40 ${
                            themeMode === "dark"
                              ? "border-white/10 bg-slate-950/40 text-white"
                              : "border-slate-200 bg-white text-slate-950"
                          }`}
                          onBlur={() => {
                            if (editingValue.trim()) {
                              onRenameSession(session.id, editingValue.trim());
                            }
                            setEditingId(null);
                          }}
                          onChange={(event) => setEditingValue(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              event.preventDefault();
                              if (editingValue.trim()) {
                                onRenameSession(session.id, editingValue.trim());
                              }
                              setEditingId(null);
                            }
                            if (event.key === "Escape") {
                              setEditingId(null);
                            }
                          }}
                          value={editingValue}
                        />
                      ) : (
                        <>
                          <p
                            className={`truncate text-sm font-medium ${
                              themeMode === "dark" ? "text-white" : "text-slate-950"
                            }`}
                          >
                            {title}
                          </p>
                          {!collapsed ? (
                            <p className="mt-1 text-xs text-slate-400">
                              {formatSessionDate(session.last_message_at ?? session.created_at)}
                            </p>
                          ) : null}
                        </>
                      )}
                    </button>

                    {!collapsed ? (
                      <div className="mt-3 flex items-center gap-2">
                        <button
                          aria-label={`Rename ${title}`}
                          className={`rounded-full border px-2.5 py-1.5 text-xs transition ${buttonChrome}`}
                          onClick={() => {
                            setEditingId(session.id);
                            setEditingValue(title);
                          }}
                          type="button"
                        >
                          Rename
                        </button>
                        <button
                          aria-label={`Delete ${title}`}
                          className={`rounded-full border px-2.5 py-1.5 text-xs transition ${
                            themeMode === "dark"
                              ? "border-white/10 text-slate-300 hover:border-rose-400/30 hover:text-rose-100"
                              : "border-slate-200 text-slate-600 hover:border-rose-300 hover:text-rose-600"
                          }`}
                          onClick={() => onDeleteSession(session.id)}
                          type="button"
                        >
                          Delete
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

export const Sidebar = memo(SidebarComponent);
