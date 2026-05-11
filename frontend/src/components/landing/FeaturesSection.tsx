const features = [
  {
    title: "Chat with PDFs & Websites",
    description: "Index knowledge from documents and live site content without rebuilding your support stack.",
    icon: "▣",
  },
  {
    title: "Real-time AI Chat",
    description: "Stream fast, grounded answers with retrieval-aware prompts and memory for follow-up questions.",
    icon: "✦",
  },
  {
    title: "Source Citations",
    description: "Show the exact document passages behind every answer to increase trust and reduce hallucinations.",
    icon: "❖",
  },
  {
    title: "Analytics Dashboard",
    description: "Understand user intent, unanswered questions, quality trends, and operational impact in one place.",
    icon: "◫",
  },
  {
    title: "Lead Capture System",
    description: "Spot high-intent visitors, collect details, and trigger sales follow-up automatically.",
    icon: "◎",
  },
  {
    title: "Website Widget",
    description: "Deploy an embedded assistant with branded styling, secure workspace isolation, and public chat flows.",
    icon: "◪",
  },
  {
    title: "Voice Support",
    description: "Add speech input and output for more natural onboarding, service, and coaching experiences.",
    icon: "◉",
  },
  {
    title: "Integrations",
    description: "Connect Slack, Google Sheets, webhooks, and future CRM workflows without reworking your core app.",
    icon: "⌘",
  },
];

export function FeaturesSection() {
  return (
    <section id="features" className="section-space">
      <div className="landing-shell">
        <div className="mx-auto max-w-3xl text-center">
          <p className="eyebrow">Features</p>
          <h2 className="mt-5 text-4xl font-semibold sm:text-5xl">Everything a serious AI chatbot SaaS needs to earn trust and convert traffic</h2>
          <p className="body-muted mt-5 text-lg leading-8">
            Purpose-built capabilities for customer support, knowledge retrieval, lead generation, and business reporting.
          </p>
        </div>

        <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {features.map((feature) => (
            <article key={feature.title} className="surface-card group p-6 transition duration-300 hover:-translate-y-1">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--accent-soft)] text-2xl text-[var(--accent)]">
                <span aria-hidden="true">{feature.icon}</span>
              </div>
              <h3 className="mt-5 text-xl font-semibold">{feature.title}</h3>
              <p className="body-muted mt-3 text-sm leading-7">{feature.description}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
