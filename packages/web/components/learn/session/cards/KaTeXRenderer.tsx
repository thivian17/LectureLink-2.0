"use client";

import { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

interface KaTeXRendererProps {
  latex: string;
  display?: boolean;
  className?: string;
}

export function KaTeXRenderer({ latex, display = true, className }: KaTeXRendererProps) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(latex, {
        displayMode: display,
        throwOnError: false,
        trust: true,
      });
    } catch {
      return `<span class="text-red-500">${latex}</span>`;
    }
  }, [latex, display]);

  return (
    <span
      className={className}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
