"use client";

import { Fragment, memo } from "react";

type MarkdownRendererProps = {
  content: string;
};

type Block =
  | { type: "code"; language: string; content: string }
  | { type: "table"; lines: string[] }
  | { type: "ul"; lines: string[] }
  | { type: "ol"; lines: string[] }
  | { type: "paragraph"; content: string };

const keywordMap: Record<string, string[]> = {
  ts: ["const", "let", "function", "return", "type", "interface", "if", "else", "await", "async"],
  typescript: ["const", "let", "function", "return", "type", "interface", "if", "else", "await", "async"],
  js: ["const", "let", "function", "return", "if", "else", "await", "async", "import", "export"],
  javascript: ["const", "let", "function", "return", "if", "else", "await", "async", "import", "export"],
  python: ["def", "return", "if", "else", "for", "while", "import", "from", "class", "await", "async"],
  bash: ["if", "then", "fi", "for", "do", "done", "echo", "export"],
  json: [],
};

function parseBlocks(markdown: string): Block[] {
  const blocks: Block[] = [];
  const regex = /```([\w-]+)?\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(markdown)) !== null) {
    const before = markdown.slice(lastIndex, match.index);
    blocks.push(...parseTextBlocks(before));
    blocks.push({
      type: "code",
      language: (match[1] ?? "text").toLowerCase(),
      content: match[2].trimEnd(),
    });
    lastIndex = match.index + match[0].length;
  }

  blocks.push(...parseTextBlocks(markdown.slice(lastIndex)));
  return blocks.filter((block) => {
    if (block.type === "paragraph") {
      return block.content.trim().length > 0;
    }
    return true;
  });
}

function parseTextBlocks(text: string): Block[] {
  return text
    .split(/\n{2,}/)
    .map((segment) => segment.trim())
    .filter(Boolean)
    .map((segment) => {
      const lines = segment.split(/\r?\n/).map((line) => line.trimEnd());
      if (
        lines.length >= 2 &&
        lines.every((line) => line.trim().startsWith("|")) &&
        /^[\|\s:-]+$/.test(lines[1].trim())
      ) {
        return { type: "table", lines };
      }
      if (lines.every((line) => /^[-*]\s+/.test(line))) {
        return { type: "ul", lines };
      }
      if (lines.every((line) => /^\d+\.\s+/.test(line))) {
        return { type: "ol", lines };
      }
      return { type: "paragraph", content: segment };
    });
}

function renderInline(content: string) {
  const regex = /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*)/g;
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(content.slice(lastIndex, match.index));
    }
    if (match[2] && match[3]) {
      nodes.push(
        <a
          key={`${match.index}-link`}
          className="text-[var(--chat-brand)] underline decoration-white/10 underline-offset-4 hover:text-white"
          href={match[3]}
          rel="noreferrer"
          target="_blank"
        >
          {match[2]}
        </a>,
      );
    } else if (match[4]) {
      nodes.push(
        <code
          key={`${match.index}-code`}
          className="rounded-md bg-slate-950/70 px-1.5 py-0.5 text-[0.92em] text-cyan-200"
        >
          {match[4]}
        </code>,
      );
    } else if (match[5]) {
      nodes.push(
        <strong key={`${match.index}-strong`} className="font-semibold text-white">
          {match[5]}
        </strong>,
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    nodes.push(content.slice(lastIndex));
  }

  return nodes;
}

function renderCodeLine(line: string, language: string) {
  const keywords = keywordMap[language] ?? [];
  if (language === "json") {
    return line.split(/(".*?"|\b\d+(?:\.\d+)?\b|null|true|false)/g).map((segment, index) => {
      if (/^".*"$/.test(segment) && segment.includes(":")) {
        return (
          <span key={index} className="text-sky-300">
            {segment}
          </span>
        );
      }
      if (/^".*"$/.test(segment)) {
        return (
          <span key={index} className="text-emerald-300">
            {segment}
          </span>
        );
      }
      if (/^\b\d+(?:\.\d+)?\b$/.test(segment)) {
        return (
          <span key={index} className="text-amber-300">
            {segment}
          </span>
        );
      }
      if (/^(null|true|false)$/.test(segment)) {
        return (
          <span key={index} className="text-fuchsia-300">
            {segment}
          </span>
        );
      }
      return <Fragment key={index}>{segment}</Fragment>;
    });
  }

  return line.split(/(\s+|".*?"|'.*?'|#.*$|\/\/.*$|\b\d+(?:\.\d+)?\b)/g).map((segment, index) => {
    if (!segment) {
      return null;
    }
    if (/^#.*$|^\/\/.*$/.test(segment)) {
      return (
        <span key={index} className="text-slate-500">
          {segment}
        </span>
      );
    }
    if (/^".*?"$|^'.*?'$/.test(segment)) {
      return (
        <span key={index} className="text-emerald-300">
          {segment}
        </span>
      );
    }
    if (/^\b\d+(?:\.\d+)?\b$/.test(segment)) {
      return (
        <span key={index} className="text-amber-300">
          {segment}
        </span>
      );
    }
    if (keywords.includes(segment)) {
      return (
        <span key={index} className="text-sky-300">
          {segment}
        </span>
      );
    }
    return <Fragment key={index}>{segment}</Fragment>;
  });
}

function MarkdownRendererComponent({ content }: MarkdownRendererProps) {
  const blocks = parseBlocks(content);

  return (
    <div className="space-y-4 text-[15px] leading-7 text-slate-200">
      {blocks.map((block, blockIndex) => {
        if (block.type === "code") {
          return (
            <div key={blockIndex} className="overflow-hidden rounded-2xl border border-white/10 bg-slate-950/70">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-2 text-xs uppercase tracking-[0.25em] text-slate-400">
                <span>{block.language || "code"}</span>
              </div>
              <pre className="overflow-x-auto px-4 py-4 text-sm text-slate-100">
                <code>
                  {block.content.split(/\r?\n/).map((line, lineIndex) => (
                    <div key={lineIndex}>{renderCodeLine(line, block.language)}</div>
                  ))}
                </code>
              </pre>
            </div>
          );
        }

        if (block.type === "table") {
          const rows = block.lines.map((line) =>
            line
              .split("|")
              .map((cell) => cell.trim())
              .filter(Boolean),
          );
          const [header, , ...body] = rows;
          return (
            <div key={blockIndex} className="overflow-x-auto rounded-2xl border border-white/10">
              <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                <thead className="bg-white/[0.04] text-slate-200">
                  <tr>
                    {header.map((cell, cellIndex) => (
                      <th key={cellIndex} className="px-4 py-3 font-medium">
                        {cell}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-slate-300">
                  {body.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} className="px-4 py-3">
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        if (block.type === "ul") {
          return (
            <ul key={blockIndex} className="space-y-2 pl-5 text-slate-200">
              {block.lines.map((line, lineIndex) => (
                <li key={lineIndex} className="list-disc">
                  {renderInline(line.replace(/^[-*]\s+/, ""))}
                </li>
              ))}
            </ul>
          );
        }

        if (block.type === "ol") {
          return (
            <ol key={blockIndex} className="space-y-2 pl-5 text-slate-200">
              {block.lines.map((line, lineIndex) => (
                <li key={lineIndex} className="list-decimal">
                  {renderInline(line.replace(/^\d+\.\s+/, ""))}
                </li>
              ))}
            </ol>
          );
        }

        return (
          <p key={blockIndex} className="whitespace-pre-wrap">
            {renderInline(block.content)}
          </p>
        );
      })}
    </div>
  );
}

export const MarkdownRenderer = memo(MarkdownRendererComponent);
