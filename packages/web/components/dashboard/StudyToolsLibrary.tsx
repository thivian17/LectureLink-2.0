"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  GraduationCap,
  ClipboardCheck,
  MessageSquare,
  Search,
  Pencil,
  Brain,
  ChevronRight,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { getCourses } from "@/lib/api";
import type { Course } from "@/types/database";

interface Tool {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  coursePath: string;
  comingSoon?: boolean;
}

const tools: Tool[] = [
  {
    icon: MessageSquare,
    title: "Assessment Prep",
    description: "Diagnose gaps, teach step by step, test understanding",
    coursePath: "/assessment-prep",
  },
  {
    icon: Brain,
    title: "Daily Study Session",
    description: "15-min guided sessions targeting concepts at risk of fading",
    coursePath: "/learn",
  },
  {
    icon: ClipboardCheck,
    title: "Smart Quizzes",
    description: "Questions from your lectures, adapting to your level",
    coursePath: "/quizzes",
  },
  {
    icon: Search,
    title: "Ask Your Lectures",
    description: "Answers sourced from your material with citations",
    coursePath: "/chat",
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
  const router = useRouter();
  const [courses, setCourses] = useState<Course[]>([]);
  const [openTool, setOpenTool] = useState<string | null>(null);

  useEffect(() => {
    getCourses()
      .then(setCourses)
      .catch(() => {});
  }, []);

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Study Tools</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {tools.map((tool) => {
          const Icon = tool.icon;
          const disabled = tool.comingSoon || courses.length === 0;

          const cardContent = (
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
            return <div key={tool.title}>{cardContent}</div>;
          }

          // Single course — navigate directly
          if (courses.length === 1) {
            return (
              <div
                key={tool.title}
                role="button"
                tabIndex={0}
                onClick={() =>
                  router.push(
                    `/dashboard/courses/${courses[0].id}${tool.coursePath}`,
                  )
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    router.push(
                      `/dashboard/courses/${courses[0].id}${tool.coursePath}`,
                    );
                  }
                }}
              >
                {cardContent}
              </div>
            );
          }

          // Multiple courses — show picker popover
          return (
            <Popover
              key={tool.title}
              open={openTool === tool.title}
              onOpenChange={(open) => setOpenTool(open ? tool.title : null)}
            >
              <PopoverTrigger asChild>
                <div role="button" tabIndex={0}>
                  {cardContent}
                </div>
              </PopoverTrigger>
              <PopoverContent className="w-56 p-1" align="center">
                <p className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                  Choose a course
                </p>
                {courses.map((course) => (
                  <button
                    key={course.id}
                    onClick={() => {
                      setOpenTool(null);
                      router.push(
                        `/dashboard/courses/${course.id}${tool.coursePath}`,
                      );
                    }}
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent transition-colors text-left"
                  >
                    <span className="truncate flex-1">
                      {course.code ? `${course.code} — ` : ""}
                      {course.name}
                    </span>
                    <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                  </button>
                ))}
              </PopoverContent>
            </Popover>
          );
        })}
      </div>
    </section>
  );
}
