"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { SessionProgressBar } from "@/components/tutor/SessionProgressBar";
import { ChatInput } from "@/components/tutor/ChatInput";
import { TeachingBlock } from "@/components/tutor/TeachingBlock";
import { CheckQuestion } from "@/components/tutor/CheckQuestion";
import { ReteachBlock } from "@/components/tutor/ReteachBlock";
import { PracticeBlock } from "@/components/tutor/PracticeBlock";
import { SummaryBlock } from "@/components/tutor/SummaryBlock";
import { TransitionBlock } from "@/components/tutor/TransitionBlock";
import { ChatResponse } from "@/components/tutor/ChatResponse";
import { DiagnosticView } from "@/components/tutor/DiagnosticView";
import { SessionSummary } from "@/components/tutor/SessionSummary";
import { LessonPlanOverview } from "@/components/tutor/LessonPlanOverview";
import {
  getActiveTutorSession,
  getAssessmentReadiness,
  resumeTutorSession,
  pauseTutorSession,
  completeTutorSession,
  sendTutorChat,
  startTutorSession,
  fetchNextBlock,
} from "@/lib/api";
import { AuthError } from "@/lib/api-errors";
import { trackEvent } from "@/lib/analytics";
import type {
  TutorSession,
  AssessmentReadiness,
  ContentBlock,
  GradingResult,
  SessionSummary as SessionSummaryType,
  DiagnosticResult,
  ChatRelevance,
} from "@/types/database";

// A rendered block in the lesson stream
interface RenderedBlock {
  id: string;
  type: ContentBlock["block_type"] | "diagnostic";
  content: string;
  block?: ContentBlock;
  // For chat blocks
  userMessage?: string;
  relevance?: ChatRelevance;
  // For summary blocks
  questionsAsked?: number;
  questionsCorrect?: number;
  mastery?: number;
  // For transition blocks
  nextConceptTitle?: string;
  estimatedMinutes?: number;
  onStart?: () => void;
  // For reteach
  reteachContent?: string;
}

export default function TutorSessionPage() {
  const params = useParams<{ courseId: string; sessionId: string }>();
  const { courseId, sessionId } = params;
  const router = useRouter();

  const [session, setSession] = useState<TutorSession | null>(null);
  const [blocks, setBlocks] = useState<RenderedBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [currentConceptIndex, setCurrentConceptIndex] = useState(0);
  const [isWaitingForAnswer, setIsWaitingForAnswer] = useState(false);
  const [showBreakModal, setShowBreakModal] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [summaryData, setSummaryData] = useState<SessionSummaryType | null>(
    null,
  );
  const [ending, setEnding] = useState(false);
  const [fetchingBlock, setFetchingBlock] = useState(false);
  const [showIntro, setShowIntro] = useState(false);
  const [assessmentReadiness, setAssessmentReadiness] =
    useState<AssessmentReadiness | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const hasShown25 = useRef(false);
  const hasShown60 = useRef(false);
  const blockIdCounter = useRef(0);

  // Per-concept tracking for missed-question review
  const missedQRef = useRef<RenderedBlock[]>([]);
  const [reviewingMissed, setReviewingMissed] = useState(false);
  const conceptQAsked = useRef(0);
  const conceptQCorrect = useRef(0);
  // How many pre-generated blocks of the current concept have been consumed
  const conceptBlocksConsumed = useRef(0);

  function nextBlockId() {
    return `block-${++blockIdCounter.current}`;
  }

  // Track tutor session start
  useEffect(() => {
    trackEvent.tutorSessionStarted(courseId, "tutor");
  }, [courseId]);

  // Load session
  const loadSession = useCallback(async () => {
    try {
      let sess = await getActiveTutorSession(courseId);
      if (!sess || sess.id !== sessionId) {
        sess = await resumeTutorSession(sessionId);
      }
      setSession(sess);
      setCurrentConceptIndex(sess.current_concept_index);
      setElapsedSeconds(sess.duration_seconds);

      // Show intro for fresh non-diagnostic sessions with a lesson plan
      const isFresh =
        sess.current_concept_index === 0 &&
        sess.concepts_completed === 0 &&
        sess.questions_asked === 0;
      if (
        sess.lesson_plan &&
        sess.mode !== "diagnostic" &&
        isFresh
      ) {
        setShowIntro(true);

        // Fetch assessment readiness for "not covered" and "remaining sessions" info
        if (sess.target_assessment_id) {
          getAssessmentReadiness(courseId, sess.target_assessment_id)
            .then(setAssessmentReadiness)
            .catch(() => {});
        }
      } else {
        // Populate initial blocks from lesson plan (resumed or non-intro)
        populateBlocks(sess);
      }
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to load session");
      router.push(`/dashboard/courses/${courseId}/tutor`);
    } finally {
      setLoading(false);
    }
  }, [courseId, sessionId, router]);

  /**
   * Render pre-generated blocks up to (and including) the first "check"
   * question, so content is presented one chunk at a time instead of all
   * at once.  Uses conceptBlocksConsumed ref to track position within the
   * current concept's block list.
   */
  function renderBlocksUntilCheck(
    allBlocks: ContentBlock[],
    startIndex: number,
    replace: boolean,
  ): void {
    const batch: RenderedBlock[] = [];

    for (let i = startIndex; i < allBlocks.length; i++) {
      const b = allBlocks[i];
      batch.push({
        id: nextBlockId(),
        type: b.block_type,
        content: b.content,
        block: b,
      });
      conceptBlocksConsumed.current = i + 1;

      // Stop after the first check question so the user must answer
      if (b.block_type === "check" && b.question) {
        setIsWaitingForAnswer(true);
        break;
      }

      // Also stop after a practice block (interactive reveal)
      if (b.block_type === "practice") {
        break;
      }
    }

    if (replace) {
      setBlocks(batch);
    } else {
      setBlocks((prev) => [...prev, ...batch]);
    }
  }

  async function populateBlocks(sess: TutorSession) {
    if (!sess.lesson_plan) return;

    const concept = sess.lesson_plan.concepts[sess.current_concept_index];
    if (concept?.generated_content) {
      // Fast path: render blocks up to the first check question
      conceptBlocksConsumed.current = 0;
      renderBlocksUntilCheck(concept.generated_content.blocks, 0, true);
      return;
    }

    // Fallback: fetch blocks on demand from the API
    await loadNextBlockFromApi();
  }

  async function loadNextBlockFromApi() {
    setFetchingBlock(true);
    try {
      const block = await fetchNextBlock(sessionId);

      if (block.block_type === "complete") {
        // All concepts done — use "complete" type, not "summary"
        setBlocks((prev) => [
          ...prev,
          {
            id: nextBlockId(),
            type: "complete",
            content: block.content ?? "All concepts covered! Great work.",
          },
        ]);
        return;
      }

      // Skip backend summary/transition steps — handleConceptComplete
      // renders a better summary with accurate stats and a transition.
      if (
        block.block_type === "summary" ||
        block.block_type === "transition"
      ) {
        await loadNextBlockFromApi();
        return;
      }

      if (block.block_type === "concept_complete") {
        setFetchingBlock(false);

        // Review missed questions before completing the concept
        if (missedQRef.current.length > 0) {
          setReviewingMissed(true);
          insertNextReviewQuestion(true);
          return;
        }

        // Show summary + transition, then auto-fetch next concept
        const completedConcept =
          session?.lesson_plan?.concepts[currentConceptIndex];
        if (completedConcept) {
          await handleConceptComplete(completedConcept);
        }
        return;
      }

      const rendered: RenderedBlock = {
        id: nextBlockId(),
        type: block.block_type as RenderedBlock["type"],
        content: block.content,
        block: block,
      };
      setBlocks((prev) => [...prev, rendered]);
      setCurrentConceptIndex(block.concept_index);

      if (block.block_type === "check" && block.question) {
        setIsWaitingForAnswer(true);
      } else if (block.block_type !== "practice") {
        // Auto-chain: non-interactive blocks (teaching, feedback, etc.)
        // automatically fetch the next block so the user doesn't have to
        // click Continue between teaching steps and check questions.
        await loadNextBlockFromApi();
        return;
      }
    } catch {
      toast.error("Failed to load lesson content");
    } finally {
      setFetchingBlock(false);
    }
  }

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  // Timer
  useEffect(() => {
    if (!session || session.status !== "active") return;
    const interval = setInterval(() => {
      setElapsedSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [session]);

  // Break suggestions
  useEffect(() => {
    if (elapsedSeconds >= 25 * 60 && !hasShown25.current) {
      hasShown25.current = true;
      toast("Good progress — 25 minutes of focused study!", {
        duration: 5000,
      });
    }
    if (elapsedSeconds >= 60 * 60 && !hasShown60.current) {
      hasShown60.current = true;
      setShowBreakModal(true);
    }
  }, [elapsedSeconds]);

  // No auto-scroll — let the user control their scroll position

  async function handlePause() {
    try {
      await pauseTutorSession(sessionId);
      router.push(`/dashboard/courses/${courseId}/tutor`);
    } catch {
      toast.error("Failed to pause session");
    }
  }

  async function handleEnd() {
    setEnding(true);
    trackEvent.tutorSessionEnded(courseId, elapsedSeconds);
    try {
      const summary = await completeTutorSession(sessionId);
      setSummaryData(summary);
      setShowSummary(true);
    } catch {
      toast.error("Failed to end session");
    } finally {
      setEnding(false);
    }
  }

  async function handleFillGaps() {
    if (!session?.target_assessment_id) return;
    try {
      await completeTutorSession(sessionId);
      const newSession = await startTutorSession(courseId, {
        mode: "full_lesson",
        target_assessment_id: session.target_assessment_id,
      });
      router.push(
        `/dashboard/courses/${courseId}/tutor/session/${newSession.id}`,
      );
    } catch {
      toast.error("Failed to start study session");
    }
  }

  async function handleRetestDiagnostic() {
    if (!session?.target_assessment_id) return;
    try {
      await completeTutorSession(sessionId);
      const newSession = await startTutorSession(courseId, {
        mode: "diagnostic",
        target_assessment_id: session.target_assessment_id,
      });
      router.push(
        `/dashboard/courses/${courseId}/tutor/session/${newSession.id}?retest=true`,
      );
    } catch {
      toast.error("Failed to start re-test");
    }
  }

  function insertNextReviewQuestion(isFirst: boolean) {
    const [next, ...rest] = missedQRef.current;
    missedQRef.current = rest;

    const newBlocks: RenderedBlock[] = [];
    if (isFirst) {
      newBlocks.push({
        id: nextBlockId(),
        type: "teaching",
        content:
          "Before we move on, let's revisit a question you missed.",
      });
    }
    // Re-insert the question block with a new id so React remounts it
    newBlocks.push({ ...next, id: nextBlockId() });

    setBlocks((prev) => [...prev, ...newBlocks]);
    setIsWaitingForAnswer(true);
  }

  async function handleAnswered(result: GradingResult) {
    setIsWaitingForAnswer(false);

    // Track per-concept stats
    conceptQAsked.current += 1;
    if (result.is_correct) conceptQCorrect.current += 1;

    // Track missed questions (not during review round)
    if (!result.is_correct && !reviewingMissed) {
      const lastCheck = [...blocks]
        .reverse()
        .find((b) => b.type === "check" && b.block?.question);
      if (lastCheck) {
        missedQRef.current = [...missedQRef.current, lastCheck];
      }
    }

    // Show reteach if triggered (skip during review — just move on)
    if (
      result.reteach_triggered &&
      result.reteach_content &&
      !reviewingMissed
    ) {
      setBlocks((prev) => [
        ...prev,
        {
          id: nextBlockId(),
          type: "reteach",
          content: result.reteach_content!,
        },
      ]);
    }

    // During review: next missed question or complete concept
    if (reviewingMissed) {
      if (missedQRef.current.length > 0) {
        insertNextReviewQuestion(false);
      } else {
        setReviewingMissed(false);
        if (session?.lesson_plan) {
          const concept =
            session.lesson_plan.concepts[currentConceptIndex];
          if (concept) {
            await handleConceptComplete(concept);
          }
        }
      }
      return;
    }

    // Normal flow: continue with remaining content
    if (session?.lesson_plan) {
      const concept =
        session.lesson_plan.concepts[currentConceptIndex];

      if (concept?.generated_content) {
        // Pre-generated path: use the ref to know where we left off
        const allContentBlocks = concept.generated_content.blocks;
        const consumed = conceptBlocksConsumed.current;

        if (consumed < allContentBlocks.length) {
          // Render the next chunk (up to the next check question)
          renderBlocksUntilCheck(allContentBlocks, consumed, false);
        } else {
          // Concept blocks done — review missed first
          if (missedQRef.current.length > 0) {
            setReviewingMissed(true);
            insertNextReviewQuestion(true);
            return;
          }
          handleConceptComplete(concept);
        }
      } else {
        // On-demand path — loadNextBlockFromApi handles concept_complete
        await loadNextBlockFromApi();
      }
    }
  }

  async function handleConceptComplete(concept: { title: string; mastery?: number; estimated_minutes?: number }) {
    if (!session?.lesson_plan) return;
    const plan = session.lesson_plan;
    const nextIdx = currentConceptIndex + 1;

    // Reset per-concept tracking for the next concept
    missedQRef.current = [];
    conceptQAsked.current = 0;
    conceptQCorrect.current = 0;
    conceptBlocksConsumed.current = 0;

    if (nextIdx < plan.concepts.length) {
      const next = plan.concepts[nextIdx];
      setCurrentConceptIndex(nextIdx);

      // Show transition with a button — user clicks to start the next concept
      setBlocks((prev) => [
        ...prev,
        {
          id: nextBlockId(),
          type: "transition",
          content: "",
          nextConceptTitle: next.title,
          estimatedMinutes: next.estimated_minutes,
          onStart: () => {
            if (next.generated_content) {
              renderBlocksUntilCheck(next.generated_content.blocks, 0, false);
            } else {
              loadNextBlockFromApi();
            }
          },
        },
      ]);
    }
  }

  async function handleChat(message: string) {
    try {
      const res = await sendTutorChat(sessionId, message);
      setBlocks((prev) => [
        ...prev,
        {
          id: nextBlockId(),
          type: "chat_response",
          content: res.response,
          userMessage: message,
          relevance: res.relevance,
        },
      ]);
    } catch {
      toast.error("Failed to send message");
    }
  }

  function handleDiagnosticComplete(_result: DiagnosticResult) {
    // DiagnosticView manages results display internally.
    // The onComplete callback is kept for any external state needs.
  }

  if (loading) {
    return (
      <div className="flex flex-col h-[calc(100vh-4rem)]">
        <div className="border-b p-4">
          <Skeleton className="h-5 w-64" />
          <Skeleton className="mt-2 h-1.5 w-full rounded-full" />
        </div>
        <div className="flex-1 p-6 space-y-4">
          <Skeleton className="h-24 w-full rounded-lg" />
          <Skeleton className="h-16 w-3/4 rounded-lg" />
          <Skeleton className="h-32 w-full rounded-lg" />
        </div>
      </div>
    );
  }

  if (!session) return null;

  const plan = session.lesson_plan;
  const currentConcept = plan?.concepts[currentConceptIndex];
  const isDiagnostic = session.mode === "diagnostic" && blocks.length === 0;

  // No lesson plan — show error and redirect
  if (!plan && !isDiagnostic) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-4rem)] gap-4">
        <p className="text-muted-foreground">
          Failed to generate a lesson plan. Please try again.
        </p>
        <Button
          onClick={() => router.push(`/dashboard/courses/${courseId}/tutor`)}
        >
          Back to Tutor
        </Button>
      </div>
    );
  }

  // Intro screen: show lesson plan overview before starting
  if (showIntro && plan) {
    return (
      <div className="flex flex-col h-[calc(100vh-4rem)] overflow-y-auto">
        <LessonPlanOverview
          plan={plan}
          assessmentReadiness={assessmentReadiness}
          onBegin={() => {
            setShowIntro(false);
            populateBlocks(session);
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Progress bar */}
      <SessionProgressBar
        currentConceptIndex={currentConceptIndex}
        totalConcepts={plan?.concepts.length ?? 0}
        conceptTitle={currentConcept?.title ?? session.mode.replace("_", " ")}
        elapsedSeconds={elapsedSeconds}
        onPause={handlePause}
        onEnd={handleEnd}
      />

      {/* Block stream */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
          {/* Diagnostic mode */}
          {isDiagnostic && (
            <DiagnosticView
              sessionId={sessionId}
              courseId={courseId}
              targetAssessmentId={session?.target_assessment_id ?? null}
              onComplete={handleDiagnosticComplete}
              onFillGaps={
                session?.target_assessment_id ? handleFillGaps : undefined
              }
              onBackToCourse={() =>
                router.push(`/dashboard/courses/${courseId}`)
              }
            />
          )}

          {/* Lesson blocks */}
          {blocks.map((block) => {
            let element: React.ReactNode;
            switch (block.type) {
              case "teaching":
                element = (
                  <TeachingBlock
                    content={block.content}
                    approach={currentConcept?.teaching_approach}
                  />
                );
                break;
              case "check":
                if (block.block?.question) {
                  element = (
                    <CheckQuestion
                      question={block.block.question}
                      sessionId={sessionId}
                      onAnswered={handleAnswered}
                    />
                  );
                } else {
                  element = (
                    <TeachingBlock content={block.content} />
                  );
                }
                break;
              case "feedback":
                element = (
                  <TeachingBlock content={block.content} />
                );
                break;
              case "reteach":
                element = (
                  <ReteachBlock content={block.content} />
                );
                break;
              case "practice":
                element = (
                  <PracticeBlock content={block.content} />
                );
                break;
              case "summary":
                element = (
                  <SummaryBlock
                    content={block.content}
                    questionsAsked={block.questionsAsked ?? 0}
                    questionsCorrect={block.questionsCorrect ?? 0}
                    mastery={block.mastery}
                  />
                );
                break;
              case "transition":
                element = (
                  <TransitionBlock
                    content={block.content}
                    nextConceptTitle={block.nextConceptTitle ?? ""}
                    estimatedMinutes={block.estimatedMinutes}
                    onStart={block.onStart}
                  />
                );
                break;
              case "chat_response":
                element = (
                  <ChatResponse
                    userMessage={block.userMessage ?? ""}
                    response={block.content}
                    relevance={block.relevance ?? "on_topic"}
                  />
                );
                break;
              case "complete":
                element = (
                  <Card className="border-green-200 dark:border-green-800">
                    <CardContent className="flex items-center gap-3 py-6">
                      <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0" />
                      <p className="text-sm font-medium">
                        {block.content}
                      </p>
                    </CardContent>
                  </Card>
                );
                break;
              default:
                element = (
                  <TeachingBlock content={block.content} />
                );
            }
            return (
              <div key={block.id} id={block.id}>
                {element}
              </div>
            );
          })}

          {/* Loading indicator for on-demand block fetching */}
          {fetchingBlock && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {/* Continue button: advance to next chunk of content */}
          {!isWaitingForAnswer &&
            !fetchingBlock &&
            !ending &&
            blocks.length > 0 &&
            !blocks.some((b) => b.type === "complete") &&
            session?.lesson_plan && (() => {
              const concept = session.lesson_plan!.concepts[currentConceptIndex];
              if (concept?.generated_content) {
                // Pre-generated path: check if there are more blocks to reveal
                const consumed = conceptBlocksConsumed.current;
                const total = concept.generated_content.blocks.length;
                if (consumed >= total) return null;
                return (
                  <div className="flex justify-center">
                    <Button
                      onClick={() => {
                        renderBlocksUntilCheck(
                          concept.generated_content!.blocks,
                          conceptBlocksConsumed.current,
                          false,
                        );
                      }}
                      variant="outline"
                    >
                      Continue
                    </Button>
                  </div>
                );
              }
              // On-demand path
              return (
                <div className="flex justify-center">
                  <Button onClick={loadNextBlockFromApi} variant="outline">
                    Continue
                  </Button>
                </div>
              );
            })()}

          {/* End session loading indicator */}
          {ending && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>
      </div>

      {/* Chat input */}
      <ChatInput onSend={handleChat} disabled={ending} />

      {/* 60 minute break modal */}
      <Dialog open={showBreakModal} onOpenChange={setShowBreakModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Take a break?</DialogTitle>
            <DialogDescription>
              You&apos;ve been studying for an hour — solid effort. Taking a
              short break can help you retain what you&apos;ve learned.
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-3 justify-end">
            <Button
              variant="outline"
              onClick={() => setShowBreakModal(false)}
            >
              Continue
            </Button>
            <Button onClick={handleEnd}>End Session</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Session summary overlay */}
      {showSummary && summaryData && (
        <SessionSummary
          summary={summaryData}
          onBackToCourse={() =>
            router.push(`/dashboard/courses/${courseId}`)
          }
          onStartAnother={() =>
            router.push(`/dashboard/courses/${courseId}/tutor`)
          }
          onRetestDiagnostic={
            session?.target_assessment_id
              ? handleRetestDiagnostic
              : undefined
          }
        />
      )}
    </div>
  );
}
