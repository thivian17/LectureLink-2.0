"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface QuizModeConfig {
  include_coding: boolean;
  coding_only: boolean;
  coding_ratio: number;
  coding_language: string;
  suggested_num_questions: number;
}

interface QuizModeSelectorProps {
  onChange: (config: QuizModeConfig) => void;
  defaultLanguage?: string;
}

const CODING_LANGUAGES = [
  "Python",
  "Java",
  "JavaScript",
  "C++",
  "SQL",
  "MATLAB",
];

type QuizMode = "knowledge" | "mixed" | "code";

const MODE_DEFAULTS: Record<QuizMode, QuizModeConfig> = {
  knowledge: {
    include_coding: false,
    coding_only: false,
    coding_ratio: 0,
    coding_language: "python",
    suggested_num_questions: 10,
  },
  mixed: {
    include_coding: true,
    coding_only: false,
    coding_ratio: 0.3,
    coding_language: "python",
    suggested_num_questions: 10,
  },
  code: {
    include_coding: true,
    coding_only: true,
    coding_ratio: 1.0,
    coding_language: "python",
    suggested_num_questions: 5,
  },
};

const MODES: { key: QuizMode; icon: string; title: string; subtitle: string }[] = [
  {
    key: "knowledge",
    icon: "\u{1F4DD}",
    title: "Knowledge Quiz",
    subtitle: "Multiple choice & short answer",
  },
  {
    key: "mixed",
    icon: "\u{1F500}",
    title: "Mixed Practice",
    subtitle: "Questions + coding challenges",
  },
  {
    key: "code",
    icon: "\u{1F4BB}",
    title: "Code Practice",
    subtitle: "Coding challenges only",
  },
];

export function QuizModeSelector({
  onChange,
  defaultLanguage = "Python",
}: QuizModeSelectorProps) {
  const [selected, setSelected] = useState<QuizMode>("knowledge");
  const [codingRatio, setCodingRatio] = useState(30);
  const [codingLanguage, setCodingLanguage] = useState(defaultLanguage);

  function selectMode(mode: QuizMode) {
    setSelected(mode);
    const config = { ...MODE_DEFAULTS[mode] };
    if (mode === "mixed") {
      config.coding_ratio = codingRatio / 100;
      config.coding_language = codingLanguage.toLowerCase();
    } else if (mode === "code") {
      config.coding_language = codingLanguage.toLowerCase();
    }
    onChange(config);
  }

  function updateRatio(value: number) {
    setCodingRatio(value);
    onChange({
      ...MODE_DEFAULTS.mixed,
      coding_ratio: value / 100,
      coding_language: codingLanguage.toLowerCase(),
    });
  }

  function updateLanguage(lang: string, mode: QuizMode) {
    setCodingLanguage(lang);
    const config = { ...MODE_DEFAULTS[mode] };
    config.coding_language = lang.toLowerCase();
    if (mode === "mixed") {
      config.coding_ratio = codingRatio / 100;
    }
    onChange(config);
  }

  return (
    <div className="space-y-3">
      <Label>Quiz mode</Label>
      <div className="grid grid-cols-3 gap-2">
        {MODES.map((mode) => (
          <button
            key={mode.key}
            type="button"
            onClick={() => selectMode(mode.key)}
            className={`flex flex-col items-center gap-1 rounded-lg border-2 p-3 text-center transition-colors ${
              selected === mode.key
                ? "border-primary bg-primary/5"
                : "border-border hover:border-muted-foreground/40"
            }`}
          >
            <span className="text-xl leading-none">{mode.icon}</span>
            <span className="text-xs font-medium leading-tight">
              {mode.title}
            </span>
            <span className="text-[10px] leading-tight text-muted-foreground">
              {mode.subtitle}
            </span>
          </button>
        ))}
      </div>

      {selected === "mixed" && (
        <div className="space-y-4 pl-1">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Coding ratio</Label>
              <span className="text-xs text-muted-foreground tabular-nums">
                {codingRatio}%
              </span>
            </div>
            <Slider
              value={[codingRatio]}
              onValueChange={([v]) => updateRatio(v)}
              min={10}
              max={80}
              step={10}
            />
          </div>
          <div className="space-y-2">
            <Label className="text-xs">Language</Label>
            <Select
              value={codingLanguage}
              onValueChange={(v) => updateLanguage(v, "mixed")}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CODING_LANGUAGES.map((lang) => (
                  <SelectItem key={lang} value={lang}>
                    {lang}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}

      {selected === "code" && (
        <div className="space-y-4 pl-1">
          <div className="space-y-2">
            <Label className="text-xs">Language</Label>
            <Select
              value={codingLanguage}
              onValueChange={(v) => updateLanguage(v, "code")}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CODING_LANGUAGES.map((lang) => (
                  <SelectItem key={lang} value={lang}>
                    {lang}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <p className="text-xs text-muted-foreground">
            Recommended: 3-5 questions per session
          </p>
        </div>
      )}
    </div>
  );
}
