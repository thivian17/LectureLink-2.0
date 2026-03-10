"use client";

import { Link2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { StudyCard } from "@/types/database";

interface ConnectionCardProps {
  card: StudyCard;
}

export function ConnectionCard({ card }: ConnectionCardProps) {
  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Link2 className="h-4 w-4 text-purple-500" />
          {card.title && <h3 className="text-sm font-semibold">{card.title}</h3>}
        </div>
        {card.related_concept && (
          <Badge variant="outline" className="text-xs border-purple-200 text-purple-700 bg-purple-50">
            {card.related_concept}
          </Badge>
        )}
        {card.content && (
          <p className="text-sm text-muted-foreground leading-relaxed">{card.content}</p>
        )}
      </CardContent>
    </Card>
  );
}
