import { Navbar } from "@/components/landing/navbar";
import { Footer } from "@/components/landing/footer";
import {
  Monitor,
  Server,
  Database,
  Brain,
  Cloud,
  FlaskConical,
  Lightbulb,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/*  Data                                                                      */
/* -------------------------------------------------------------------------- */

const stackLayers = [
  {
    title: "Frontend",
    icon: Monitor,
    items: [
      {
        name: "Next.js 16 + React 19",
        desc: "App Router, RSC, 33 pages, streaming SSR, TypeScript strict mode.",
      },
      {
        name: "Tailwind CSS 4 + shadcn/ui",
        desc: "Custom design system, oklch color space, semantic tokens, 173+ components.",
      },
      {
        name: "Radix UI",
        desc: "Accessible primitives, WCAG keyboard nav, ARIA labels.",
      },
    ],
  },
  {
    title: "Backend",
    icon: Server,
    items: [
      {
        name: "FastAPI + Python 3.12",
        desc: "22 API modules, Pydantic, fully async.",
      },
      {
        name: "arq (Redis job queue)",
        desc: "Background workers, always-on Cloud Run.",
      },
      {
        name: "Google Gemini 2.5 Flash",
        desc: "Single LLM for transcription, slides, concepts, quizzes, tutoring, RAG.",
      },
    ],
  },
  {
    title: "Data",
    icon: Database,
    items: [
      {
        name: "Supabase (PostgreSQL + pgvector)",
        desc: "Auth, storage, RLS, hybrid search via RRF.",
      },
      {
        name: "Gemini embeddings (2000-dim)",
        desc: "pgvector storage, hybrid_search RPC via UNION.",
      },
      {
        name: "Redis",
        desc: "LLM caching, job queue, session state.",
      },
    ],
  },
  {
    title: "AI / ML",
    icon: Brain,
    items: [
      {
        name: "6-Stage Processing Pipeline",
        desc: "Input router \u2192 Transcription \u2192 Slides \u2192 Alignment \u2192 Concepts (V2, dedup-aware) \u2192 Embedding.",
      },
      {
        name: "Bayesian Knowledge Tracing",
        desc: "Per-concept mastery, confidence-weighted, unified mastery.py.",
      },
      {
        name: "4-Signal Readiness",
        desc: "Coverage 35%, Practice 30%, Freshness 20%, Effort 15%.",
      },
      {
        name: "Concept Registry",
        desc: "Two-pass dedup (title + embedding cosine similarity).",
      },
    ],
  },
  {
    title: "Infrastructure",
    icon: Cloud,
    items: [
      {
        name: "Google Cloud Run",
        desc: "3 services (API 2 CPU / 2 GB, Worker 1 CPU / 1 GB always-on, Web 256 MB).",
      },
      {
        name: "GitHub Actions CI/CD",
        desc: "Workload Identity Federation, prod + staging pipelines.",
      },
      {
        name: "Observability",
        desc: "Sentry, PostHog, Langfuse, bug reporting \u2192 GitHub Issues.",
      },
    ],
  },
];

const decisions = [
  {
    title: "Deterministic-first architecture",
    desc: "LLM calls are constrained and grounded in structured data. If the LLM fails, deterministic layers (schedule-based, keyword overlap, embedding similarity) still work.",
  },
  {
    title: "Unified mastery system",
    desc: "One learning_events table and a shared mastery module replaced fragmented tracking across features. Single source of truth.",
  },
  {
    title: "Parallel execution",
    desc: "Development decomposed into non-conflicting tracks with explicit sync points, yielding ~3\u00d7 throughput over sequential execution.",
  },
  {
    title: "Syllabus locking",
    desc: "Syllabus confirmed by student then locked. Re-upload requires full course deletion. Eliminates complex cascade cleanup.",
  },
];

const testingStats = [
  { value: "1,298", label: "unit tests across 92 files" },
  { value: "E2E", label: "Playwright integration tests" },
  { value: "Critic", label: "Quiz critic agent validates question quality" },
  { value: "Full", label: "Integration tests for lecture processing pipeline" },
];

/* -------------------------------------------------------------------------- */
/*  Page                                                                      */
/* -------------------------------------------------------------------------- */

export default function StackPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar activeLink="/stack" />

      {/* Hero */}
      <section className="pt-32 pb-16 text-center px-6">
        <h1 className="text-4xl md:text-5xl font-[800] tracking-tight">
          How LectureLink is built
        </h1>
        <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
          A full-stack AI study platform &mdash; from audio transcription to
          adaptive mastery tracking. Here&apos;s what&apos;s under the hood.
        </p>
      </section>

      {/* Architecture overview */}
      <section className="max-w-4xl mx-auto px-6 pb-20">
        <div className="rounded-2xl bg-muted p-6 md:p-8">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
            Architecture Overview
          </h2>
          <div className="space-y-2 font-mono text-sm">
            <Row left="lecturelink.ca" right="Cloud Run: Next.js 16 frontend" />
            <Row
              left="api.lecturelink.ca"
              right="Cloud Run: FastAPI backend + arq worker"
            />
            <Row left="Redis" right="Queue + cache" />
            <Row
              left="Supabase"
              right="PostgreSQL + pgvector + Auth + Storage"
            />
            <Row left="Google Gemini API" right="Transcription, concepts, RAG" />
          </div>
        </div>
      </section>

      {/* Stack layers */}
      <section className="max-w-5xl mx-auto px-6 pb-20 space-y-8">
        {stackLayers.map((layer) => (
          <div
            key={layer.title}
            className="rounded-xl border border-border bg-card p-6"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                <layer.icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold">{layer.title}</h3>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {layer.items.map((item) => (
                <div key={item.name} className="space-y-1">
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="text-sm text-muted-foreground">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>

      {/* Testing */}
      <section className="max-w-5xl mx-auto px-6 pb-20">
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
              <FlaskConical className="h-5 w-5 text-primary" />
            </div>
            <h3 className="text-lg font-semibold">Testing</h3>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {testingStats.map((s) => (
              <div key={s.label} className="text-center">
                <p className="text-2xl font-bold text-primary">{s.value}</p>
                <p className="mt-1 text-sm text-muted-foreground">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Key engineering decisions */}
      <section className="max-w-5xl mx-auto px-6 pb-24">
        <div className="flex items-center gap-3 mb-6">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
            <Lightbulb className="h-5 w-5 text-primary" />
          </div>
          <h3 className="text-lg font-semibold">Key Engineering Decisions</h3>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {decisions.map((d) => (
            <div
              key={d.title}
              className="rounded-xl border border-border bg-card p-6"
            >
              <p className="font-semibold">{d.title}</p>
              <p className="mt-2 text-sm text-muted-foreground">{d.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <Footer />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                   */
/* -------------------------------------------------------------------------- */

function Row({ left, right }: { left: string; right: string }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4 py-2 border-b border-border/50 last:border-0">
      <span className="font-semibold text-foreground min-w-[200px]">
        {left}
      </span>
      <span className="text-muted-foreground">{right}</span>
    </div>
  );
}
