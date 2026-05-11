"use client";

import dynamic from "next/dynamic";

const ChatLayout = dynamic(
  () => import("@/components/chat/ChatLayout").then((module) => module.ChatLayout),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-[2.25rem] border border-white/10 bg-white/[0.04] p-8">
        <div className="space-y-4">
          <div className="h-8 w-56 animate-pulse rounded-full bg-white/10" />
          <div className="h-[70vh] animate-pulse rounded-[2rem] bg-white/[0.05]" />
        </div>
      </div>
    ),
  },
);

export default function ChatHistoryPage() {
  return <ChatLayout initialView="history" />;
}
