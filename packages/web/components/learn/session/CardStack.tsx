"use client";

import { useState, useCallback } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { XPPopup } from "./XPPopup";
import { HookCard } from "./cards/HookCard";
import { ExplainCard } from "./cards/ExplainCard";
import { FormulaCard } from "./cards/FormulaCard";
import { ExampleCard } from "./cards/ExampleCard";
import { InteractiveCard } from "./cards/InteractiveCard";
import { RealWorldCard } from "./cards/RealWorldCard";
import { ConnectionCard } from "./cards/ConnectionCard";
import { GutCheckCard } from "./cards/GutCheckCard";
import type { StudyCard } from "@/types/database";

interface CardStackProps {
  cards: StudyCard[];
  conceptTitle: string;
  sessionId: string;
  conceptId: string;
  onComplete: () => void;
}

const CARD_TYPE_META: Record<string, { icon: string; label: string }> = {
  hook: { icon: "🎯", label: "Hook" },
  explain: { icon: "📖", label: "Explain" },
  formula: { icon: "🔢", label: "Formula" },
  example: { icon: "✏️", label: "Example" },
  interactive: { icon: "🧩", label: "Challenge" },
  real_world: { icon: "🌍", label: "Real World" },
  connection: { icon: "🔗", label: "Connection" },
  gut_check: { icon: "✅", label: "Gut Check" },
};

const INTERACTIVE_TYPES = new Set(["gut_check", "interactive"]);

export function CardStack({ cards, conceptTitle, sessionId, conceptId, onComplete }: CardStackProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [completedCards, setCompletedCards] = useState<Set<number>>(new Set());
  const [direction, setDirection] = useState<"left" | "right">("right");
  const [xpAmount, setXpAmount] = useState(0);
  const [xpTrigger, setXpTrigger] = useState(0);

  const card = cards[currentIndex];
  const isInteractive = card ? INTERACTIVE_TYPES.has(card.type) : false;
  const isCardCompleted = completedCards.has(currentIndex);
  const canAdvance = !isInteractive || isCardCompleted;
  const isLastCard = currentIndex === cards.length - 1;
  const meta = card ? CARD_TYPE_META[card.type] ?? { icon: "📄", label: card.type } : null;

  const handleCardInteraction = useCallback((xp?: number) => {
    setCompletedCards((prev) => new Set(prev).add(currentIndex));
    if (xp && xp > 0) {
      setXpAmount(xp);
      setXpTrigger((t) => t + 1);
    }
  }, [currentIndex]);

  function goNext() {
    if (!canAdvance) return;
    if (isLastCard) {
      onComplete();
      return;
    }
    setDirection("right");
    if (!isInteractive) {
      setCompletedCards((prev) => new Set(prev).add(currentIndex));
    }
    setCurrentIndex((i) => i + 1);
  }

  function goBack() {
    if (currentIndex === 0) return;
    setDirection("left");
    setCurrentIndex((i) => i - 1);
  }

  if (!card) return null;

  function renderCard() {
    if (!card) return null;
    const commonProps = { onInteraction: handleCardInteraction };

    switch (card.type) {
      case "hook": return <HookCard card={card} />;
      case "explain": return <ExplainCard card={card} />;
      case "formula": return <FormulaCard card={card} />;
      case "example": return <ExampleCard card={card} />;
      case "interactive": return <InteractiveCard card={card} {...commonProps} />;
      case "real_world": return <RealWorldCard card={card} />;
      case "connection": return <ConnectionCard card={card} />;
      case "gut_check": return (
        <GutCheckCard
          card={card}
          sessionId={sessionId}
          conceptId={conceptId}
          {...commonProps}
        />
      );
      default: return <ExplainCard card={{ ...card, type: "explain" }} />;
    }
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      {/* Progress dots */}
      <div className="flex items-center gap-1 px-1">
        {cards.map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-1 flex-1 rounded-full transition-all duration-300",
              i < currentIndex && "bg-primary",
              i === currentIndex && "bg-primary/70 scale-y-150",
              i > currentIndex && "bg-muted",
            )}
          />
        ))}
      </div>

      {/* Card type label */}
      <div className="flex items-center justify-between px-1">
        <span className="text-xs text-muted-foreground">
          {meta?.icon} {meta?.label} · {currentIndex + 1}/{cards.length}
        </span>
        <span className="text-xs text-muted-foreground font-medium">
          {conceptTitle}
        </span>
      </div>

      {/* Card container with animation */}
      <div className="relative overflow-hidden rounded-xl min-h-[300px]">
        <XPPopup xp={xpAmount} trigger={xpTrigger} />
        <div
          key={currentIndex}
          className={cn(
            "animate-in duration-200 ease-out fill-mode-both",
            direction === "right" ? "slide-in-from-right-4 fade-in" : "slide-in-from-left-4 fade-in",
          )}
        >
          {renderCard()}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9"
          onClick={goBack}
          disabled={currentIndex === 0}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          className="flex-1"
          onClick={goNext}
          disabled={!canAdvance}
        >
          {isLastCard ? "Continue" : "Next"}
          {!isLastCard && <ChevronRight className="ml-1 h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
