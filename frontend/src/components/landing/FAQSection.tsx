const faqs = [
  {
    question: "How does it work?",
    answer:
      "You upload documents or connect a website, the platform indexes the content, and the chatbot retrieves relevant context before generating a cited answer.",
  },
  {
    question: "Is my data secure?",
    answer:
      "Yes. The product is designed around workspace isolation, secure access controls, and grounded retrieval so each tenant’s data remains separated.",
  },
  {
    question: "Can I use my own documents?",
    answer:
      "Yes. The platform supports PDFs, DOCX, TXT, CSV, and website sources so you can bring your existing knowledge base directly into the assistant.",
  },
  {
    question: "Does it support websites?",
    answer:
      "Yes. You can crawl website content, clean it, index it, and combine it with document sources for a single assistant experience.",
  },
  {
    question: "How do I deploy?",
    answer:
      "After configuring your assistant, you can embed the website widget, share a public chat surface, or use the internal dashboard experience.",
  },
];

export function FAQSection() {
  return (
    <section id="faq" className="section-space">
      <div className="landing-shell grid gap-10 xl:grid-cols-[0.9fr_1.1fr]">
        <div>
          <p className="eyebrow">FAQ</p>
          <h2 className="mt-5 text-4xl font-semibold sm:text-5xl">Questions decision-makers ask before they launch</h2>
          <p className="body-muted mt-5 text-lg leading-8">
            The page is designed to reduce buying friction with security, deployment, and source-ingestion answers up front.
          </p>
        </div>

        <div className="space-y-4">
          {faqs.map((faq) => (
            <details key={faq.question} className="surface-card group p-5">
              <summary className="cursor-pointer list-none text-lg font-semibold">
                <span className="flex items-center justify-between gap-4">
                  {faq.question}
                  <span className="text-[var(--accent)] transition group-open:rotate-45">+</span>
                </span>
              </summary>
              <p className="body-muted mt-4 text-sm leading-7">{faq.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
