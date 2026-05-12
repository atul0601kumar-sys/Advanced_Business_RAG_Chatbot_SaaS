"use client";

import { memo, useMemo, useState } from "react";

import type { Citation } from "@/lib/chat";

type CitationCardProps = {
  citation: Citation;
  highlightQuery?: string;
  index: number;
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

function CitationCardComponent({ citation, highlightQuery, index }: CitationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const previewNodes = useMemo(
    () => highlightPreview(citation.chunk_preview, highlightQuery),
    [citation.chunk_preview, highlightQuery],
  );

  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.025] px-3 py-2.5 transition hover:border-white/15">
      <div className="flex items-start gap-3">
        <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-1.5 text-[0.68rem] font-medium text-slate-300">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <p className="truncate text-sm font-medium text-white">
              {citation.file_name ?? "Website source"}
            </p>
            {citation.page_number !== null ? (
              <span className="text-xs text-slate-400">p. {citation.page_number}</span>
            ) : null}
            {citation.url ? (
              <a
                className="text-xs text-[var(--chat-brand)] transition hover:text-white"
                href={citation.url}
                rel="noreferrer"
                target="_blank"
              >
                Open source
              </a>
            ) : null}
            <button
              aria-expanded={isExpanded}
              className="text-xs text-slate-400 transition hover:text-white"
              onClick={() => setIsExpanded((current) => !current)}
              type="button"
            >
              {isExpanded ? "Hide preview" : "Preview"}
            </button>
          </div>
        </div>
      </div>
      {isExpanded ? (
        <div className="mt-2 rounded-xl border border-white/8 bg-slate-950/30 px-3 py-2 text-sm leading-6 text-slate-200">
          {previewNodes}
        </div>
      ) : null}
    </div>
  );
}

export const CitationCard = memo(CitationCardComponent);
