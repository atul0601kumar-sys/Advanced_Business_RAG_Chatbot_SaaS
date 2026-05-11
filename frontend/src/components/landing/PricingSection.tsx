const plans = [
  {
    name: "Basic",
    price: "$49",
    description: "For small teams validating AI-powered support and knowledge retrieval.",
    features: ["1 workspace", "Document + website ingestion", "Website widget", "Email support"],
    cta: "Start Basic",
  },
  {
    name: "Pro",
    price: "$149",
    description: "For growing businesses that need analytics, lead capture, and advanced controls.",
    features: ["5 workspaces", "Hybrid search + citations", "Lead capture + analytics", "Slack + webhook integrations"],
    cta: "Choose Pro",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "For larger organizations with high-volume traffic, security reviews, and custom workflows.",
    features: ["Unlimited workspaces", "SSO-ready architecture", "Dedicated onboarding", "Priority support + custom integrations"],
    cta: "Talk to Sales",
  },
];

export function PricingSection() {
  return (
    <section id="pricing" className="section-space">
      <div className="landing-shell">
        <div className="mx-auto max-w-3xl text-center">
          <p className="eyebrow">Pricing</p>
          <h2 className="mt-5 text-4xl font-semibold sm:text-5xl">Flexible plans for every stage of your AI rollout</h2>
          <p className="body-muted mt-5 text-lg leading-8">
            Clear packaging for pilots, growth teams, and enterprise deployments. Pricing shown as placeholders for demo-ready presentation.
          </p>
        </div>

        <div className="mt-12 grid gap-6 xl:grid-cols-3">
          {plans.map((plan) => (
            <article
              key={plan.name}
              className={`surface-card p-6 sm:p-8 ${plan.highlighted ? "gradient-border scale-[1.01]" : ""}`}
            >
              <div className="flex items-center justify-between">
                <h3 className="text-2xl font-semibold">{plan.name}</h3>
                {plan.highlighted ? (
                  <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs font-semibold text-[var(--accent)]">
                    Most Popular
                  </span>
                ) : null}
              </div>
              <p className="mt-5 text-5xl font-semibold">{plan.price}<span className="body-muted ml-2 text-base font-medium">/ month</span></p>
              <p className="body-muted mt-4 text-sm leading-7">{plan.description}</p>
              <ul className="mt-6 space-y-3 text-sm">
                {plan.features.map((feature) => (
                  <li key={feature} className="surface-panel flex items-center gap-3 px-4 py-3">
                    <span className="text-[var(--accent)]">•</span>
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <a href="/signup" className={`mt-8 w-full ${plan.highlighted ? "button-primary" : "button-secondary"}`}>
                {plan.cta}
              </a>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
