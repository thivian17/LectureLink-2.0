import Link from "next/link";
import Image from "next/image";
import {
  Upload,
  Brain,
  Target,
  Sparkles,
  BookOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Navbar } from "@/components/landing/navbar";
import { Footer } from "@/components/landing/footer";
import { SecondaryFeatures } from "@/components/landing/secondary-features";
import { Feature197 } from "@/components/accordion-feature-section";

// ─── Feature data for accordion ────────────────────────────────────────
const FEATURES = [
  {
    id: 1,
    title: "AI Tutor",
    description:
      "One-on-one study sessions that diagnose your knowledge gaps, teach concepts step by step, and test your understanding \u2014 all pulled from your actual lecture content.",
  },
  {
    id: 2,
    title: "Exam Readiness",
    description:
      "Four independent signals \u2014 Coverage, Practice, Freshness, and Effort \u2014 give you an honest picture of where you stand before each assessment. Updates in real-time as you study.",
  },
  {
    id: 3,
    title: "Smart Quizzes",
    description:
      "Every question is generated from your lectures \u2014 not a generic question bank. The system tracks what you know at the concept level and adjusts difficulty automatically.",
  },
  {
    id: 4,
    title: "Daily Study Sessions",
    description:
      "Fifteen-minute guided sessions that surface the concepts most at risk of fading. Flash reviews, focused teaching, and a quick quiz \u2014 then you see exactly what moved.",
  },
  {
    id: 5,
    title: "Ask Your Lectures",
    description:
      "Type a question and get an answer sourced directly from your course material \u2014 with the exact lecture, timestamp, and slide number cited.",
  },
  {
    id: 6,
    title: "Syllabus-Aware",
    description:
      "Upload a syllabus PDF and LectureLink extracts your schedule, assessments, and grade weights automatically. Every recommendation aligns to what\u2019s actually being graded.",
  },
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
    desc: "AI tutor, adaptive quizzes, and daily sessions \u2014 personalized to your weak spots and deadlines.",
  },
  {
    icon: Target,
    title: "Track Readiness",
    desc: "Watch your readiness scores update as you study. Always know where you stand.",
  },
];

// ═══════════════════════════════════════════════════════════════════════
// Landing page
// ═══════════════════════════════════════════════════════════════════════
export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {/* Hero */}
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
              <Link href="/login">Try the Demo &rarr;</Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="rounded-lg">
              <a href="#how">See How It Works</a>
            </Button>
          </div>

          <p className="text-sm text-muted-foreground">
            No signup required &mdash; explore a pre-loaded CS course instantly
          </p>
        </div>

        {/* Hero screenshot */}
        <div className="max-w-4xl mx-auto mt-16 px-6 relative z-10">
          <div className="rounded-2xl overflow-hidden border border-border shadow-2xl">
            <div className="flex items-center gap-2 px-4 py-3 bg-muted border-b border-border">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-yellow-400" />
                <div className="w-3 h-3 rounded-full bg-green-400" />
              </div>
              <div className="flex-1 flex justify-center">
                <div className="px-4 py-1 rounded-md bg-background text-xs text-muted-foreground border border-border">
                  lecturelink.ca/dashboard
                </div>
              </div>
            </div>
            <Image
              src="/images/screenshots/dashboard.png"
              alt="LectureLink Dashboard"
              width={1200}
              height={800}
              className="w-full"
              priority
            />
          </div>
        </div>

        {/* Decorative gradient blobs */}
        <div className="absolute -top-40 -right-40 h-96 w-96 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-40 -left-40 h-96 w-96 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
      </section>

      {/* Social proof */}
      <section className="py-8 px-6 border-y border-border bg-muted/30">
        <p className="text-center text-sm text-muted-foreground">
          Built for students, by a student &mdash; processing lecture audio, slides, and syllabi into personalized study plans
        </p>
      </section>

      {/* Features — Tier 1: Accordion */}
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
          <SecondaryFeatures />
        </div>
      </section>

      {/* How It Works */}
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

      {/* Final CTA */}
      <section className="py-24 px-6 bg-muted">
        <div className="max-w-2xl mx-auto text-center space-y-6">
          <h2 className="text-4xl font-[800] tracking-tight">
            See it in action
          </h2>
          <p className="text-muted-foreground">
            Explore a pre-loaded CS course with real lectures, quizzes, and
            study progress &mdash; no account needed.
          </p>
          <div className="space-y-3">
            <Button
              asChild
              size="lg"
              className="bg-primary text-primary-foreground rounded-lg px-8 text-base font-semibold"
            >
              <Link href="/login">Try the Demo &rarr;</Link>
            </Button>
            <p className="text-xs text-muted-foreground">
              Or{" "}
              <Link href="/stack" className="text-primary hover:underline">
                see the full technical architecture
              </Link>
            </p>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
