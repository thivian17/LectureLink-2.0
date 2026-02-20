"use client";

import { useState } from "react";
import Link from "next/link";
import { format } from "date-fns";
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Lightbulb,
  ImageIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { formatDuration } from "@/lib/format";

interface LectureSummaryProps {
  title: string;
  summary: string | null;
  lectureDate: string | null;
  lectureNumber: number | null;
  durationSeconds: number | null;
  conceptCount: number;
  slideCount: number;
  segmentCount: number;
  courseId: string;
}

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function LectureSummary({
  title,
  summary,
  lectureDate,
  lectureNumber,
  durationSeconds,
  conceptCount,
  slideCount,
  segmentCount,
  courseId,
}: LectureSummaryProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border-b bg-background px-4 py-3">
      <div className="flex items-center gap-3 mb-2">
        <Link href={`/dashboard/courses/${courseId}/lectures`}>
          <Button variant="ghost" size="sm" className="gap-1 px-2">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-semibold truncate">{title}</h1>
        </div>
        {lectureNumber != null && (
          <Badge variant="secondary" className="shrink-0">
            Lec #{lectureNumber}
          </Badge>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground ml-11">
        {lectureDate && (
          <span>{format(parseLocalDate(lectureDate), "MMM d, yyyy")}</span>
        )}
        {durationSeconds != null && (
          <span className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" />
            {formatDuration(durationSeconds)}
          </span>
        )}
        {slideCount > 0 && (
          <span className="flex items-center gap-1">
            <ImageIcon className="h-3.5 w-3.5" />
            {slideCount} slides
          </span>
        )}
        {conceptCount > 0 && (
          <span className="flex items-center gap-1">
            <Lightbulb className="h-3.5 w-3.5" />
            {conceptCount} concepts
          </span>
        )}
        {segmentCount > 0 && (
          <span className="flex items-center gap-1">
            <FileText className="h-3.5 w-3.5" />
            {segmentCount} segments
          </span>
        )}
      </div>

      {summary && (
        <Collapsible open={isOpen} onOpenChange={setIsOpen} className="mt-2 ml-11">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-1 px-2 text-xs h-7">
              {isOpen ? (
                <>
                  <ChevronUp className="h-3 w-3" />
                  Hide Summary
                </>
              ) : (
                <>
                  <ChevronDown className="h-3 w-3" />
                  Show Summary
                </>
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2">
            <p className="text-sm text-muted-foreground leading-relaxed">
              {summary}
            </p>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}
