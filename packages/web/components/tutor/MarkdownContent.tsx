"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

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
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Numbered lists get clear step styling
          ol: ({ children }) => (
            <ol className="ll-steps">{children}</ol>
          ),
          // Headings inside content get visual breaks
          h3: ({ children }) => (
            <h3 className="ll-section-heading">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="ll-section-heading text-sm">{children}</h4>
          ),
          // Code blocks (non-math) get distinct styling
          code: ({ className: codeClassName, children, ...props }) => {
            const isInline = !codeClassName;
            return isInline ? (
              <code className="ll-inline-code" {...props}>
                {children}
              </code>
            ) : (
              <code className={codeClassName} {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {content ?? ""}
      </ReactMarkdown>
    </div>
  );
}
