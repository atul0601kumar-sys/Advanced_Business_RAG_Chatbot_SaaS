"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/dashboard", label: "Home", hint: "Overview" },
  { href: "/dashboard/documents", label: "Documents", hint: "Uploads" },
  { href: "/dashboard/website-sources", label: "Website Sources", hint: "Crawlers" },
  { href: "/dashboard/faqs", label: "FAQs", hint: "Review and publish" },
  { href: "/dashboard/chat", label: "Chat", hint: "Live assistant" },
  { href: "/dashboard/chat-history", label: "Chat History", hint: "Past sessions" },
  { href: "/dashboard/leads", label: "Leads", hint: "Conversions" },
  { href: "/dashboard/scheduling", label: "Scheduling", hint: "Bookings and calendars" },
  { href: "/dashboard/integrations", label: "Integrations", hint: "External systems" },
  { href: "/dashboard/analytics", label: "Analytics", hint: "Usage and impact" },
  { href: "/dashboard/team", label: "Team", hint: "Users and roles" },
  { href: "/dashboard/settings", label: "Settings", hint: "Controls" },
  { href: "/dashboard/widget-preview", label: "Widget Preview", hint: "Embeddable UI" },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <aside className="flex w-full max-w-xs flex-col rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.96))] p-5 shadow-2xl shadow-cyan-950/20">
      <div className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-5">
        <p className="text-xs uppercase tracking-[0.35em] text-cyan-100/80">Control center</p>
        <h2 className="mt-3 text-xl font-semibold text-white">RAG Ops Console</h2>
        <p className="mt-2 text-sm text-slate-300">
          Manage sources, conversations, and growth signals from one workspace shell.
        </p>
      </div>

      <nav className="mt-5 space-y-2">
        {navItems.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between rounded-2xl px-4 py-3 transition ${
                active
                  ? "bg-white text-slate-950"
                  : "border border-transparent text-slate-300 hover:border-white/10 hover:bg-white/5 hover:text-white"
              }`}
            >
              <div>
                <p className="text-sm font-medium">{item.label}</p>
                <p
                  className={`text-xs ${
                    active ? "text-slate-600" : "text-slate-500 group-hover:text-slate-400"
                  }`}
                >
                  {item.hint}
                </p>
              </div>
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  active ? "bg-cyan-500" : "bg-slate-700 group-hover:bg-cyan-700"
                }`}
              />
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto rounded-3xl border border-white/10 bg-white/5 p-4">
        <p className="text-sm font-medium text-white">Workspace posture</p>
        <div className="mt-4 h-2 rounded-full bg-white/10">
          <div className="h-2 w-3/4 rounded-full bg-gradient-to-r from-cyan-400 to-sky-500" />
        </div>
        <p className="mt-3 text-xs text-slate-400">74% knowledge coverage across configured surfaces</p>
      </div>
    </aside>
  );
}
