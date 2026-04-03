import {
  Code,
  Trophy,
  BarChart3,
  FileText,
  GitBranch,
  Upload,
} from "lucide-react";

const features = [
  {
    icon: Code,
    title: "Code Practice",
    desc: "Built-in editor with AI grading, line-by-line feedback, and progressive hints.",
  },
  {
    icon: Trophy,
    title: "Streaks, XP & Badges",
    desc: "Daily streaks, leveling, and achievements that keep you showing up.",
  },
  {
    icon: BarChart3,
    title: "Study Dashboard",
    desc: "Deadlines, readiness scores, and your best next moves \u2014 one screen.",
  },
  {
    icon: FileText,
    title: "Course Materials",
    desc: "Upload readings and problem sets. Everything becomes searchable.",
  },
  {
    icon: GitBranch,
    title: "Concept Mapping",
    desc: "Links the same topic across lectures into a unified course map.",
  },
  {
    icon: Upload,
    title: "Bulk Upload",
    desc: "Drop all your files at once \u2014 audio and slides get matched automatically.",
  },
];

export function SecondaryFeatures() {
  return (
    <section className="py-20">
      <div className="mx-auto max-w-5xl px-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-border bg-background p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
            >
              <f.icon className="h-5 w-5 text-primary" />
              <p className="mt-3 text-sm font-semibold text-foreground">
                {f.title}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
