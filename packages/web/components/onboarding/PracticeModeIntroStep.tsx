"use client";

import { Brain, Code, BookOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { completeOnboarding } from "@/lib/api";
import { useState } from "react";
import { toast } from "sonner";

interface PracticeModeIntroStepProps {
  courseId: string;
  onComplete: () => void;
}

const FEATURES = [
  {
    icon: Brain,
    title: "Smart Practice Tests",
    description:
      "Auto-generated practice tests based on your lecture content, weighted toward upcoming exams.",
  },
  {
    icon: Code,
    title: "Coding Practice",
    description:
      "AI-graded coding questions with starter code, test cases, and progressive hints.",
  },
  {
    icon: BookOpen,
    title: "Study Coach",
    description:
      "Personalized study recommendations based on your performance and upcoming deadlines.",
  },
];

export function PracticeModeIntroStep({
  courseId,
  onComplete,
}: PracticeModeIntroStepProps) {
  const [completing, setCompleting] = useState(false);

  async function handleComplete() {
    setCompleting(true);
    try {
      await completeOnboarding(courseId);
      onComplete();
    } catch {
      toast.error("Failed to complete onboarding");
    } finally {
      setCompleting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">
          Practice Mode
        </h2>
        <p className="text-sm text-muted-foreground">
          Here&apos;s what you can do once your lectures are processed.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {FEATURES.map((feature) => (
          <Card key={feature.title}>
            <CardHeader className="pb-2">
              <feature.icon className="h-8 w-8 text-primary mb-2" />
              <CardTitle className="text-base">{feature.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>{feature.description}</CardDescription>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex justify-end">
        <Button onClick={handleComplete} disabled={completing}>
          {completing ? "Finishing..." : "Go to Dashboard \u2192"}
        </Button>
      </div>
    </div>
  );
}
