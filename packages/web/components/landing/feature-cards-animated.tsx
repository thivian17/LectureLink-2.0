"use client";

import { Brain, Star, FileText, Clock, Search, BookOpen } from "lucide-react";
import { useIntersectionObserver } from "@/hooks/use-intersection-observer";

const ICONS = [Brain, Star, FileText, Clock, Search, BookOpen];

interface Feature {
  id: number;
  title: string;
  description: string;
}

interface FeatureCardsAnimatedProps {
  features: Feature[];
}

export function FeatureCardsAnimated({ features }: FeatureCardsAnimatedProps) {
  const { ref, isVisible } = useIntersectionObserver({ threshold: 0.2 });

  return (
    <div
      ref={ref as React.RefObject<HTMLDivElement>}
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
    >
      {features.map((feature, i) => {
        const Icon = ICONS[i] ?? BookOpen;
        return (
          <div
            key={feature.id}
            className="bg-background border border-border rounded-xl p-4"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? "translateY(0)" : "translateY(20px)",
              transition: `opacity 450ms ease ${i * 120}ms, transform 450ms ease ${i * 120}ms`,
            }}
          >
            <div
              className="flex h-7 w-7 items-center justify-center rounded-lg mb-3"
              style={{ backgroundColor: "#E6F1FB" }}
            >
              <Icon className="h-4 w-4" style={{ color: "#185FA5" }} />
            </div>
            <h3 className="text-sm font-medium">{feature.title}</h3>
            <p className="text-xs text-muted-foreground leading-relaxed mt-1">
              {feature.description}
            </p>
          </div>
        );
      })}
    </div>
  );
}
