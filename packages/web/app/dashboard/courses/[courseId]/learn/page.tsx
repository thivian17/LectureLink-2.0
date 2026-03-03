"use client";

import { useParams } from "next/navigation";
import { LearnSession } from "@/components/learn/session/LearnSession";

export default function LearnPage() {
  const params = useParams<{ courseId: string }>();

  return (
    <div className="py-2">
      <LearnSession courseId={params.courseId} />
    </div>
  );
}
