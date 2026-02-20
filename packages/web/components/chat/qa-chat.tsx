"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { SendHorizontal, X, Loader2, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ScrollArea } from "@/components/ui/scroll-area";
import { askQuestion } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { QAMessage, QACitation } from "@/types/database";

const MAX_CHARS = 2000;

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function getConfidenceLabel(c: number): { label: string; className: string } {
  if (c >= 0.8) return { label: "High", className: "text-green-600" };
  if (c >= 0.5) return { label: "Moderate", className: "text-amber-600" };
  return { label: "Low", className: "text-red-600" };
}

function renderAnswer(
  content: string,
  citations: QACitation[],
  _courseId: string,
): React.ReactNode[] {
  const parts = content.split(/(\[Source \d+\])/g);
  return parts.map((part, i) => {
    const sourceMatch = part.match(/^\[Source (\d+)\]$/);
    if (sourceMatch) {
      const idx = parseInt(sourceMatch[1], 10) - 1;
      const citation = citations[idx];
      if (citation) {
        const label =
          citation.timestamp_seconds != null
            ? `${citation.lecture_title}, ${formatTimestamp(citation.timestamp_seconds)}`
            : citation.slide_number != null
              ? `${citation.lecture_title}, Slide ${citation.slide_number}`
              : citation.lecture_title;

        return (
          <Tooltip key={i}>
            <TooltipTrigger asChild>
              <Badge
                variant="secondary"
                className="cursor-pointer mx-0.5 text-xs inline-flex"
              >
                {label}
              </Badge>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <p className="text-xs">{citation.content_preview}</p>
            </TooltipContent>
          </Tooltip>
        );
      }
    }
    return <span key={i}>{part}</span>;
  });
}

interface QAChatProps {
  courseId: string;
  lectureIds?: string[];
  position: "sidebar" | "panel" | "floating";
  onClose?: () => void;
}

export function QAChat({ courseId, lectureIds, position, onClose }: QAChatProps) {
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const title = lectureIds?.length
    ? "Ask about this lecture"
    : "Ask about this course";

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      const userMsg: QAMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        citations: [],
        follow_ups: [],
        confidence: null,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);
      setError(null);

      try {
        const resp = await askQuestion(courseId, trimmed, lectureIds);
        const assistantMsg: QAMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: resp.answer,
          citations: resp.citations,
          follow_ups: resp.follow_ups,
          confidence: resp.confidence,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Something went wrong.";
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [courseId, lectureIds, loading],
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  function handleRetry() {
    // Retry with the last user message
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) {
      setError(null);
      sendMessage(lastUser.content);
    }
  }

  const isRateLimit = error?.toLowerCase().includes("rate limit");

  return (
    <TooltipProvider>
      <div
        className={cn(
          "flex flex-col bg-background border rounded-lg",
          position === "floating" && "h-full",
          position === "panel" && "h-full",
          position === "sidebar" && "h-full",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-sm font-medium">{title}</h3>
          {onClose && (
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1 px-4">
          <div className="space-y-4 py-4">
            {messages.length === 0 && !loading && (
              <p className="text-center text-sm text-muted-foreground py-8">
                Ask a question about your lecture content.
              </p>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "flex",
                  msg.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                    msg.role === "user"
                      ? "bg-blue-500 text-white"
                      : "bg-muted",
                  )}
                >
                  {msg.role === "assistant" ? (
                    <div className="space-y-2">
                      <p className="leading-relaxed whitespace-pre-wrap">
                        {renderAnswer(msg.content, msg.citations, courseId)}
                      </p>

                      {/* Confidence */}
                      {msg.confidence != null && (
                        <p className="text-xs">
                          Confidence:{" "}
                          <span className={getConfidenceLabel(msg.confidence).className}>
                            {getConfidenceLabel(msg.confidence).label}
                          </span>
                        </p>
                      )}

                      {/* Follow-up suggestions */}
                      {msg.follow_ups.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {msg.follow_ups.map((suggestion, i) => (
                            <Button
                              key={i}
                              variant="outline"
                              size="sm"
                              className="h-auto py-1 px-2 text-xs"
                              disabled={loading}
                              onClick={() => sendMessage(suggestion)}
                            >
                              {suggestion}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-lg px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:0ms]" />
                    <span className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:150ms]" />
                    <span className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="flex justify-start">
                <div className="max-w-[85%] rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm">
                  <p className="text-destructive">
                    {isRateLimit
                      ? "You've reached the question limit. Please wait a moment and try again."
                      : "Something went wrong. Please try again."}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2 h-7 text-xs"
                    onClick={handleRetry}
                  >
                    <RotateCcw className="mr-1 h-3 w-3" />
                    Retry
                  </Button>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        {/* Input */}
        <div className="border-t px-4 py-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <textarea
                ref={textareaRef}
                placeholder="Ask a question..."
                value={input}
                onChange={(e) => {
                  if (e.target.value.length <= MAX_CHARS) {
                    setInput(e.target.value);
                  }
                }}
                onKeyDown={handleKeyDown}
                disabled={loading}
                rows={1}
                className="w-full resize-none rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                style={{ maxHeight: 120 }}
              />
            </div>
            <Button
              size="sm"
              disabled={!input.trim() || loading}
              onClick={() => sendMessage(input)}
              className="shrink-0"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <SendHorizontal className="h-4 w-4" />
              )}
            </Button>
          </div>
          {input.length > MAX_CHARS * 0.8 && (
            <p
              className={cn(
                "mt-1 text-xs",
                input.length >= MAX_CHARS
                  ? "text-destructive"
                  : "text-muted-foreground",
              )}
            >
              {input.length}/{MAX_CHARS}
            </p>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
