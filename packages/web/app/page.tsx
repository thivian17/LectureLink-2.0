"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import {
  BookOpen,
  Upload,
  Brain,
  Target,
  Sparkles,
  Search,
  CalendarCheck,
  GraduationCap,
  Shield,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Navbar } from "@/components/landing/navbar";
import { Footer } from "@/components/landing/footer";
import { Feature197 } from "@/components/accordion-feature-section";
import { ZoomParallax } from "@/components/zoom-parallax";

const Casestudies = dynamic(() => import("@/components/case-studies"), {
  ssr: false,
});
const RuixenStats = dynamic(() => import("@/components/ruixen-stats"), {
  ssr: false,
});

/* Try importing Track B components; fall back to placeholders */
let FeaturePreviews: Record<string, React.ComponentType> = {};
let SecondaryFeatures: React.ComponentType | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  FeaturePreviews = require("@/components/landing/feature-previews");
} catch {
  /* Track B hasn't created this yet */
}
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("@/components/landing/secondary-features");
  SecondaryFeatures = mod.SecondaryFeatures ?? mod.default ?? null;
} catch {
  /* Track B hasn't created this yet */
}

// ─── Feature data for accordion ────────────────────────────────────────
const FEATURE_KEYS = [
  "AiTutorPreview",
  "ExamReadinessPreview",
  "SmartQuizzesPreview",
  "DailySessionsPreview",
  "AskLecturesPreview",
  "SyllabusAwarePreview",
] as const;

const FEATURES = [
  {
    id: 1,
    title: "AI Tutor",
    description:
      "One-on-one study sessions that diagnose your knowledge gaps, teach concepts step by step, and test your understanding — all pulled from your actual lecture content. It asks the right questions, catches misconceptions, and adapts on the fly across three study modes.",
    image: "",
  },
  {
    id: 2,
    title: "Exam Readiness",
    description:
      "Instead of a single grade, four independent signals — Coverage, Practice, Freshness, and Effort — give you an honest picture of where you stand before each assessment. The model updates in real-time as you study.",
    image: "",
  },
  {
    id: 3,
    title: "Smart Quizzes",
    description:
      "Every question is generated from your lectures — not a generic question bank. The system tracks what you know at the concept level and quietly adjusts difficulty so you're always working at the edge of your understanding.",
    image: "",
  },
  {
    id: 4,
    title: "Daily Study Sessions",
    description:
      "Fifteen-minute guided sessions that surface the concepts most at risk of fading. Each session blends flash reviews, focused teaching, and a quick quiz — then shows you exactly what moved.",
    image: "",
  },
  {
    id: 5,
    title: "Ask Your Lectures",
    description:
      'Type a question and get an answer sourced directly from your course material — with the exact lecture, timestamp, and slide number cited. It searches across everything you\'ve uploaded.',
    image: "",
  },
  {
    id: 6,
    title: "Syllabus-Aware",
    description:
      "Upload a syllabus PDF and LectureLink extracts your full schedule, assessments, and grade weights automatically. From that point on, every recommendation, quiz, and study session is aligned to what's actually being graded.",
    image: "",
  },
].map((f, i) => {
  // Attempt to use Track B preview component as image placeholder
  const key = FEATURE_KEYS[i];
  const PreviewComp = FeaturePreviews[key];
  return { ...f, _preview: PreviewComp ?? null };
});

// ─── Tech stack ────────────────────────────────────────────────────────
const TECH_STACK = [
  { name: "Next.js 16", desc: "React framework", icon: Zap },
  { name: "FastAPI", desc: "Python backend", icon: Zap },
  { name: "Gemini AI", desc: "Foundation model", icon: Sparkles },
  { name: "Supabase", desc: "Database & auth", icon: Shield },
  { name: "Redis", desc: "Job queue & cache", icon: Zap },
  { name: "Cloud Run", desc: "Serverless deploy", icon: Target },
  { name: "TypeScript", desc: "End-to-end types", icon: BookOpen },
  { name: "shadcn/ui", desc: "Component system", icon: GraduationCap },
];

// ─── How it works steps ────────────────────────────────────────────────
const STEPS = [
  {
    icon: Upload,
    title: "Upload Syllabus",
    desc: "Drop your PDF. Schedule, assessments, and grade weights are extracted automatically.",
  },
  {
    icon: BookOpen,
    title: "Add Lectures",
    desc: "Upload recordings or slides. The pipeline transcribes, extracts concepts, and indexes everything.",
  },
  {
    icon: Brain,
    title: "Study Smart",
    desc: "AI tutor, adaptive quizzes, and daily sessions — personalized to your weak spots and deadlines.",
  },
  {
    icon: Target,
    title: "Track Readiness",
    desc: "Watch your readiness scores update as you study. Always know where you stand.",
  },
];

// ─── Readiness ring SVG helper ─────────────────────────────────────────
function ReadinessRing({
  pct,
  label,
  color,
}: {
  pct: number;
  label: string;
  color: string;
}) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle
          cx="44"
          cy="44"
          r={r}
          fill="none"
          stroke="currentColor"
          className="text-muted"
          strokeWidth="6"
        />
        <circle
          cx="44"
          cy="44"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          transform="rotate(-90 44 44)"
        />
        <text
          x="44"
          y="44"
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-foreground text-sm font-semibold"
        >
          {pct}%
        </text>
      </svg>
      <span className="text-xs text-muted-foreground font-medium">{label}</span>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// Landing page
// ═══════════════════════════════════════════════════════════════════════
export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      {/* 1. Navbar */}
      <Navbar />

      {/* 2. Hero */}
      <section className="relative pt-32 pb-24 px-6 overflow-hidden">
        <div className="max-w-4xl mx-auto text-center space-y-8">
          <Badge
            variant="secondary"
            className="px-4 py-1.5 text-sm font-medium"
          >
            <Sparkles className="h-3.5 w-3.5 mr-1.5" />
            AI-Powered Study Platform
          </Badge>

          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-[800] tracking-tight leading-[1.08]">
            Know what to study.
            <br />
            <span className="text-primary">Know when to study it.</span>
          </h1>

          <p className="max-w-2xl mx-auto text-lg text-muted-foreground leading-relaxed">
            Upload your syllabus and lectures. LectureLink learns your course,
            tracks what you&apos;ve mastered, and tells you exactly what to focus
            on before every exam.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button
              asChild
              size="lg"
              className="bg-primary text-primary-foreground rounded-lg px-8 text-base font-semibold"
            >
              <Link href="/login">Try It Free</Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="rounded-lg">
              <a href="#features">See How It Works</a>
            </Button>
          </div>

          {/* Tech pills */}
          <div className="flex flex-wrap items-center justify-center gap-2 pt-4">
            {[
              "Next.js 16",
              "FastAPI",
              "Gemini AI",
              "Supabase",
              "TypeScript",
            ].map((t) => (
              <span
                key={t}
                className="px-3 py-1 rounded-full bg-muted text-xs font-medium text-muted-foreground"
              >
                {t}
              </span>
            ))}
          </div>
        </div>

        {/* Decorative gradient blobs */}
        <div className="absolute -top-40 -right-40 h-96 w-96 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-40 -left-40 h-96 w-96 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
      </section>

      {/* 3. Features — Tier 1: Accordion */}
      <section id="features" className="bg-muted">
        <div className="max-w-6xl mx-auto px-6 py-24">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-[800] tracking-tight">
              Everything you need to study smarter
            </h2>
            <p className="mt-4 text-muted-foreground max-w-xl mx-auto">
              Six core features that work together to keep you prepared for every
              assessment.
            </p>
          </div>
          <Feature197 features={FEATURES} />
        </div>

        {/* Tier 2: Secondary features */}
        <div className="max-w-6xl mx-auto px-6 pb-24">
          <p className="text-center text-sm font-semibold text-muted-foreground uppercase tracking-widest mb-8">
            Plus everything else you need
          </p>
          {SecondaryFeatures ? (
            <SecondaryFeatures />
          ) : (
            <div className="rounded-2xl border border-border bg-background p-12 text-center text-muted-foreground">
              {/* TODO: Track B will provide SecondaryFeatures component */}
              Secondary features coming soon
            </div>
          )}
        </div>
      </section>

      {/* 4. Zoom Parallax */}
      <ZoomParallax
        images={[
          {
            src: "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=800&q=80",
            alt: "Students collaborating",
          },
          {
            src: "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=600&q=80",
            alt: "Studying at desk",
          },
          {
            src: "https://images.unsplash.com/photo-1513258496099-48168024aec0?w=600&q=80",
            alt: "Laptop and notes",
          },
          {
            src: "https://images.unsplash.com/photo-1501504905252-473c47e087f8?w=600&q=80",
            alt: "Library study",
          },
          {
            src: "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=600&q=80",
            alt: "Campus life",
          },
          {
            src: "https://images.unsplash.com/photo-1517486808906-6ca8b3f04846?w=600&q=80",
            alt: "Group study",
          },
          {
            src: "https://images.unsplash.com/photo-1488190211105-8b0e65b80b4e?w=600&q=80",
            alt: "Writing notes",
          },
        ]}
      />
      {/* TODO: Replace with actual app screenshots */}

      {/* 5. How It Works */}
      <section id="how" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-[800] tracking-tight">
              From lecture recording to study-ready
            </h2>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {STEPS.map((step, i) => (
              <div key={step.title} className="relative text-center space-y-4">
                {/* Connector line (desktop) */}
                {i < STEPS.length - 1 && (
                  <div className="hidden lg:block absolute top-6 left-[calc(50%+24px)] right-[calc(-50%+24px)] h-px bg-border" />
                )}
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground relative z-10">
                  <step.icon className="h-5 w-5" />
                </div>
                <Badge
                  variant="outline"
                  className="text-xs font-medium tabular-nums"
                >
                  Step {i + 1}
                </Badge>
                <h3 className="text-lg font-semibold tracking-tight">
                  {step.title}
                </h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {step.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 6. Case Studies */}
      <Casestudies />

      {/* 7. Dashboard Preview */}
      <section id="dashboard" className="bg-muted py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-[800] tracking-tight">
              Your command center
            </h2>
            <p className="mt-4 text-muted-foreground max-w-xl mx-auto">
              A dashboard that shows you exactly where you stand — and what to do
              next.
            </p>
          </div>

          {/* Browser chrome mockup */}
          <div className="rounded-2xl border border-border bg-background shadow-xl overflow-hidden max-w-4xl mx-auto">
            {/* Title bar */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-muted/50">
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-red-400" />
                <div className="h-3 w-3 rounded-full bg-yellow-400" />
                <div className="h-3 w-3 rounded-full bg-green-400" />
              </div>
              <div className="flex-1 mx-4">
                <div className="bg-background rounded-md px-3 py-1 text-xs text-muted-foreground text-center border border-border">
                  lecturelink.ca/dashboard
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="p-6 sm:p-8 space-y-6">
              {/* Greeting */}
              <div>
                <h3 className="text-xl font-semibold tracking-tight">
                  Good morning, Alex
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Your midterm is in 3 days. Here&apos;s what to focus on today.
                </p>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-4 gap-3">
                {[
                  { emoji: "\uD83D\uDD25", value: "12", label: "Day Streak" },
                  { emoji: "\u26A1", value: "2,450", label: "XP Earned" },
                  { emoji: "\uD83D\uDCDA", value: "18.5h", label: "Study Time" },
                  { emoji: "\uD83E\uDDE0", value: "47", label: "Concepts" },
                ].map((s) => (
                  <div
                    key={s.label}
                    className="rounded-xl bg-muted p-3 text-center"
                  >
                    <p className="text-lg font-semibold">
                      {s.emoji} {s.value}
                    </p>
                    <p className="text-xs text-muted-foreground">{s.label}</p>
                  </div>
                ))}
              </div>

              {/* Two columns */}
              <div className="grid sm:grid-cols-2 gap-6">
                {/* Readiness rings */}
                <Card>
                  <CardContent className="pt-5">
                    <p className="text-sm font-medium mb-4">
                      Assessment Readiness
                    </p>
                    <div className="grid grid-cols-2 gap-4 justify-items-center">
                      <ReadinessRing
                        pct={82}
                        label="Midterm 1"
                        color="hsl(142 71% 45%)"
                      />
                      <ReadinessRing
                        pct={65}
                        label="Quiz 3"
                        color="hsl(48 96% 53%)"
                      />
                      <ReadinessRing
                        pct={71}
                        label="Assignment 4"
                        color="hsl(142 71% 45%)"
                      />
                      <ReadinessRing
                        pct={55}
                        label="Lab Report"
                        color="hsl(0 84% 60%)"
                      />
                    </div>
                  </CardContent>
                </Card>

                {/* Action cards */}
                <div className="space-y-3">
                  {[
                    {
                      urgency: "Critical",
                      color: "bg-red-100 text-red-700",
                      title: "Review Linked Lists",
                      sub: "Midterm in 3 days - lowest readiness",
                    },
                    {
                      urgency: "High",
                      color: "bg-yellow-100 text-yellow-700",
                      title: "Practice Recursion",
                      sub: "Quiz 3 next week - 2 weak concepts",
                    },
                    {
                      urgency: "Medium",
                      color: "bg-blue-100 text-blue-700",
                      title: "Finish Lab 4 Notes",
                      sub: "Report due in 10 days",
                    },
                  ].map((a) => (
                    <Card key={a.title}>
                      <CardContent className="py-3 px-4 flex items-center gap-3">
                        <Badge
                          className={`${a.color} text-xs font-medium border-0 shrink-0`}
                        >
                          {a.urgency}
                        </Badge>
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">
                            {a.title}
                          </p>
                          <p className="text-xs text-muted-foreground truncate">
                            {a.sub}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 8. Stats */}
      <section className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-[800] tracking-tight">
              Built at scale
            </h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { value: "22+", label: "API Endpoints" },
              { value: "1,298", label: "Unit Tests" },
              { value: "13", label: "AI Agents" },
              { value: "173+", label: "Components" },
            ].map((s) => (
              <div key={s.label}>
                <p className="text-4xl font-[800] tracking-tight text-primary">
                  {s.value}
                </p>
                <p className="text-sm text-muted-foreground mt-1 font-medium">
                  {s.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 9. Tech Stack Preview */}
      <section className="bg-muted py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-[800] tracking-tight">
              Built with tools you can trust
            </h2>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {TECH_STACK.map((t) => (
              <Card
                key={t.name}
                className="hover:shadow-lg transition-shadow border border-border rounded-2xl"
              >
                <CardContent className="pt-5 pb-4 text-center space-y-2">
                  <t.icon className="h-6 w-6 text-primary mx-auto" />
                  <p className="font-semibold text-sm">{t.name}</p>
                  <p className="text-xs text-muted-foreground">{t.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="text-center mt-8">
            <Link
              href="/stack"
              className="text-sm font-medium text-primary hover:underline"
            >
              See the full architecture &rarr;
            </Link>
          </div>
        </div>
      </section>

      {/* 10. Final CTA */}
      <section className="py-24 px-6">
        <div className="max-w-2xl mx-auto text-center space-y-6">
          <h2 className="text-4xl font-[800] tracking-tight">
            See it in action
          </h2>
          <p className="text-muted-foreground">
            Upload your first syllabus and see LectureLink build your study plan
            in minutes.
          </p>
          <Button
            asChild
            size="lg"
            className="bg-primary text-primary-foreground rounded-lg px-8 text-base font-semibold"
          >
            <Link href="/login">Try It Free &rarr;</Link>
          </Button>
        </div>
      </section>

      {/* 11. Footer */}
      <Footer />
    </div>
  );
}
