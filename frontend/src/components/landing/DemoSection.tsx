import type { ReactNode } from "react";

function DemoCard({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <article className="surface-card p-5 sm:p-6">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--accent)]">{eyebrow}</p>
      <h3 className="mt-4 text-2xl font-semibold">{title}</h3>
      <p className="body-muted mt-3 text-sm leading-7">{description}</p>
      <div className="mt-6">{children}</div>
    </article>
  );
}

export function DemoSection() {
  return (
    <section id="demo" className="section-space">
      <div className="landing-shell space-y-10">
        <div className="max-w-3xl">
          <p className="eyebrow">Product demo</p>
          <h2 className="mt-5 text-4xl font-semibold sm:text-5xl">A client-ready product story from first document to measurable outcomes</h2>
          <p className="body-muted mt-5 text-lg leading-8">
            Show teams exactly how your assistant answers in real time, cites sources, captures leads, and highlights usage trends.
          </p>
        </div>

        <div className="grid gap-6 xl:grid-cols-3">
          <DemoCard
            eyebrow="Chat UI screenshot"
            title="Real-time grounded answers"
            description="Stream responses with visible source citations, confidence indicators, and lead escalation cues."
          >
            <div className="surface-panel overflow-hidden p-4">
              <div className="mb-4 flex items-center justify-between text-xs font-semibold body-muted">
                <span>Live session</span>
                <span>Typing…</span>
              </div>
              <div className="space-y-3 text-sm">
                <div className="rounded-2xl bg-[var(--accent-soft)] px-3 py-3">How do we answer implementation timeline questions?</div>
                <div className="rounded-2xl bg-[var(--foreground)] px-3 py-3 text-white dark:bg-white dark:text-slate-900">
                  Enterprise onboarding averages 9 business days. I’m citing the deployment playbook and last quarter’s launch summary.
                </div>
                <div className="rounded-2xl border border-[var(--border)] px-3 py-3 text-xs body-muted">
                  Citations: Deployment_Playbook.pdf · Launch_Summary_Q1.docx
                </div>
              </div>
            </div>
          </DemoCard>

          <DemoCard
            eyebrow="Dashboard screenshot"
            title="Control every customer-facing workflow"
            description="Tune tone, workspace sources, voice, lead capture, and handoff behavior from one polished dashboard."
          >
            <div className="surface-panel p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-[var(--border)] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] body-muted">Knowledge</p>
                  <p className="mt-2 text-2xl font-semibold">148 docs</p>
                  <p className="body-muted mt-1 text-sm">PDFs, websites, SOPs, and FAQs synced</p>
                </div>
                <div className="rounded-2xl border border-[var(--border)] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] body-muted">Lead routing</p>
                  <p className="mt-2 text-2xl font-semibold">12 hot leads</p>
                  <p className="body-muted mt-1 text-sm">Auto-routed to Slack and email</p>
                </div>
              </div>
              <div className="mt-3 rounded-2xl bg-[var(--accent-soft)] p-4 text-sm">
                Workspace controls: retrieval filters, answer style, escalation rules, widget branding
              </div>
            </div>
          </DemoCard>

          <DemoCard
            eyebrow="Analytics screenshot"
            title="Measure trust, demand, and conversion"
            description="Track answer quality, unresolved questions, traffic patterns, and revenue-linked opportunities."
          >
            <div className="surface-panel p-4">
              <div className="grid grid-cols-4 items-end gap-3">
                {[38, 62, 54, 86].map((height, index) => (
                  <div key={height} className="space-y-2 text-center text-xs">
                    <div
                      className="mx-auto w-full rounded-t-2xl bg-gradient-to-t from-[var(--accent)] to-[var(--accent-strong)]"
                      style={{ height: `${height * 1.4}px` }}
                    />
                    <span className="body-muted">{["Mon", "Tue", "Wed", "Thu"][index]}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-between rounded-2xl border border-[var(--border)] px-4 py-3 text-sm">
                <span className="body-muted">Resolved answers</span>
                <span className="font-semibold">92%</span>
              </div>
            </div>
          </DemoCard>
        </div>
      </div>
    </section>
  );
}
