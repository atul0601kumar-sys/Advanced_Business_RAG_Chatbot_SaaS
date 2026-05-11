"use client";

import { memo, useMemo, useState } from "react";

import type { Citation } from "@/lib/chat";

type CitationCardProps = {
  citation: Citation;
  highlightQuery?: string;
};

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightPreview(content: string, query?: string) {
  if (!query?.trim()) {
    return [content];
  }

  const keywords = query
    .toLowerCase()
    .split(/\s+/)
    .map((term) => term.trim())
    .filter((term) => term.length > 3)
    .slice(0, 5);

  if (!keywords.length) {
    return [content];
  }

  const matcher = new RegExp(`(${keywords.map(escapeRegExp).join("|")})`, "gi");
  return content.split(matcher).map((segment, index) =>
    keywords.some((keyword) => keyword.toLowerCase() === segment.toLowerCase()) ? (
      <mark key={index} className="rounded bg-[var(--chat-brand)]/25 px-1 text-white">
        {segment}
      </mark>
    ) : (
      segment
    ),
  );
}

function CitationCardComponent({ citation, highlightQuery }: CitationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const previewNodes = useMemo(
    () => highlightPreview(citation.chunk_preview, highlightQuery),
    [citation.chunk_preview, highlightQuery],
  );

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 transition hover:border-white/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-white">
            {citation.file_name ?? "Website source"}
          </p>
          <div className="flex flex-wrap gap-2 text-xs text-slate-400">
            {citation.page_number !== null ? <span>Page {citation.page_number}</span> : null}
            {citation.url ? (
              <a
                className="text-[var(--chat-brand)] hover:text-white"
                href={citation.url}
                rel="noreferrer"
                target="_blank"
              >
                Open source
              </a>
            ) : null}
          </div>
        </div>
        <button
          aria-expanded={isExpanded}
          className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 transition hover:border-white/20 hover:text-white"
          onClick={() => setIsExpanded((current) => !current)}
          type="button"
        >
          {isExpanded ? "Hide preview" : "View preview"}
        </button>
      </div>
      {isExpanded ? (
        <div className="mt-3 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm leading-6 text-slate-200">
          {previewNodes}
        </div>
      ) : null}
    </div>
  );
}

export const CitationCard = memo(CitationCardComponent);
