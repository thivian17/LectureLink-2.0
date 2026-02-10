"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Search, X, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SearchResultItem } from "@/components/search/search-result-item";
import { searchLectures, getLectures, AuthError, RateLimitError } from "@/lib/api";
import type { Lecture, SearchResult } from "@/types/database";

interface SearchPageClientProps {
  courseId: string;
}

export function SearchPageClient({ courseId }: SearchPageClientProps) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [lectureFilter, setLectureFilter] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [hasSearched, setHasSearched] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Load lectures for filter dropdown
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getLectures(courseId);
        if (cancelled) return;
        setLectures(
          data
            .filter((l) => l.processing_status === "completed")
            .sort(
              (a, b) =>
                (a.lecture_number ?? 0) - (b.lecture_number ?? 0),
            ),
        );
      } catch {
        // Silently handle — filter just won't have options
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  // Debounce query input
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // Fetch search results
  const fetchResults = useCallback(
    async (q: string, lectureId: string | null) => {
      if (!q.trim()) {
        setResults([]);
        setTotalCount(0);
        setHasSearched(false);
        return;
      }
      setLoading(true);
      try {
        const resp = await searchLectures(courseId, q, lectureId);
        setResults(resp.results);
        setTotalCount(resp.total_count);
        setHasSearched(true);
      } catch (err) {
        if (err instanceof AuthError) {
          toast.error("Session expired. Please log in again.");
          return;
        }
        if (err instanceof RateLimitError) {
          toast.error(
            `Rate limit reached. Try again in ${Math.ceil(err.retryAfterSeconds / 60)} min.`,
          );
          return;
        }
        toast.error(
          err instanceof Error ? err.message : "Search failed. Please try again.",
        );
        setResults([]);
        setTotalCount(0);
      } finally {
        setLoading(false);
      }
    },
    [courseId],
  );

  useEffect(() => {
    fetchResults(debouncedQuery, lectureFilter);
  }, [debouncedQuery, lectureFilter, fetchResults]);

  function handleClear() {
    setQuery("");
    setDebouncedQuery("");
    setResults([]);
    setTotalCount(0);
    setHasSearched(false);
    inputRef.current?.focus();
  }

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={inputRef}
          placeholder="Search across all lectures..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-10 pr-10 h-12 text-base"
        />
        {query && (
          <Button
            variant="ghost"
            size="sm"
            className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 p-0"
            onClick={handleClear}
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Filters row */}
      <div className="flex items-center gap-3">
        <Select
          value={lectureFilter ?? "all"}
          onValueChange={(v) => setLectureFilter(v === "all" ? null : v)}
        >
          <SelectTrigger className="w-[240px]">
            <SelectValue placeholder="All Lectures" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Lectures</SelectItem>
            {lectures.map((l) => (
              <SelectItem key={l.id} value={l.id}>
                {l.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {hasSearched && !loading && (
          <span className="text-sm text-muted-foreground">
            {totalCount} result{totalCount !== 1 ? "s" : ""} for &ldquo;
            {debouncedQuery}&rdquo;
          </span>
        )}

        {loading && (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>

      {/* Results */}
      {!hasSearched && !loading && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <Search className="h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">
            Search across all your lecture content
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Type a query above to find relevant content across transcripts,
            slides, and concepts.
          </p>
        </div>
      )}

      {hasSearched && !loading && results.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <Search className="h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">No results found</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            No results found for &ldquo;{debouncedQuery}&rdquo;. Try different
            keywords or check that lectures have been uploaded.
          </p>
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          {results.map((result) => (
            <SearchResultItem
              key={result.id}
              result={result}
              courseId={courseId}
            />
          ))}
        </div>
      )}
    </div>
  );
}
