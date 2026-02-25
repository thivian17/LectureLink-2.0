"use client";

import { BrainCircuit, BookOpen, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TutorMode } from "@/types/database";

interface ModeSelectorProps {
  selected: TutorMode | null;
  onSelect: (mode: TutorMode) => void;
}

const MODES: {
  mode: TutorMode;
  icon: React.ElementType;
  title: string;
  subtitle: string;
}[] = [
  {
    mode: "diagnostic",
    icon: BrainCircuit,
    title: "Test Me First",
    subtitle: "Quick diagnostic, then targeted teaching",
  },
  {
    mode: "full_lesson",
    icon: BookOpen,
    title: "Auto Study Plan",
    subtitle: "30-min plan targeting your weakest concepts",
  },
  {
    mode: "custom_plan",
    icon: Pencil,
    title: "Custom Study Plan",
    subtitle: "Choose which concepts to study",
  },
];

export function ModeSelector({ selected, onSelect }: ModeSelectorProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {MODES.map(({ mode, icon: Icon, title, subtitle }) => (
        <button
          key={mode}
          onClick={() => onSelect(mode)}
          className={cn(
            "flex flex-col items-center gap-2 rounded-xl border p-4 text-center transition-all hover:shadow-sm",
            selected === mode
              ? "border-primary bg-primary/5 ring-1 ring-primary"
              : "border-border hover:border-muted-foreground/30",
          )}
        >
          <Icon className="h-6 w-6 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">{title}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
          </div>
        </button>
      ))}
    </div>
  );
}
