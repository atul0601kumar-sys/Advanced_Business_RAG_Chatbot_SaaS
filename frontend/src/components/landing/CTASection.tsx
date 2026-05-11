import Link from "next/link";

export function CTASection() {
  return (
    <section className="section-space">
      <div className="landing-shell">
        <div className="surface-card gradient-border overflow-hidden px-6 py-12 text-center sm:px-10 lg:px-16">
          <p className="eyebrow">Ready to launch</p>
          <h2 className="mx-auto mt-5 max-w-3xl text-4xl font-semibold sm:text-5xl">
            Start Building Your AI Chatbot Today
          </h2>
          <p className="body-muted mx-auto mt-5 max-w-2xl text-lg leading-8">
            Turn business data into a client-ready chatbot experience with retrieval, citations, analytics, and lead capture built in.
          </p>
          <div className="mt-8 flex justify-center">
            <Link href="/signup" className="button-primary">
              Get Started
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
