"use client";

import { MessageCircle, Info } from "lucide-react";
import type { ChatRelevance } from "@/types/database";
import { MarkdownContent } from "./MarkdownContent";

interface ChatResponseProps {
  userMessage: string;
  response: string;
  relevance: ChatRelevance;
}

export function ChatResponse({
  userMessage,
  response,
  relevance,
}: ChatResponseProps) {
  return (
    <div className="ml-4 rounded-lg border border-blue-200 bg-blue-50/50 p-4 space-y-3 dark:border-blue-800 dark:bg-blue-950/20">
      <div className="flex items-start gap-2">
        <MessageCircle className="mt-0.5 h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />
        <p className="text-sm italic text-muted-foreground">
          &ldquo;{userMessage}&rdquo;
        </p>
      </div>
      <MarkdownContent content={response} />
      {relevance !== "on_topic" && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="h-3 w-3" />
          {relevance === "related"
            ? "This is related — let's circle back to the main topic."
            : "This is a bit off-topic — let's refocus on the lesson."}
        </div>
      )}
    </div>
  );
}
