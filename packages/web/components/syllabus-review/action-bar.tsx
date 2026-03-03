"use client";

import { Loader2, RefreshCw, CheckCircle2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ActionBarProps {
  totalAssessments: number;
  highConfidenceCount: number;
  needsReviewCount: number;
  ambiguousDateCount: number;
  isSaving: boolean;
  onAcceptHighConfidence: () => void;
  onSave: () => void;
  onReExtract: () => void;
  hideConfidence?: boolean;
}

export function ActionBar({
  totalAssessments,
  highConfidenceCount,
  needsReviewCount,
  ambiguousDateCount,
  isSaving,
  onAcceptHighConfidence,
  onSave,
  onReExtract,
  hideConfidence,
}: ActionBarProps) {
  return (
    <div className="fixed bottom-0 left-0 right-0 lg:left-60 z-40 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center justify-between px-4 py-3 gap-4">
        {/* Summary */}
        <p className="text-sm text-muted-foreground hidden sm:block">
          {totalAssessments} assessment{totalAssessments !== 1 ? "s" : ""}{" "}
          extracted
          {!hideConfidence && (
            <>
              <span className="mx-1">&middot;</span>
              <span className="text-green-600">{highConfidenceCount} high confidence</span>
              {needsReviewCount > 0 && (
                <>
                  <span className="mx-1">&middot;</span>
                  <span className="text-amber-600">{needsReviewCount} need review</span>
                </>
              )}
              {ambiguousDateCount > 0 && (
                <>
                  <span className="mx-1">&middot;</span>
                  <span className="text-red-600">
                    {ambiguousDateCount} ambiguous date{ambiguousDateCount !== 1 ? "s" : ""}
                  </span>
                </>
              )}
            </>
          )}
        </p>

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={onReExtract}
            disabled={isSaving}
          >
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            Re-extract
          </Button>
          {!hideConfidence && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onAcceptHighConfidence}
              disabled={isSaving}
            >
              <CheckCircle2 className="mr-2 h-3.5 w-3.5" />
              Accept All High Confidence
            </Button>
          )}
          <Button size="sm" onClick={onSave} disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="mr-2 h-3.5 w-3.5" />
            )}
            Save &amp; Continue
          </Button>
        </div>
      </div>
    </div>
  );
}
