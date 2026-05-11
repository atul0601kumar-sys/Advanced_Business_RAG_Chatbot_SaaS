import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

const stats = [
  { value: "3 min", label: "to first grounded chatbot" },
  { value: "99.9%", label: "workspace-isolated retrieval" },
  { value: "24/7", label: "sales and support availability" },
];

const trustLogos = ["Northstar Ops", "Vertex Care", "Aster Labs", "RetailGrid", "Signal Path"];

function MockChatWindow() {
  return (
    <div className="surface-card gradient-border float-card overflow-hidden p-4 sm:p-5">
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
        <div>
          <p className="text-sm font-semibold">Atlas Assistant</p>
          <p className="body-muted text-xs">Grounded on policies, product docs, and CRM notes</p>
        </div>
        <div className="rounded-full bg-emerald-400/20 px-3 py-1 text-xs font-semibold text-emerald-500">
          Live
        </div>
      </div>

      <div className="space-y-4 py-5">
        <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-[var(--accent-soft)] px-4 py-3 text-sm">
          Which onboarding blockers are causing the most churn this week?
        </div>
        <div className="ml-auto max-w-[92%] rounded-2xl rounded-tr-sm bg-[var(--foreground)] px-4 py-3 text-sm text-white dark:bg-white dark:text-slate-900">
          Activation delays are clustering around missing SSO setup and billing migration questions.
          I found 3 matching sources and a 22% rise in escalation volume.
        </div>
      </div>

      <div className="surface-panel grid gap-3 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold">Citations</p>
          <p className="body-muted text-xs">3 matched sources</p>
        </div>
        <div className="rounded-2xl border border-[var(--border)] p-3">
          <p className="text-sm font-medium">Q1 Customer Pulse.pdf</p>
          <p className="body-muted mt-1 text-xs">Page 12 • Activation issues increased after billing migration launch</p>
        </div>
        <div className="flex items-center justify-between rounded-2xl bg-[var(--accent-soft)] px-3 py-2 text-xs font-semibold">
          <span>Confidence</span>
          <span>High</span>
        </div>
      </div>
    </div>
  );
}

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pt-6 sm:pt-8">
      <div className="landing-shell">
        <header className="surface-card fade-up flex flex-col gap-4 rounded-[28px] px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <Link href="/" className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--foreground)] text-sm font-bold text-white dark:bg-white dark:text-slate-900">
              AI
            </span>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Atlas RAG Cloud</p>
              <p className="body-muted text-sm">Business-grounded chatbots for teams that move fast</p>
            </div>
          </Link>

          <nav aria-label="Primary" className="flex flex-wrap items-center gap-4 text-sm font-medium">
            <a href="#features" className="hover:text-[var(--accent)]">Features</a>
            <a href="#pricing" className="hover:text-[var(--accent)]">Pricing</a>
            <a href="#faq" className="hover:text-[var(--accent)]">FAQ</a>
            <Link href="/login" className="hover:text-[var(--accent)]">Login</Link>
            <ThemeToggle />
          </nav>
        </header>

        <div className="section-space grid gap-12 lg:grid-cols-[1.08fr_0.92fr] lg:items-center">
          <div className="space-y-8">
            <div className="space-y-5 fade-up">
              <p className="eyebrow">AI knowledge platform for support, sales, and ops</p>
              <h1 className="max-w-3xl text-5xl font-semibold leading-[1.02] sm:text-6xl lg:text-7xl">
                Build AI Chatbots That Understand Your Business Data
              </h1>
              <p className="max-w-2xl text-lg leading-8 body-muted sm:text-xl">
                Upload documents, connect your website, and deploy an intelligent chatbot in minutes.
                Ground every answer with citations, real-time retrieval, and analytics your team can trust.
              </p>
            </div>

            <div className="fade-up-delay flex flex-col gap-4 sm:flex-row sm:flex-wrap">
              <Link href="/signup" className="button-primary">
                Get Started
              </Link>
              <a href="#demo" className="button-secondary">
                View Demo
              </a>
              <a href="#features" className="button-tertiary">
                See Features
                <span aria-hidden="true">→</span>
              </a>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {stats.map((stat) => (
                <div key={stat.label} className="surface-panel fade-up p-4">
                  <p className="text-2xl font-semibold">{stat.value}</p>
                  <p className="body-muted mt-1 text-sm">{stat.label}</p>
                </div>
              ))}
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.26em] body-muted">Trusted by businesses</p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {trustLogos.map((logo) => (
                  <div key={logo} className="surface-panel flex items-center justify-center px-4 py-3 text-sm font-semibold body-muted">
                    {logo}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="fade-up-delay relative">
            <MockChatWindow />
            <div className="surface-panel absolute -bottom-6 -left-2 hidden max-w-xs p-4 shadow-2xl sm:block">
              <p className="text-sm font-semibold">Lead capture automation</p>
              <p className="body-muted mt-2 text-sm">Detect high-intent questions, collect contact details, and route hot leads to your team instantly.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
