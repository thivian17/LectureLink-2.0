"use client";

import { Lightbulb } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { StudyCard } from "@/types/database";

interface HookCardProps {
  card: StudyCard;
}

export function HookCard({ card }: HookCardProps) {
  return (
    <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
      <CardContent className="p-6 space-y-4">
        <div className="flex justify-center">
          <div className="rounded-full bg-primary/10 p-3">
            <Lightbulb className="h-6 w-6 text-primary" />
          </div>
        </div>
        <p className="text-base text-center leading-relaxed">
          {card.content}
        </p>
      </CardContent>
    </Card>
  );
}
