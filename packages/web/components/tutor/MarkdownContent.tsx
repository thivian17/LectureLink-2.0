"use client";

import ReactMarkdown from "react-markdown";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  return (
    <div
      className={
        className ??
        "prose prose-sm max-w-none dark:prose-invert leading-relaxed"
      }
    >
      <ReactMarkdown>{content ?? ""}</ReactMarkdown>
    </div>
  );
}
