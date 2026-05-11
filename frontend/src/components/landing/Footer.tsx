const footerLinks = {
  Product: [
    { label: "Features", href: "#features" },
    { label: "Pricing", href: "#pricing" },
    { label: "Demo", href: "#demo" },
  ],
  Resources: [
    { label: "Docs", href: "/login" },
    { label: "API", href: "/login" },
    { label: "Security", href: "#faq" },
  ],
  Company: [
    { label: "Contact", href: "mailto:hello@example.com" },
    { label: "LinkedIn", href: "#" },
    { label: "X / Twitter", href: "#" },
  ],
};

export function Footer() {
  return (
    <footer className="pb-10 pt-4">
      <div className="landing-shell">
        <div className="surface-card grid gap-8 px-6 py-8 lg:grid-cols-[1.2fr_1fr] lg:px-8">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[var(--accent)]">Atlas RAG Cloud</p>
            <p className="mt-4 max-w-xl text-2xl font-semibold">
              Premium AI chatbot infrastructure for teams that need trustworthy business answers.
            </p>
            <p className="body-muted mt-4 max-w-lg text-sm leading-7">
              Built for document-grounded support, lead conversion, and analytics-backed deployment decisions.
            </p>
          </div>

          <div className="grid gap-8 sm:grid-cols-3">
            {Object.entries(footerLinks).map(([heading, links]) => (
              <div key={heading}>
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] body-muted">{heading}</h3>
                <ul className="mt-4 space-y-3 text-sm">
                  {links.map((link) => (
                    <li key={link.label}>
                      <a href={link.href} className="hover:text-[var(--accent)]">
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-5 flex flex-col gap-3 px-2 text-sm body-muted sm:flex-row sm:items-center sm:justify-between">
          <p>Contact: hello@example.com</p>
          <p>© 2026 Atlas RAG Cloud. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
