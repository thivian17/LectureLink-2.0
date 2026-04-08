"use client";

import { useState } from "react";
import { BookOpen, Link2, CheckCircle2, XCircle, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { XPPopup } from "./XPPopup";
import { CardStack } from "./CardStack";
import { MarkdownContent } from "@/components/tutor/MarkdownContent";
import { submitGutCheck } from "@/lib/api";
import type { ConceptBrief, StudyCard } from "@/types/database";

interface ConceptBriefCardProps {
  concept: ConceptBrief & { cards?: StudyCard[] };
  sessionId: string;
  onComplete: () => void;
}

const TIER_STYLES: Record<string, { label: string; className: string }> = {
  novice: { label: "Novice", className: "border-gray-200 text-gray-600 bg-gray-50" },
  developing: { label: "Developing", className: "border-amber-200 text-amber-700 bg-amber-50" },
  proficient: { label: "Proficient", className: "border-blue-200 text-blue-700 bg-blue-50" },
  advanced: { label: "Advanced", className: "border-green-200 text-green-700 bg-green-50" },
};

export function ConceptBriefCard({ concept, sessionId, onComplete }: ConceptBriefCardProps) {
  // V2: Use CardStack if cards array is present
  if (concept.cards && concept.cards.length > 0) {
    return (
      <CardStack
        cards={concept.cards}
        conceptTitle={concept.concept_title}
        sessionId={sessionId}
        conceptId={concept.concept_id}
        onComplete={onComplete}
      />
    );
  }

  // V1 fallback: existing rendering
  return (
    <ConceptBriefV1
      concept={concept}
      sessionId={sessionId}
      onComplete={onComplete}
    />
  );
}

// V1 fallback component (original implementation)
function ConceptBriefV1({
  concept,
  sessionId,
  onComplete,
}: {
  concept: ConceptBrief;
  sessionId: string;
  onComplete: () => void;
}) {
  const [gutCheckAnswer, setGutCheckAnswer] = useState<number | null>(null);
  const [gutCheckResult, setGutCheckResult] = useState<{
    correct: boolean;
    explanation: string;
    clarification: string | null;
  } | null>(null);
  const [xpAmount, setXpAmount] = useState(0);
  const [xpTrigger, setXpTrigger] = useState(0);

  const tier = TIER_STYLES[concept.mastery_tier] ?? TIER_STYLES.novice;

  async function handleGutCheck(index: number) {
    if (gutCheckAnswer !== null) return;
    setGutCheckAnswer(index);

    try {
      const result = await submitGutCheck(sessionId, concept.concept_id, index);
      setGutCheckResult({
        correct: result.correct,
        explanation: concept.gut_check.explanation,
        clarification: null,
      });
      setXpAmount(result.xp_earned);
      setXpTrigger((t) => t + 1);
    } catch {
      const isCorrect = index === concept.gut_check.correct_index;
      setGutCheckResult({
        correct: isCorrect,
        explanation: concept.gut_check.explanation,
        clarification: null,
      });
    }
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{concept.concept_title}</h2>
        <Badge variant="outline" className={cn("text-xs", tier.className)}>
          {tier.label}
        </Badge>
      </div>

      {/* What is this? */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <BookOpen className="h-4 w-4 text-blue-500" />
            What is this?
          </div>
          <MarkdownContent
            content={concept.sections.what_is_this}
            className="text-sm text-muted-foreground prose prose-sm max-w-none dark:prose-invert"
          />
        </CardContent>
      </Card>


      {/* Key relationship */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Link2 className="h-4 w-4 text-purple-500" />
            Key relationship
          </div>
          <MarkdownContent
            content={concept.sections.key_relationship}
            className="text-sm text-muted-foreground prose prose-sm max-w-none dark:prose-invert"
          />
        </CardContent>
      </Card>

      {/* Sources (deduplicated by lecture title) */}
      {concept.sources.length > 0 && (() => {
        const seen = new Set<string>();
        const unique = concept.sources.filter((src) => {
          if (seen.has(src.lecture_title)) return false;
          seen.add(src.lecture_title);
          return true;
        });
        return (
          <div className="flex flex-wrap gap-1.5">
            {unique.map((src, i) => (
              <Badge key={i} variant="secondary" className="text-[10px]">
                <FileText className="h-3 w-3 mr-1" />
                {src.lecture_title}
              </Badge>
            ))}
          </div>
        );
      })()}

      {/* Gut check MCQ */}
      <Card className="relative overflow-hidden">
        <XPPopup xp={xpAmount} trigger={xpTrigger} />
        <CardContent className="p-4 space-y-3">
          <p className="text-sm font-medium">Gut check</p>
          <p className="text-sm">{concept.gut_check.question_text}</p>
          <div className="space-y-2">
            {concept.gut_check.options.map((option, i) => {
              const isSelected = gutCheckAnswer === i;
              const showResult = gutCheckResult !== null;
              const isCorrectOption = concept.gut_check.correct_index === i;

              return (
                <button
                  key={i}
                  onClick={() => handleGutCheck(i)}
                  disabled={gutCheckAnswer !== null}
                  className={cn(
                    "w-full text-left rounded-lg border p-3 text-sm transition-all duration-200",
                    gutCheckAnswer === null &&
                      "hover:border-primary/50 hover:bg-muted/50 cursor-pointer",
                    showResult && isCorrectOption &&
                      "border-green-500 bg-green-50 text-green-800",
                    showResult && isSelected && !isCorrectOption &&
                      "border-red-500 bg-red-50 text-red-800",
                    showResult && !isSelected && !isCorrectOption &&
                      "opacity-50",
                  )}
                >
                  {option}
                </button>
              );
            })}
          </div>

          {gutCheckResult && (
            <div
              className={cn(
                "rounded-lg p-3 text-sm transition-all duration-300",
                gutCheckResult.correct
                  ? "bg-green-50 border border-green-200"
                  : "bg-red-50 border border-red-200",
              )}
            >
              <div className="flex items-center gap-1.5 mb-1 font-medium">
                {gutCheckResult.correct ? (
                  <><CheckCircle2 className="h-4 w-4 text-green-600" /> Correct!</>
                ) : (
                  <><XCircle className="h-4 w-4 text-red-600" /> Not quite</>
                )}
              </div>
              <p className="text-muted-foreground">{gutCheckResult.explanation}</p>
              {gutCheckResult.clarification && (
                <p className="mt-2 text-muted-foreground italic">{gutCheckResult.clarification}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {gutCheckResult && (
        <Button onClick={onComplete} className="w-full">
          Continue
        </Button>
      )}
    </div>
  );
}
