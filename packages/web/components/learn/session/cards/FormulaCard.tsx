"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { KaTeXRenderer } from "./KaTeXRenderer";
import type { StudyCard } from "@/types/database";

interface FormulaCardProps {
  card: StudyCard;
}

export function FormulaCard({ card }: FormulaCardProps) {
  const [showVariables, setShowVariables] = useState(false);

  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        {card.formula_name && (
          <h3 className="text-sm font-semibold text-center">{card.formula_name}</h3>
        )}

        {/* Formula display */}
        {card.formula_latex && (
          <div className="bg-muted/30 rounded-lg p-4 flex justify-center">
            <KaTeXRenderer latex={card.formula_latex} />
          </div>
        )}

        {/* Plain English */}
        {card.plain_english && (
          <div className="rounded-lg bg-primary/5 border border-primary/10 p-3">
            <p className="text-sm text-muted-foreground">{card.plain_english}</p>
          </div>
        )}

        {/* Variable breakdown toggle */}
        {card.variable_breakdown && card.variable_breakdown.length > 0 && (
          <div>
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-between text-xs"
              onClick={() => setShowVariables(!showVariables)}
            >
              {showVariables ? "Hide variables" : "Show variables"}
              <ChevronDown className={cn(
                "h-3 w-3 transition-transform",
                showVariables && "rotate-180",
              )} />
            </Button>

            {showVariables && (
              <div className="mt-2 space-y-2">
                {card.variable_breakdown.map((v, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-md border p-2.5 text-sm">
                    <div className="shrink-0 w-12 text-center">
                      <KaTeXRenderer latex={v.symbol} display={false} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium">{v.name} <span className="text-muted-foreground font-normal">({v.unit})</span></div>
                      <p className="text-xs text-muted-foreground">{v.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Conditions */}
        {card.conditions && (
          <p className="text-xs text-muted-foreground italic">{card.conditions}</p>
        )}
      </CardContent>
    </Card>
  );
}
