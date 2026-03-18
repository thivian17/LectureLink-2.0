"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { LearnSession } from "@/components/learn/session/LearnSession";

export default function LearnPage() {
  const params = useParams<{ courseId: string }>();
  const searchParams = useSearchParams();

  const initialTargetAssessmentId = searchParams.get("assessmentId") ?? undefined;
  const initialTargetConceptIds = useMemo(() => {
    const raw = searchParams.get("concepts");
    return raw ? raw.split(",").filter(Boolean) : undefined;
  }, [searchParams]);

  return (
    <div className="py-2">
      <LearnSession
        courseId={params.courseId}
        initialTargetAssessmentId={initialTargetAssessmentId}
        initialTargetConceptIds={initialTargetConceptIds}
      />
    </div>
  );
}
