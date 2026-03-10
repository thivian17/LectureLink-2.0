"use client";

import { Globe } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { StudyCard } from "@/types/database";

interface RealWorldCardProps {
  card: StudyCard;
}

export function RealWorldCard({ card }: RealWorldCardProps) {
  return (
    <Card className="bg-gradient-to-br from-emerald-50/50 to-teal-50/50 dark:from-emerald-950/20 dark:to-teal-950/20">
      <CardContent className="p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-emerald-600" />
          {card.title && <h3 className="text-sm font-semibold">{card.title}</h3>}
          {card.domain && (
            <Badge variant="secondary" className="ml-auto text-[10px]">
              {card.domain}
            </Badge>
          )}
        </div>
        {card.content && (
          <p className="text-sm text-muted-foreground leading-relaxed">{card.content}</p>
        )}
      </CardContent>
    </Card>
  );
}
