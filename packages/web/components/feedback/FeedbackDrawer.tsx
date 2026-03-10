"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { AnnotationCanvas } from "@/components/feedback/AnnotationCanvas";
import { useConsoleErrors } from "@/lib/use-console-errors";
import {
  uploadFeedbackScreenshot,
  submitFeedback,
} from "@/lib/api";

type FeedbackType = "bug" | "feature" | "ux" | "praise";

const feedbackTypes: {
  type: FeedbackType;
  emoji: string;
  label: string;
  hint: string;
}[] = [
  { type: "bug", emoji: "\u{1F41B}", label: "Bug", hint: "Something isn't working" },
  { type: "feature", emoji: "\u{1F4A1}", label: "Feature", hint: "I have an idea" },
  { type: "ux", emoji: "\u{1F615}", label: "Confusing", hint: "I don't understand this" },
  { type: "praise", emoji: "\u{1F389}", label: "Praise", hint: "This is great!" },
];

const placeholders: Record<FeedbackType, string> = {
  bug: "What happened? What did you expect to happen?",
  feature: "Describe the feature you'd like to see...",
  ux: "What was confusing? What would make it clearer?",
  praise: "What did you love?",
};

interface FeedbackDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function FeedbackDrawer({ open, onClose }: FeedbackDrawerProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [feedbackType, setFeedbackType] = useState<FeedbackType | null>(null);
  const [screenshotDataUrl, setScreenshotDataUrl] = useState<string | null>(null);
  const [screenshotBlob, setScreenshotBlob] = useState<Blob | null>(null);
  const [annotationBounds, setAnnotationBounds] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);
  const [description, setDescription] = useState("");
  const [isCapturing, setIsCapturing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const getConsoleErrors = useConsoleErrors();

  const resetState = useCallback(() => {
    setStep(1);
    setFeedbackType(null);
    setScreenshotDataUrl(null);
    setScreenshotBlob(null);
    setAnnotationBounds(null);
    setDescription("");
    setSubmitted(false);
  }, []);

  // Capture screenshot as soon as the drawer opens (before the Sheet overlay
  // is painted) so html2canvas captures the actual page, not the drawer.
  const captureScreenshot = useCallback(async () => {
    setIsCapturing(true);
    try {
      const html2canvas = (await import("html2canvas")).default;
      // Hide the Sheet portal so it doesn't appear in the screenshot
      const sheetOverlay = document.querySelector<HTMLElement>(
        "[data-slot='sheet-overlay']",
      );
      const sheetContent = document.querySelector<HTMLElement>(
        "[data-slot='sheet-content']",
      );
      if (sheetOverlay) sheetOverlay.style.display = "none";
      if (sheetContent) sheetContent.style.display = "none";

      const canvas = await html2canvas(document.body, {
        useCORS: true,
        scale: 0.5,
        ignoreElements: (el) =>
          el.closest("[data-slot='sheet-overlay']") !== null ||
          el.closest("[data-slot='sheet-content']") !== null,
      });

      // Restore visibility
      if (sheetOverlay) sheetOverlay.style.display = "";
      if (sheetContent) sheetContent.style.display = "";

      canvas.toBlob(
        (blob) => {
          if (blob) {
            setScreenshotBlob(blob);
            setScreenshotDataUrl(canvas.toDataURL("image/png"));
          }
          setIsCapturing(false);
        },
        "image/png",
      );
    } catch {
      setIsCapturing(false);
    }
  }, []);

  // Capture as soon as drawer opens so the screenshot is ready by step 2
  useEffect(() => {
    if (open && !screenshotDataUrl && !isCapturing) {
      captureScreenshot();
    }
  }, [open, screenshotDataUrl, isCapturing, captureScreenshot]);

  function handleTypeSelect(type: FeedbackType) {
    setFeedbackType(type);
    setStep(2);
  }

  function handleAnnotationComplete(
    _annotatedUrl: string,
    bounds: { x: number; y: number; width: number; height: number } | null,
  ) {
    setAnnotationBounds(bounds);
    setStep(3);
  }

  function handleRetake() {
    setScreenshotDataUrl(null);
    setScreenshotBlob(null);
    setAnnotationBounds(null);
    captureScreenshot();
  }

  async function handleSubmit() {
    setIsSubmitting(true);
    try {
      let storagePath: string | undefined;
      if (screenshotBlob) {
        const { storage_path } = await uploadFeedbackScreenshot(screenshotBlob);
        storagePath = storage_path;
      }
      await submitFeedback({
        type: feedbackType!,
        description,
        page_url: window.location.href,
        page_title: document.title,
        screenshot_storage_path: storagePath,
        annotation_bounds: annotationBounds ?? undefined,
        browser_info: {
          user_agent: navigator.userAgent,
          viewport_width: window.innerWidth,
          viewport_height: window.innerHeight,
          platform: navigator.platform,
        },
        console_errors: getConsoleErrors(),
      });
      setSubmitted(true);
      setTimeout(() => {
        onClose();
        setTimeout(resetState, 300);
      }, 2000);
    } catch {
      toast.error("Failed to submit feedback. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) {
      onClose();
      setTimeout(resetState, 300);
    }
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="right" className="w-[400px] sm:w-[400px] overflow-auto">
        <SheetHeader>
          <SheetTitle>Send Feedback</SheetTitle>
          <SheetDescription>
            {step === 1 && "What kind of feedback do you have?"}
            {step === 2 && "Annotate your screenshot"}
            {step === 3 && "Tell us more"}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 space-y-4 px-1">
          {submitted ? (
            <div className="flex flex-col items-center justify-center gap-3 py-12">
              <CheckCircle2 className="h-16 w-16 text-green-500" />
              <h3 className="text-lg font-semibold">Thanks for your feedback!</h3>
              <p className="text-sm text-muted-foreground">
                We&apos;ll look into it and get back to you.
              </p>
            </div>
          ) : (
            <>
              {/* Step 1: Type Selection */}
              {step === 1 && (
                <div className="grid grid-cols-2 gap-3">
                  {feedbackTypes.map((ft) => (
                    <button
                      key={ft.type}
                      type="button"
                      onClick={() => handleTypeSelect(ft.type)}
                      className={`flex flex-col items-center gap-2 rounded-lg border p-4 text-center transition-colors hover:bg-accent ${
                        feedbackType === ft.type
                          ? "ring-2 ring-primary bg-primary/5"
                          : ""
                      }`}
                    >
                      <span className="text-2xl">{ft.emoji}</span>
                      <span className="text-sm font-medium">{ft.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {ft.hint}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {/* Step 2: Screenshot */}
              {step === 2 && (
                <div className="space-y-4">
                  {isCapturing ? (
                    <div className="flex flex-col items-center gap-3 py-8">
                      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                      <p className="text-sm text-muted-foreground">
                        Capturing screenshot...
                      </p>
                    </div>
                  ) : screenshotDataUrl ? (
                    <AnnotationCanvas
                      screenshotDataUrl={screenshotDataUrl}
                      onAnnotationComplete={handleAnnotationComplete}
                      onRetake={handleRetake}
                    />
                  ) : null}
                  <button
                    type="button"
                    className="text-xs text-muted-foreground underline hover:text-foreground"
                    onClick={() => {
                      setScreenshotDataUrl(null);
                      setScreenshotBlob(null);
                      setStep(3);
                    }}
                  >
                    Skip screenshot
                  </button>
                </div>
              )}

              {/* Step 3: Description */}
              {step === 3 && (
                <div className="space-y-4">
                  {screenshotDataUrl && (
                    <img
                      src={screenshotDataUrl}
                      alt="Annotated screenshot"
                      className="w-full max-h-32 object-contain rounded border"
                    />
                  )}
                  <div className="relative">
                    <textarea
                      placeholder={
                        feedbackType ? placeholders[feedbackType] : ""
                      }
                      value={description}
                      onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDescription(e.target.value)}
                      rows={5}
                      className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
                    />
                    <span className="absolute bottom-2 right-3 text-xs text-muted-foreground">
                      {description.length}
                    </span>
                  </div>
                  <Button
                    onClick={handleSubmit}
                    disabled={description.length < 10 || isSubmitting}
                    className="w-full"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Submitting...
                      </>
                    ) : (
                      "Submit Feedback"
                    )}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
