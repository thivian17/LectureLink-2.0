import { Search } from "lucide-react";

/* -------------------------------------------------------------------------- */
/*  1. TutorPreview                                                           */
/* -------------------------------------------------------------------------- */

export function TutorPreview() {
  return (
    <div className="flex flex-col gap-2 p-4">
      <div className="flex items-center gap-2 mb-1">
        <span className="rounded-full bg-primary/10 text-primary text-[10px] font-medium px-2 py-0.5">
          Diagnostic Mode
        </span>
        <span className="text-xs text-muted-foreground">Binary Search Trees</span>
      </div>

      {/* Tutor */}
      <div className="flex justify-start">
        <div className="bg-muted rounded-2xl rounded-tl-sm p-3 max-w-[85%]">
          <p className="text-sm">
            Can you explain how a binary search tree maintains its ordering
            property?
          </p>
        </div>
      </div>

      {/* Student */}
      <div className="flex justify-end">
        <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-sm p-3 max-w-[85%]">
          <p className="text-sm">
            The left child is always smaller and the right child is always larger
            than the parent?
          </p>
        </div>
      </div>

      {/* Tutor */}
      <div className="flex justify-start">
        <div className="bg-muted rounded-2xl rounded-tl-sm p-3 max-w-[85%]">
          <p className="text-sm">
            Good start! What happens when you insert a value equal to the current
            node?
          </p>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  2. ReadinessPreview                                                       */
/* -------------------------------------------------------------------------- */

function ProgressRing({
  percent,
  color,
  label,
}: {
  percent: number;
  color: string;
  label: string;
}) {
  const r = 28;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="68" height="68" viewBox="0 0 68 68">
        <circle
          cx="34"
          cy="34"
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth="5"
          className="text-muted"
        />
        <circle
          cx="34"
          cy="34"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 34 34)"
        />
        <text
          x="34"
          y="38"
          textAnchor="middle"
          className="fill-foreground text-xs font-semibold"
        >
          {percent}%
        </text>
      </svg>
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}

export function ReadinessPreview() {
  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">Midterm Exam</span>
        <span className="rounded-full bg-destructive/10 text-destructive text-[10px] font-medium px-2 py-0.5">
          3 days away
        </span>
      </div>

      <div className="flex justify-between px-1">
        <ProgressRing percent={82} color="hsl(220 70% 55%)" label="Coverage" />
        <ProgressRing percent={65} color="hsl(35 90% 55%)" label="Practice" />
        <ProgressRing percent={71} color="hsl(145 60% 45%)" label="Freshness" />
        <ProgressRing percent={55} color="hsl(270 60% 55%)" label="Effort" />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Overall Readiness</span>
          <span className="font-semibold">68%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
          <div className="h-full rounded-full bg-primary" style={{ width: "68%" }} />
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  3. QuizPreview                                                            */
/* -------------------------------------------------------------------------- */

export function QuizPreview() {
  const options = [
    { label: "A", text: "In-order" },
    { label: "B", text: "Pre-order", selected: true },
    { label: "C", text: "Post-order" },
    { label: "D", text: "Level-order" },
  ];

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Q3 of 10</span>
        <span className="rounded-full bg-muted text-muted-foreground text-[10px] font-medium px-2 py-0.5">
          Adaptive &middot; Medium
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div className="h-full rounded-full bg-primary" style={{ width: "30%" }} />
      </div>

      <p className="text-sm font-medium">
        Which traversal visits the root node first?
      </p>

      <div className="space-y-2">
        {options.map((opt) => (
          <div
            key={opt.label}
            className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm ${
              opt.selected
                ? "border-primary bg-primary/5"
                : "border-border"
            }`}
          >
            <div
              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                opt.selected
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-muted-foreground/40"
              }`}
            >
              {opt.selected && (
                <div className="h-2 w-2 rounded-full bg-primary-foreground" />
              )}
            </div>
            <span>{opt.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  4. SessionPreview                                                         */
/* -------------------------------------------------------------------------- */

export function SessionPreview() {
  const concepts = [
    { name: "Binary Search Trees", dot: "bg-red-500", status: "needs work" },
    { name: "Graph Traversal", dot: "bg-amber-500", status: "developing" },
    { name: "Sorting Algorithms", dot: "bg-green-500", status: "strong" },
  ];

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">Today&apos;s Session</span>
        <span className="rounded-full bg-muted text-muted-foreground text-[10px] font-medium px-2 py-0.5">
          ~15 min
        </span>
      </div>

      <div className="space-y-2.5">
        {concepts.map((c) => (
          <div key={c.name} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${c.dot}`} />
              <span className="text-sm">{c.name}</span>
            </div>
            <span className="text-[10px] text-muted-foreground">{c.status}</span>
          </div>
        ))}
      </div>

      <div className="rounded-lg bg-muted/50 px-3 py-1.5">
        <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
          Flash Review
        </span>
      </div>

      <div className="text-right">
        <span className="text-primary font-semibold text-sm">+45 XP earned</span>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  5. SearchPreview                                                          */
/* -------------------------------------------------------------------------- */

export function SearchPreview() {
  return (
    <div className="p-4 space-y-3">
      {/* Search input */}
      <div className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2">
        <Search className="h-4 w-4 text-muted-foreground shrink-0" />
        <span className="text-sm">What is dynamic programming?</span>
      </div>

      {/* Result 1 */}
      <div className="rounded-lg border border-border p-3 space-y-1">
        <p className="text-sm font-semibold">Lecture 7 &mdash; Algorithms</p>
        <p className="text-xs text-muted-foreground">Slide 14 &middot; 34:20</p>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Dynamic programming breaks complex problems into overlapping
          subproblems, storing results to avoid redundant computation&hellip;
        </p>
      </div>

      {/* Result 2 (faded) */}
      <div className="rounded-lg border border-border p-3 opacity-50">
        <p className="text-sm font-semibold">
          Lecture 12 &mdash; Advanced Topics
        </p>
        <p className="text-xs text-muted-foreground">Slide 3</p>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  6. SyllabusPreview                                                        */
/* -------------------------------------------------------------------------- */

export function SyllabusPreview() {
  const rows = [
    { assessment: "Midterm", date: "Oct 15", weight: "30%", readiness: "68%", color: "bg-amber-100 text-amber-700" },
    { assessment: "Quiz 3", date: "Oct 8", weight: "5%", readiness: "91%", color: "bg-green-100 text-green-700" },
    { assessment: "Assignment 4", date: "Oct 20", weight: "10%", readiness: "45%", color: "bg-red-100 text-red-700" },
    { assessment: "Final Exam", date: "Dec 12", weight: "40%", readiness: "\u2014", color: "bg-muted text-muted-foreground" },
  ];

  return (
    <div className="p-4 space-y-3">
      <span className="inline-block rounded-full bg-primary/10 text-primary text-[10px] font-medium px-2 py-0.5">
        Auto-extracted from syllabus
      </span>

      <div className="rounded-lg border border-border overflow-hidden text-xs">
        {/* Header */}
        <div className="grid grid-cols-4 gap-2 bg-muted/80 px-3 py-2 font-medium text-muted-foreground">
          <span>Assessment</span>
          <span>Date</span>
          <span>Weight</span>
          <span>Readiness</span>
        </div>

        {/* Rows */}
        {rows.map((row, i) => (
          <div
            key={row.assessment}
            className={`grid grid-cols-4 gap-2 px-3 py-2 ${i % 2 === 1 ? "bg-muted/50" : ""}`}
          >
            <span className="font-medium truncate">{row.assessment}</span>
            <span className="text-muted-foreground">{row.date}</span>
            <span className="text-muted-foreground">{row.weight}</span>
            <span
              className={`inline-flex w-fit items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium ${row.color}`}
            >
              {row.readiness}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
