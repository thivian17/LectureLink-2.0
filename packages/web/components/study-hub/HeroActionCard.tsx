"use client";

import Link from "next/link";
import {
  UploadCloud,
  FileCheck,
  BookOpen,
  AlertTriangle,
  Brain,
  ArrowRight,
} from "lucide-react";
import type { StudyAction } from "@/types/database";

const ICON_MAP: Record<string, typeof UploadCloud> = {
  upload_syllabus: UploadCloud,
  review_syllabus: FileCheck,
  upload_lectures: BookOpen,
  assessment_prep: AlertTriangle,
  take_quiz: Brain,
  study_weak_concept: Brain,
};

interface HeroActionCardProps {
  action: StudyAction;
}

export function HeroActionCard({ action }: HeroActionCardProps) {
  const Icon = ICON_MAP[action.action_type] ?? BookOpen;

  return (
    <Link href={action.cta_url} className="block group">
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-blue-700 to-blue-500 p-4 text-white shadow-sm shadow-blue-500/20 transition-shadow hover:shadow-md hover:shadow-blue-500/25">
        {/* Decorative glow */}
        <div className="absolute -top-10 -right-10 h-32 w-32 rounded-full bg-white/10 blur-2xl" />

        <div className="relative flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            {/* Icon container */}
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/15">
              <Icon className="h-5 w-5" />
            </div>
            {/* Text */}
            <div className="min-w-0">
              <p className="font-semibold leading-tight">{action.title}</p>
              <p className="text-sm text-blue-200 mt-0.5 truncate">
                {action.description}
              </p>
            </div>
          </div>
          {/* Arrow */}
          <ArrowRight className="h-5 w-5 shrink-0 text-blue-200 transition-transform group-hover:translate-x-0.5" />
        </div>
      </div>
    </Link>
  );
}
