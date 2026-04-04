"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  GraduationCap,
  ClipboardCheck,
  Target,
  MessageSquare,
  Pencil,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getCourses } from "@/lib/api";

interface Tool {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  /** Path suffix appended to /dashboard/courses/[courseId] */
  coursePath: string;
  comingSoon?: boolean;
}

const tools: Tool[] = [
  {
    icon: GraduationCap,
    title: "Learn Session",
    description: "AI-guided study sessions",
    coursePath: "/learn",
  },
  {
    icon: ClipboardCheck,
    title: "Practice Tests",
    description: "Test your knowledge",
    coursePath: "/quizzes",
  },
  {
    icon: Target,
    title: "Assessment Prep",
    description: "Targeted exam preparation",
    coursePath: "/readiness",
  },
  {
    icon: MessageSquare,
    title: "Tutor Chat",
    description: "Ask about any concept",
    coursePath: "/tutor",
  },
  {
    icon: Pencil,
    title: "Discussion Help",
    description: "Craft discussion responses",
    coursePath: "",
    comingSoon: true,
  },
];

export function StudyToolsLibrary() {
  const [firstCourseId, setFirstCourseId] = useState<string | null>(null);

  useEffect(() => {
    getCourses()
      .then((courses) => {
        if (courses.length > 0) setFirstCourseId(courses[0].id);
      })
      .catch(() => {});
  }, []);

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Study Tools</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {tools.map((tool) => {
          const Icon = tool.icon;
          const disabled = tool.comingSoon || !firstCourseId;
          const href = firstCourseId
            ? `/dashboard/courses/${firstCourseId}${tool.coursePath}`
            : "/dashboard";

          const content = (
            <Card
              className={`p-3 text-center space-y-2 hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer relative ${
                disabled ? "opacity-60" : ""
              }`}
            >
              {tool.comingSoon && (
                <Badge
                  variant="secondary"
                  className="absolute top-1.5 right-1.5 text-[10px]"
                >
                  Soon
                </Badge>
              )}
              <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Icon className="h-5 w-5 text-primary" />
              </div>
              <p className="text-sm font-medium">{tool.title}</p>
              <p className="text-xs text-muted-foreground line-clamp-2">
                {tool.description}
              </p>
            </Card>
          );

          if (disabled) {
            return <div key={tool.title}>{content}</div>;
          }

          return (
            <Link key={tool.title} href={href}>
              {content}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
