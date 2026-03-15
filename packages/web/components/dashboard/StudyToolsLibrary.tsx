"use client";

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

interface Tool {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  href: string;
  comingSoon?: boolean;
}

const tools: Tool[] = [
  {
    icon: GraduationCap,
    title: "Learn Session",
    description: "AI-guided study sessions",
    href: "/dashboard",
  },
  {
    icon: ClipboardCheck,
    title: "Practice Tests",
    description: "Test your knowledge",
    href: "/dashboard",
  },
  {
    icon: Target,
    title: "Assessment Prep",
    description: "Targeted exam preparation",
    href: "/dashboard",
  },
  {
    icon: MessageSquare,
    title: "Tutor Chat",
    description: "Ask about any concept",
    href: "/dashboard",
  },
  {
    icon: Pencil,
    title: "Discussion Help",
    description: "Craft discussion responses",
    href: "/dashboard",
    comingSoon: true,
  },
];

export function StudyToolsLibrary() {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Study Tools</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {tools.map((tool) => {
          const Icon = tool.icon;
          const content = (
            <Card
              className={`p-3 text-center space-y-2 hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer relative ${
                tool.comingSoon ? "opacity-60" : ""
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

          if (tool.comingSoon) {
            return <div key={tool.title}>{content}</div>;
          }

          return (
            <Link key={tool.title} href={tool.href}>
              {content}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
