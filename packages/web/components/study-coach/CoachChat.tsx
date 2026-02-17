"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  SendHorizontal,
  Loader2,
  RotateCcw,
  GraduationCap,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { chatWithCoach, AuthError, RateLimitError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { CoachMessage, CoachRecommendation } from "@/types/database";
import { toast } from "sonner";

const MAX_CHARS = 2000;

const STARTER_PROMPTS = [
  "What should I study this week?",
  "What are my weakest areas?",
  "Create a study plan for my next exam",
  "Which concepts am I improving on?",
];

interface CoachChatProps {
  courseId: string;
}

export function CoachChat({ courseId }: CoachChatProps) {
  const [messages, setMessages] = useState<CoachMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      const userMsg: CoachMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        recommendations: [],
        suggested_quiz: null,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);
      setError(null);

      try {
        const history = messages.map((m) => ({
          role: m.role,
          content: m.content,
        }));
        const resp = await chatWithCoach(courseId, trimmed, history);
        const assistantMsg: CoachMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: resp.message,
          recommendations: resp.recommendations,
          suggested_quiz: resp.suggested_quiz,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err) {
        if (err instanceof AuthError) {
          toast.error("Session expired. Please log in again.");
        } else if (err instanceof RateLimitError) {
          toast.error("Rate limit reached. Please try again later.");
        } else {
          setError(
            err instanceof Error ? err.message : "Something went wrong.",
          );
        }
      } finally {
        setLoading(false);
      }
    },
    [courseId, loading, messages],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const priorityColor: Record<string, string> = {
    high: "border-red-300 text-red-700",
    medium: "border-yellow-300 text-yellow-700",
    low: "border-green-300 text-green-700",
  };

  return (
    <Card className="flex flex-col h-[420px]">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <GraduationCap className="h-4 w-4" />
          Study Coach
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col flex-1 min-h-0 gap-3">
        <ScrollArea className="flex-1 pr-3">
          {messages.length === 0 && !loading && (
            <div className="space-y-3 py-4">
              <p className="text-sm text-muted-foreground text-center">
                Ask your Study Coach for personalized advice
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {STARTER_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    className="text-xs px-3 py-1.5 rounded-full border hover:bg-accent transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "mb-3 rounded-lg p-3 text-sm",
                msg.role === "user"
                  ? "bg-primary text-primary-foreground ml-8"
                  : "bg-muted mr-4",
              )}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.role === "assistant" && msg.recommendations.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.recommendations.map((rec, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-xs bg-background rounded p-2"
                    >
                      <Badge
                        variant="outline"
                        className={cn(
                          "shrink-0",
                          priorityColor[rec.priority] ?? "",
                        )}
                      >
                        {rec.priority}
                      </Badge>
                      <div>
                        <span className="font-medium">{rec.concept}:</span>{" "}
                        {rec.action}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {msg.role === "assistant" && msg.suggested_quiz && (
                <div className="mt-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-xs h-7"
                    onClick={() =>
                      window.location.assign(
                        `/dashboard/courses/${courseId}/quizzes?difficulty=${msg.suggested_quiz?.difficulty ?? "adaptive"}`,
                      )
                    }
                  >
                    <Zap className="mr-1 h-3 w-3" />
                    Take Suggested Quiz
                  </Button>
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-3 p-3">
              <Loader2 className="h-4 w-4 animate-spin" />
              Thinking...
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 mb-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm">
              <span className="flex-1">{error}</span>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 w-6 p-0"
                onClick={() => {
                  setError(null);
                  const last = messages.filter((m) => m.role === "user").pop();
                  if (last) sendMessage(last.content);
                }}
              >
                <RotateCcw className="h-3 w-3" />
              </Button>
            </div>
          )}

          <div ref={bottomRef} />
        </ScrollArea>

        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, MAX_CHARS))}
            onKeyDown={handleKeyDown}
            placeholder="Ask your study coach..."
            rows={1}
            className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            disabled={loading}
          />
          <Button
            size="icon"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="shrink-0"
          >
            <SendHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
