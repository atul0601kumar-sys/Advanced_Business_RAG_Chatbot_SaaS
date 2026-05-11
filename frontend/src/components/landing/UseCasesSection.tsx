const useCases = [
  {
    title: "Businesses",
    description: "Turn internal SOPs, policies, and sales collateral into a searchable assistant for teams and clients.",
  },
  {
    title: "Customer Support",
    description: "Deflect repetitive questions, escalate sensitive cases, and cite the exact policy behind every answer.",
  },
  {
    title: "Education / Coaching",
    description: "Offer students and clients an always-on guide grounded in curricula, playbooks, and training resources.",
  },
  {
    title: "SaaS products",
    description: "Embed product help, onboarding guidance, and technical answers directly inside the customer journey.",
  },
  {
    title: "E-commerce",
    description: "Answer product, shipping, and returns questions while capturing buying intent and support signals.",
  },
];

const steps = [
  "Upload documents or connect your website",
  "AI indexes your data with chunking, embeddings, and metadata",
  "Ask questions in the chatbot and receive cited answers",
  "Deploy on your website and track performance in analytics",
];

export function UseCasesSection() {
  return (
    <section className="section-space">
      <div className="landing-shell grid gap-12 xl:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="eyebrow">Use cases</p>
          <h2 className="mt-5 text-4xl font-semibold sm:text-5xl">Built for teams that need answers customers can trust</h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {useCases.map((useCase) => (
              <article key={useCase.title} className="surface-card p-5">
                <h3 className="text-xl font-semibold">{useCase.title}</h3>
                <p className="body-muted mt-3 text-sm leading-7">{useCase.description}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="surface-card p-6 sm:p-8">
          <p className="eyebrow">How it works</p>
          <ol className="mt-8 space-y-5">
            {steps.map((step, index) => (
              <li key={step} className="surface-panel flex items-start gap-4 p-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[var(--foreground)] text-sm font-semibold text-white dark:bg-white dark:text-slate-900">
                  {index + 1}
                </span>
                <div>
                  <p className="text-lg font-semibold">{step}</p>
                  <p className="body-muted mt-1 text-sm">
                    {index === 0 && "Bring in PDFs, websites, FAQs, and operational knowledge in one clean workflow."}
                    {index === 1 && "Your RAG pipeline organizes content for relevant retrieval, filtering, and reranking."}
                    {index === 2 && "Users get real-time responses with citations, confidence, and safe fallback handling."}
                    {index === 3 && "Launch a widget, public assistant, or internal knowledge tool with analytics built in."}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
