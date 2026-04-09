"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Send, BookOpen, Clock, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { askQuestion } from "@/lib/api";
import type { QACitation } from "@/types/database";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: QACitation[];
  followUps: string[];
  confidence: number | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(seconds: number | null): string {
  if (seconds == null) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Citation chip
// ---------------------------------------------------------------------------

function CitationChip({ citation, index }: { citation: QACitation; index: number }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-xs">
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold mt-0.5">
        {index + 1}
      </span>
      <div className="min-w-0 space-y-0.5">
        <p className="font-medium text-foreground truncate">
          {citation.lecture_title}
        </p>
        <div className="flex items-center gap-2 text-muted-foreground">
          {citation.timestamp_seconds != null && (
            <span className="flex items-center gap-0.5">
              <Clock className="h-3 w-3" />
              {formatTimestamp(citation.timestamp_seconds)}
            </span>
          )}
          {citation.slide_number != null && (
            <span className="flex items-center gap-0.5">
              <FileText className="h-3 w-3" />
              Slide {citation.slide_number}
            </span>
          )}
        </div>
        <p className="text-muted-foreground line-clamp-2">
          {citation.content_preview}
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chat message bubble
// ---------------------------------------------------------------------------

function ChatBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] space-y-3",
          isUser ? "order-1" : "order-1",
        )}
      >
        {/* Message content */}
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-primary text-primary-foreground rounded-br-md"
              : "bg-muted rounded-bl-md",
          )}
        >
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Citations */}
        {!isUser && message.citations.length > 0 && (
          <div className="space-y-1.5 pl-1">
            <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
              Sources
            </p>
            <div className="grid gap-1.5">
              {message.citations.map((c, i) => (
                <CitationChip key={c.id} citation={c} index={i} />
              ))}
            </div>
          </div>
        )}

        {/* Follow-up suggestions */}
        {!isUser && message.followUps.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pl-1">
            {message.followUps.map((q) => (
              <button
                key={q}
                className="rounded-full border px-3 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors text-left"
                data-followup={q}
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const params = useParams<{ courseId: string }>();
  const courseId = params.courseId;

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  // Auto-resize textarea
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        citations: [],
        followUps: [],
        confidence: null,
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      try {
        const res = await askQuestion(courseId, trimmed);

        const assistantMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.answer,
          citations: res.citations,
          followUps: res.follow_ups,
          confidence: res.confidence,
        };

        setMessages((prev) => [...prev, assistantMsg]);
      } catch {
        const errorMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            "Sorry, I wasn't able to answer that. Make sure lectures have been uploaded and processed for this course.",
          citations: [],
          followUps: [],
          confidence: null,
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    },
    [courseId, loading],
  );

  // Handle follow-up clicks via event delegation
  const handleContainerClick = useCallback(
    (e: React.MouseEvent) => {
      const target = (e.target as HTMLElement).closest<HTMLElement>(
        "[data-followup]",
      );
      if (target?.dataset.followup) {
        sendMessage(target.dataset.followup);
      }
    },
    [sendMessage],
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="shrink-0 border-b px-4 py-3">
        <h1 className="text-lg font-bold tracking-tight flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-primary" />
          Ask Your Lectures
        </h1>
        <p className="text-xs text-muted-foreground">
          Ask questions and get answers sourced from your course material
        </p>
      </div>

      {/* Messages area */}
      <div
        ref={scrollRef}
        onClick={handleContainerClick}
        className="flex-1 overflow-y-auto px-4 py-6 space-y-4"
      >
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-3 text-muted-foreground">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
              <BookOpen className="h-7 w-7 text-primary" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">
                Ask anything about your lectures
              </p>
              <p className="text-xs mt-1 max-w-xs">
                Every answer is sourced from your course material with the exact
                lecture, timestamp, and slide number cited.
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatBubble key={msg.id} message={msg} />
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-md bg-muted px-4 py-3">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t bg-background p-4">
        <div className="flex items-end gap-2 max-w-3xl mx-auto">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your lectures..."
            rows={1}
            disabled={loading}
            className="flex-1 resize-none rounded-xl border bg-muted/50 px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary disabled:opacity-50"
          />
          <Button
            size="icon"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="shrink-0 rounded-xl h-10 w-10"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-[10px] text-muted-foreground text-center mt-2">
          Answers are generated from your uploaded lectures. Shift+Enter for new line.
        </p>
      </div>
    </div>
  );
}
