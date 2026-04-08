"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Navbar } from "@/components/landing/navbar";
import { Footer } from "@/components/landing/footer";
import { FloatingConcepts, TypewriterHeadline } from "@/components/landing/hero-animations";
import { Feature197 } from "@/components/accordion-feature-section";
import { PipelineAnimated } from "@/components/landing/pipeline-animated";
import { ReadinessRingAnimated } from "@/components/landing/readiness-ring-animated";

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


// ═══════════════════════════════════════════════════════════════════════
// Landing page
// ═══════════════════════════════════════════════════════════════════════
export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {/* Hero */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        {/* Pills — z-index 0, behind all content */}
        <FloatingConcepts />

        {/* Hero content — z-index 1, in front of pills */}
        <div className="relative z-10 max-w-4xl mx-auto text-center space-y-8">
          <Badge
            variant="secondary"
            className="px-4 py-1.5 text-sm font-medium"
          >
            <Sparkles className="h-3.5 w-3.5 mr-1.5" />
            AI-Powered Study Platform
          </Badge>

          <TypewriterHeadline />

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
              <Link href="/login?demo=true">Try the Demo &rarr;</Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="rounded-lg px-8 text-base font-semibold">
              <Link href="/signup">Sign Up Free</Link>
            </Button>
          </div>

          <p className="text-sm text-muted-foreground">
            No credit card required &mdash; or{" "}
            <a href="#how" className="underline underline-offset-4 hover:text-foreground transition-colors">
              see how it works
            </a>
          </p>
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

      {/* Features — Accordion with interactive mockups */}
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
      </section>

      {/* How It Works */}
      <section id="how" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-[800] tracking-tight">
              From lecture recording to study-ready
            </h2>
          </div>
          <PipelineAnimated />
        </div>
      </section>

      {/* Assessment Readiness */}
      <section className="py-24 px-6">
        <div className="max-w-2xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-[800] tracking-tight">See your readiness in real time</h2>
            <p className="mt-4 text-muted-foreground max-w-xl mx-auto">
              Four independent signals combine into a single score, updated every time you study.
            </p>
          </div>
          <ReadinessRingAnimated />
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
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button
              asChild
              size="lg"
              className="bg-primary text-primary-foreground rounded-lg px-8 text-base font-semibold"
            >
              <Link href="/login?demo=true">Try the Demo &rarr;</Link>
            </Button>
            <Button
              asChild
              variant="outline"
              size="lg"
              className="rounded-lg px-8 text-base font-semibold"
            >
              <Link href="/signup">Sign Up Free</Link>
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            <Link href="/stack" className="text-primary hover:underline">
              See the full technical architecture &rarr;
            </Link>
          </p>
        </div>
      </section>

      <Footer />
    </div>
  );
}
