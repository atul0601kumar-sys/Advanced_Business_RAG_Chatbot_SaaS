import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CitationCard } from "@/components/chat/CitationCard";

test("shows citations and highlighted preview context", async () => {
  const user = userEvent.setup();
  render(
    <CitationCard
      citation={{
        file_name: "report.pdf",
        page_number: 2,
        url: "https://example.com/report",
        chunk_preview: "Revenue grew 18 percent year over year while onboarding improved.",
      }}
      highlightQuery="revenue onboarding changes"
    />,
  );

  expect(screen.getByText("report.pdf")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "View preview" }));
  const previewMatches = screen.getAllByText(
    (_, element) => element?.textContent?.includes("Revenue grew 18 percent year over year while onboarding improved.") ?? false,
  );
  expect(previewMatches.length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: "Open source" })).toHaveAttribute("href", "https://example.com/report");
});
