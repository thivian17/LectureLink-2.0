"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { Skeleton } from "@/components/ui/skeleton";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { SyllabusUploadStep } from "@/components/onboarding/SyllabusUploadStep";
import { ExtractionReviewStep } from "@/components/onboarding/ExtractionReviewStep";
import { PathSelectionStep } from "@/components/onboarding/PathSelectionStep";
import { PersonalizedMessageStep } from "@/components/onboarding/PersonalizedMessageStep";
import { StudyPlanStep } from "@/components/onboarding/StudyPlanStep";
import { LectureCatchUpStep } from "@/components/onboarding/LectureCatchUpStep";
import { PastResultsStep } from "@/components/onboarding/PastResultsStep";
import { MaterialUploadStep } from "@/components/onboarding/MaterialUploadStep";
import { PracticeModeIntroStep } from "@/components/onboarding/PracticeModeIntroStep";
import {
  startOnboarding,
  getOnboardingStatus,
  updateOnboardingStep,
} from "@/lib/api";
import type { OnboardingPath } from "@/types/database";

// Step keys for each path
const STEP_SEQUENCES: Record<OnboardingPath, string[]> = {
  just_starting: [
    "syllabus_upload",
    "extraction_review",
    "path_selection",
    "personalized_message",
    "study_plan",
  ],
  mid_semester: [
    "syllabus_upload",
    "extraction_review",
    "path_selection",
    "personalized_message",
    "lecture_catchup",
    "past_results",
    "study_plan",
  ],
  course_complete: [
    "syllabus_upload",
    "extraction_review",
    "path_selection",
    "personalized_message",
    "material_upload",
    "practice_intro",
  ],
};

// Before path is chosen, show these initial steps
const INITIAL_STEPS = [
  "syllabus_upload",
  "extraction_review",
  "path_selection",
];

const STEP_LABELS: Record<string, string> = {
  syllabus_upload: "Syllabus",
  extraction_review: "Review",
  path_selection: "Path",
  personalized_message: "Message",
  lecture_catchup: "Lectures",
  past_results: "Results",
  study_plan: "Plan",
  material_upload: "Materials",
  practice_intro: "Practice",
};

export default function OnboardingPage() {
  const params = useParams();
  const router = useRouter();
  const courseId = params.courseId as string;

  const [loading, setLoading] = useState(true);
  const [currentStepKey, setCurrentStepKey] = useState("syllabus_upload");
  const [path, setPath] = useState<OnboardingPath | null>(null);
  const [syllabusId, setSyllabusId] = useState<string | null>(null);
  const [syllabusSkipped, setSyllabusSkipped] = useState(false);

  // Initialize onboarding on mount
  useEffect(() => {
    async function init() {
      try {
        // Check existing status first
        const status = await getOnboardingStatus(courseId);
        if (status.completed_at) {
          // Already completed — redirect to course page
          router.replace(`/dashboard/courses/${courseId}`);
          return;
        }
        if (status.path) {
          setPath(status.path);
        }
        if (status.step) {
          setCurrentStepKey(status.step);
        } else {
          // Start fresh
          await startOnboarding(courseId);
        }
      } catch {
        // If 404 or error, try starting fresh
        try {
          await startOnboarding(courseId);
        } catch {
          toast.error("Failed to start onboarding");
        }
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [courseId, router]);

  // Get the active step sequence
  const steps = path ? STEP_SEQUENCES[path] : INITIAL_STEPS;
  const stepIndex = steps.indexOf(currentStepKey);
  const labels = steps.map((s) => STEP_LABELS[s] ?? s);

  const goToStep = useCallback(
    async (stepKey: string) => {
      setCurrentStepKey(stepKey);
      try {
        await updateOnboardingStep(courseId, stepKey);
      } catch {
        // Non-critical — don't block navigation
      }
    },
    [courseId],
  );

  const goBack = useCallback(() => {
    if (stepIndex > 0) {
      goToStep(steps[stepIndex - 1]);
    }
  }, [stepIndex, steps, goToStep]);

  const handleOnboardingComplete = useCallback(() => {
    router.replace(`/dashboard/courses/${courseId}`);
  }, [router, courseId]);

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-6 py-6">
        <Skeleton className="h-2 w-full" />
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  function renderStep() {
    switch (currentStepKey) {
      case "syllabus_upload":
        return (
          <SyllabusUploadStep
            courseId={courseId}
            onComplete={(id) => {
              setSyllabusId(id);
              goToStep("extraction_review");
            }}
            onSkip={() => {
              setSyllabusSkipped(true);
              goToStep("path_selection");
            }}
          />
        );

      case "extraction_review":
        if (!syllabusId) {
          // Edge case: no syllabus ID, skip to path selection
          goToStep("path_selection");
          return null;
        }
        return (
          <ExtractionReviewStep
            courseId={courseId}
            syllabusId={syllabusId}
            onComplete={() => goToStep("path_selection")}
          />
        );

      case "path_selection":
        return (
          <PathSelectionStep
            courseId={courseId}
            syllabusSkipped={syllabusSkipped}
            onComplete={(selectedPath) => {
              setPath(selectedPath);
              goToStep("personalized_message");
            }}
          />
        );

      case "personalized_message":
        if (!path) return null;
        return (
          <PersonalizedMessageStep
            courseId={courseId}
            path={path}
            onContinue={() => {
              // Navigate to next step based on path
              const sequence = STEP_SEQUENCES[path];
              const msgIdx = sequence.indexOf("personalized_message");
              if (msgIdx >= 0 && msgIdx < sequence.length - 1) {
                goToStep(sequence[msgIdx + 1]);
              }
            }}
          />
        );

      case "lecture_catchup":
        return (
          <LectureCatchUpStep
            courseId={courseId}
            onContinue={() => goToStep("past_results")}
          />
        );

      case "past_results":
        return (
          <PastResultsStep
            courseId={courseId}
            onContinue={() => goToStep("study_plan")}
          />
        );

      case "study_plan":
        if (!path) return null;
        return (
          <StudyPlanStep
            courseId={courseId}
            path={path}
            onComplete={handleOnboardingComplete}
          />
        );

      case "material_upload":
        return (
          <MaterialUploadStep
            courseId={courseId}
            onContinue={() => goToStep("practice_intro")}
          />
        );

      case "practice_intro":
        return (
          <PracticeModeIntroStep
            courseId={courseId}
            onComplete={handleOnboardingComplete}
          />
        );

      default:
        return null;
    }
  }

  return (
    <OnboardingShell
      courseId={courseId}
      currentStep={Math.max(0, stepIndex)}
      totalSteps={steps.length}
      stepLabels={labels}
      onBack={stepIndex > 0 ? goBack : undefined}
    >
      {renderStep()}
    </OnboardingShell>
  );
}
