"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { StudyCard } from "@/types/database";

interface ExampleCardProps {
  card: StudyCard;
}

export function ExampleCard({ card }: ExampleCardProps) {
  const totalSteps = card.steps?.length ?? 0;
  const [revealedCount, setRevealedCount] = useState(0);
  const allRevealed = revealedCount >= totalSteps;

  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        {card.title && (
          <h3 className="text-sm font-semibold">{card.title}</h3>
        )}

        {card.setup && (
          <p className="text-sm text-muted-foreground">{card.setup}</p>
        )}

        {/* Revealed steps */}
        {card.steps && revealedCount > 0 && (
          <div className="space-y-2">
            {card.steps.slice(0, revealedCount).map((step, i) => (
              <div key={i} className="flex items-start gap-2 animate-in fade-in slide-in-from-bottom-2 duration-200">
                <Badge variant="secondary" className="shrink-0 h-5 w-5 p-0 justify-center text-[10px]">
                  {i + 1}
                </Badge>
                <p className="text-sm">{step}</p>
              </div>
            ))}
          </div>
        )}

        {/* Reveal next step button */}
        {!allRevealed && (
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => setRevealedCount((c) => c + 1)}
          >
            {revealedCount === 0 ? "Show first step" : `Show step ${revealedCount + 1} of ${totalSteps}`}
          </Button>
        )}

        {/* Answer callout */}
        {allRevealed && card.answer && (
          <div className="rounded-lg border border-green-200 bg-green-50 p-3 animate-in fade-in duration-300">
            <p className="text-sm font-medium text-green-800">{card.answer}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
