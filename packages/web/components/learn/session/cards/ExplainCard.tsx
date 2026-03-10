"use client";

import { Card, CardContent } from "@/components/ui/card";
import { MarkdownContent } from "@/components/tutor/MarkdownContent";
import type { StudyCard } from "@/types/database";

interface ExplainCardProps {
  card: StudyCard;
}

export function ExplainCard({ card }: ExplainCardProps) {
  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        {card.title && (
          <h3 className="text-sm font-semibold">{card.title}</h3>
        )}
        {card.content && (
          <MarkdownContent
            content={card.content}
            className="text-sm text-muted-foreground prose prose-sm max-w-none dark:prose-invert"
          />
        )}
      </CardContent>
    </Card>
  );
}
