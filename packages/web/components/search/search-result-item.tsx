"use client";

import Link from "next/link";
import { Clock, Image } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { SearchResult } from "@/types/database";

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function renderHighlighted(html: string): React.ReactNode[] {
  const parts = html.split(/(<mark>.*?<\/mark>)/g);
  return parts.map((part, i) => {
    const match = part.match(/^<mark>(.*)<\/mark>$/);
    if (match) {
      return (
        <mark key={i} className="bg-yellow-100 font-medium rounded-sm px-0.5">
          {match[1]}
        </mark>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

const CHUNK_LABELS: Record<string, string> = {
  transcript: "Transcript",
  slide: "Slide",
  concept: "Concept",
};

interface SearchResultItemProps {
  result: SearchResult;
  courseId: string;
}

export function SearchResultItem({ result, courseId }: SearchResultItemProps) {
  const deepLink =
    result.timestamp_seconds != null
      ? `?t=${result.timestamp_seconds}`
      : result.slide_number != null
        ? `?slide=${result.slide_number}`
        : "";

  const locationLabel =
    result.timestamp_seconds != null
      ? `at ${formatTimestamp(result.timestamp_seconds)}`
      : result.slide_number != null
        ? `Slide ${result.slide_number}`
        : null;

  return (
    <Link
      href={`/dashboard/courses/${courseId}/lectures/${result.lecture_id}${deepLink}`}
      className="block rounded-lg border p-4 transition-colors hover:bg-accent/50"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium">{result.lecture_title}</span>
            <Badge variant="outline" className="text-xs">
              {CHUNK_LABELS[result.chunk_type] ?? result.chunk_type}
            </Badge>
            {locationLabel && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                {result.timestamp_seconds != null ? (
                  <Clock className="h-3 w-3" />
                ) : (
                  <Image className="h-3 w-3" />
                )}
                {locationLabel}
              </span>
            )}
          </div>

          <p className="text-sm text-muted-foreground line-clamp-3">
            {result.highlighted_snippet
              ? renderHighlighted(result.highlighted_snippet)
              : result.content_snippet}
          </p>
        </div>
      </div>

      {/* Relevance bar */}
      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 flex-1 rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${Math.round(result.relevance_score * 100)}%` }}
          />
        </div>
        <span className="text-xs text-muted-foreground">
          {Math.round(result.relevance_score * 100)}%
        </span>
      </div>
    </Link>
  );
}
