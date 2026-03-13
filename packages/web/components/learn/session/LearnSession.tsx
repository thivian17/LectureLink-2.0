"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { SessionProgressBar } from "./SessionProgressBar";
import { DailyBriefing } from "./DailyBriefing";
import { FlashReview } from "./FlashReview";
import { ConceptBriefCard } from "./ConceptBriefCard";
import { PowerQuiz } from "./PowerQuiz";
import { SessionCelebration } from "./SessionCelebration";
import {
  startLearnSession,
  getConceptBrief,
  getPowerQuiz,
  completeLearnSession,
  abandonLearnSession,
  AuthError,
} from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import type {
  LearnSessionStep,
  LearnStartSessionResponse,
  ConceptBrief,
  StudyCard,
  PowerQuizQuestion,
  LearnSessionComplete,
} from "@/types/database";

interface LearnSessionProps {
  courseId: string;
}

export function LearnSession({ courseId }: LearnSessionProps) {
  const router = useRouter();

  const [step, setStep] = useState<LearnSessionStep>("briefing");
  const [sessionData, setSessionData] = useState<LearnStartSessionResponse | null>(null);
  const [timeBudget, setTimeBudget] = useState(15);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [abandonDialogOpen, setAbandonDialogOpen] = useState(false);

  // Concept brief state
  const [conceptIndex, setConceptIndex] = useState(0);
  const [conceptBrief, setConceptBrief] = useState<(ConceptBrief & { cards?: StudyCard[] }) | null>(null);
  const [conceptLoading, setConceptLoading] = useState(false);

  // Power quiz state
  const [quizQuestions, setQuizQuestions] = useState<PowerQuizQuestion[]>([]);

  // Celebration state
  const [celebrationData, setCelebrationData] = useState<LearnSessionComplete | null>(null);

  // Targeting state for customization
  const [targetAssessmentId, setTargetAssessmentId] = useState<string | undefined>();
  const [targetConceptIds, setTargetConceptIds] = useState<string[] | undefined>();

  const sessionId = sessionData?.session_id ?? null;
  const totalConcepts = sessionData?.daily_briefing.concepts_planned.length ?? 0;
  const hasLoadedInitial = useRef(false);

  // Load initial briefing data
  const loadBriefing = useCallback(async (options?: {
    targetAssessmentId?: string;
    targetConceptIds?: string[];
  }) => {
    if (!options && hasLoadedInitial.current) return;
    hasLoadedInitial.current = true;
    setLoading(true);
    try {
      const data = await startLearnSession(courseId, timeBudget, options);
      setSessionData(data);
      trackEvent.learnSessionStarted(courseId, timeBudget);
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to start session");
    } finally {
      setLoading(false);
    }
  }, [courseId, timeBudget, router]);

  useEffect(() => {
    loadBriefing();
  }, [loadBriefing]);

  const handleCustomize = useCallback((options: {
    targetAssessmentId?: string;
    targetConceptIds?: string[];
  }) => {
    setTargetAssessmentId(options.targetAssessmentId);
    setTargetConceptIds(options.targetConceptIds);
    // Re-fetch session with new targeting
    loadBriefing(
      options.targetAssessmentId || options.targetConceptIds?.length
        ? options
        : undefined,
    );
  }, [loadBriefing]);

  async function handleStartSession() {
    if (!sessionData) return;
    setStarting(true);
    try {
      // Session already started from loadBriefing, move to flash review
      if (sessionData.flash_review_cards.length > 0) {
        setStep("flash_review");
      } else if (totalConcepts > 0) {
        await loadConceptBrief(0);
        setStep("concept_brief");
      } else {
        await loadQuiz();
        setStep("power_quiz");
      }
    } catch {
      toast.error("Failed to start session");
    } finally {
      setStarting(false);
    }
  }

  async function loadConceptBrief(index: number) {
    if (!sessionId) return;
    setConceptLoading(true);
    try {
      const brief = await getConceptBrief(sessionId, index);
      setConceptBrief(brief);
      setConceptIndex(index);
    } catch {
      toast.error("Failed to load concept");
    } finally {
      setConceptLoading(false);
    }
  }

  async function loadQuiz() {
    if (!sessionId) return;
    try {
      const data = await getPowerQuiz(sessionId);
      setQuizQuestions(data.questions);
    } catch {
      toast.error("Failed to load quiz");
    }
  }

  function handleFlashReviewComplete() {
    if (totalConcepts > 0) {
      loadConceptBrief(0);
      setStep("concept_brief");
    } else {
      loadQuiz();
      setStep("power_quiz");
    }
  }

  function handleConceptComplete() {
    const nextIndex = conceptIndex + 1;
    if (nextIndex < totalConcepts) {
      loadConceptBrief(nextIndex);
    } else {
      loadQuiz();
      setStep("power_quiz");
    }
  }

  async function handleQuizComplete() {
    if (!sessionId) return;
    try {
      const result = await completeLearnSession(sessionId);
      setCelebrationData(result);
      setStep("celebration");
    } catch {
      toast.error("Failed to complete session");
      router.push("/dashboard");
    }
  }

  async function handleAbandon() {
    if (sessionId) {
      try {
        await abandonLearnSession(sessionId);
      } catch {
        // silent
      }
    }
    router.push("/dashboard");
  }

  if (loading) {
    return (
      <div className="max-w-lg mx-auto space-y-4 pt-8">
        <Skeleton className="h-6 w-48 mx-auto" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (!sessionData) {
    return (
      <div className="text-center py-16 text-muted-foreground">
        <p>Failed to load session. Please try again.</p>
        <Button variant="outline" className="mt-4" onClick={() => router.push("/dashboard")}>
          Back to Dashboard
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <SessionProgressBar currentStep={step} />
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={() => setAbandonDialogOpen(true)}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Step content */}
      {step === "briefing" && (
        <DailyBriefing
          briefing={sessionData.daily_briefing}
          timeBudget={timeBudget}
          onTimeBudgetChange={setTimeBudget}
          onStart={handleStartSession}
          onCustomize={handleCustomize}
          starting={starting}
        />
      )}

      {step === "flash_review" && (
        <FlashReview
          cards={sessionData.flash_review_cards}
          sessionId={sessionData.session_id}
          onComplete={handleFlashReviewComplete}
        />
      )}

      {step === "concept_brief" && (
        conceptLoading ? (
          <div className="max-w-lg mx-auto space-y-4">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-32 w-full rounded-xl" />
            <Skeleton className="h-32 w-full rounded-xl" />
          </div>
        ) : conceptBrief ? (
          <ConceptBriefCard
            concept={conceptBrief}
            sessionId={sessionData.session_id}
            onComplete={handleConceptComplete}
          />
        ) : null
      )}

      {step === "power_quiz" && (
        quizQuestions.length > 0 ? (
          <PowerQuiz
            sessionId={sessionData.session_id}
            questions={quizQuestions}
            onComplete={handleQuizComplete}
          />
        ) : (
          <div className="text-center py-12 max-w-md mx-auto space-y-4">
            <p className="text-muted-foreground">
              No quiz questions available for this session.
            </p>
            <Button onClick={handleQuizComplete}>
              Finish Session
            </Button>
          </div>
        )
      )}

      {step === "celebration" && celebrationData && (
        <SessionCelebration data={celebrationData} />
      )}

      {/* Abandon dialog */}
      <Dialog open={abandonDialogOpen} onOpenChange={setAbandonDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Leave session?</DialogTitle>
            <DialogDescription>
              Your progress will be saved and you can resume later.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAbandonDialogOpen(false)}>
              Continue Session
            </Button>
            <Button variant="destructive" onClick={handleAbandon}>
              Leave
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
