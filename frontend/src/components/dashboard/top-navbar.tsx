"use client";

import { usePathname } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import { useToast } from "@/components/toast-provider";

const titleMap: Record<string, string> = {
  "/dashboard": "Dashboard Home",
  "/dashboard/documents": "Documents",
  "/dashboard/website-sources": "Website Sources",
  "/dashboard/faqs": "FAQ Generator",
  "/dashboard/chat": "Chat Workspace",
  "/dashboard/chat-history": "Chat History",
  "/dashboard/leads": "Leads",
  "/dashboard/analytics": "Analytics",
  "/dashboard/analytics/chats": "Chat Analytics",
  "/dashboard/analytics/leads": "Lead Analytics",
  "/dashboard/analytics/performance": "AI Performance",
  "/dashboard/analytics/queries": "Query Insights",
  "/dashboard/settings": "Settings",
  "/dashboard/team": "Team and Roles",
  "/dashboard/widget-preview": "Widget Preview",
};

export function TopNavbar() {
  const pathname = usePathname();
  const { pushToast } = useToast();

  return (
    <header className="sticky top-0 z-30 rounded-[2rem] border border-white/10 bg-slate-950/85 px-5 py-4 backdrop-blur-xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Workspace command</p>
          <h1 className="mt-2 text-2xl font-semibold text-white">
            {titleMap[pathname] ?? "Dashboard"}
          </h1>
        </div>

        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2.5">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            <span className="text-sm text-slate-300">API online</span>
          </div>

          <div className="flex min-w-[260px] items-center rounded-full border border-white/10 bg-white/5 px-4 py-2.5">
            <input
              className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
              placeholder="Search sources, chats, or team members"
              type="text"
            />
          </div>

          <button
            className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2.5 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20"
            onClick={() =>
              pushToast({
                title: "Launch sequence queued",
                description: "Widget preview link copied to the handoff stack.",
                tone: "info",
              })
            }
            type="button"
          >
            Launch widget
          </button>

          <LogoutButton />
        </div>
      </div>
    </header>
  );
}
