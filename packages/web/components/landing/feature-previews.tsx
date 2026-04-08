"use client";

/**
 * Static UI mockups for the landing page feature accordion.
 * These are illustrative — not functional. Inline styles are intentional
 * since these are decorative previews with very specific layouts.
 */

const BLUE = "#2563EB";
const BLUE_LIGHT = "#EFF6FF";
const SLATE: Record<number, string> = {
  50: "#F8FAFC", 100: "#F1F5F9", 200: "#E2E8F0", 300: "#CBD5E1",
  400: "#94A3B8", 500: "#64748B", 600: "#475569", 700: "#334155",
  800: "#1E293B", 900: "#0F172A",
};

const font = "var(--font-dm-sans), 'DM Sans', system-ui, sans-serif";

/* ─── 1. AI Tutor ──────────────────────────────────────────────── */

export function TutorPreview() {
  return (
    <div style={{ fontFamily: font, background: "#fff", borderRadius: 16, border: `1px solid ${SLATE[200]}`, padding: 20, height: 380, display: "flex", flexDirection: "column", gap: 12, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ background: BLUE_LIGHT, color: BLUE, fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 100 }}>Diagnostic Mode</span>
          <span style={{ color: SLATE[400], fontSize: 11 }}>&middot;</span>
          <span style={{ color: SLATE[500], fontSize: 12, fontWeight: 500 }}>Binary Search Trees</span>
        </div>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10, justifyContent: "center" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
          <div style={{ width: 28, height: 28, borderRadius: "50%", background: BLUE, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 12, fontWeight: 700, flexShrink: 0 }}>T</div>
          <div style={{ background: SLATE[50], border: `1px solid ${SLATE[200]}`, borderRadius: "16px 16px 16px 4px", padding: "10px 14px", maxWidth: "80%", fontSize: 13, color: SLATE[700], lineHeight: 1.5 }}>
            Can you explain how a binary search tree maintains its ordering property?
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexDirection: "row-reverse" }}>
          <div style={{ width: 28, height: 28, borderRadius: "50%", background: SLATE[200], display: "flex", alignItems: "center", justifyContent: "center", color: SLATE[600], fontSize: 12, fontWeight: 700, flexShrink: 0 }}>A</div>
          <div style={{ background: BLUE, borderRadius: "16px 16px 4px 16px", padding: "10px 14px", maxWidth: "80%", fontSize: 13, color: "#fff", lineHeight: 1.5 }}>
            The left child is always smaller and the right child is always larger than the parent?
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
          <div style={{ width: 28, height: 28, borderRadius: "50%", background: BLUE, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 12, fontWeight: 700, flexShrink: 0 }}>T</div>
          <div style={{ background: SLATE[50], border: `1px solid ${SLATE[200]}`, borderRadius: "16px 16px 16px 4px", padding: "10px 14px", maxWidth: "80%", fontSize: 13, color: SLATE[700], lineHeight: 1.5 }}>
            Good start! Now — what happens when you insert a value <em>equal</em> to the current node?
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <div style={{ flex: 1, background: SLATE[50], border: `1px solid ${SLATE[200]}`, borderRadius: 12, padding: "10px 14px", fontSize: 13, color: SLATE[400] }}>
          Type your answer...
        </div>
        <div style={{ width: 36, height: 36, borderRadius: 10, background: BLUE, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
        </div>
      </div>
    </div>
  );
}

/* ─── 2. Exam Readiness ────────────────────────────────────────── */

function ReadinessRing({ score, label, color, size = 72 }: { score: number; label: string; color: string; size?: number }) {
  const sw = 5, r = (size - sw) / 2, c = 2 * Math.PI * r;
  const off = c - (score / 100) * c;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`${color}20`} strokeWidth={sw} />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={sw} strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round" />
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15, fontWeight: 700, color: SLATE[800], fontFamily: font }}>{score}%</div>
      </div>
      <span style={{ fontSize: 11, fontWeight: 600, color: SLATE[500], textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</span>
    </div>
  );
}

export function ReadinessPreview() {
  return (
    <div style={{ fontFamily: font, background: "#fff", borderRadius: 16, border: `1px solid ${SLATE[200]}`, padding: 24, height: 380, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div>
          <h3 style={{ fontSize: 17, fontWeight: 700, color: SLATE[900], margin: 0 }}>Midterm Exam</h3>
          <p style={{ fontSize: 12, color: SLATE[500], margin: "2px 0 0" }}>Data Structures &amp; Algorithms</p>
        </div>
        <span style={{ background: "#FEF2F2", color: "#DC2626", fontSize: 12, fontWeight: 600, padding: "4px 12px", borderRadius: 100 }}>3 days away</span>
      </div>
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "space-around", padding: "12px 0" }}>
        <ReadinessRing score={82} label="Coverage" color={BLUE} />
        <ReadinessRing score={65} label="Practice" color="#F59E0B" />
        <ReadinessRing score={71} label="Freshness" color="#16A34A" />
        <ReadinessRing score={55} label="Effort" color="#8B5CF6" />
      </div>
      <div style={{ marginTop: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: SLATE[600] }}>Overall Readiness</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: SLATE[800] }}>68%</span>
        </div>
        <div style={{ height: 8, borderRadius: 100, background: SLATE[100], overflow: "hidden" }}>
          <div style={{ height: "100%", width: "68%", borderRadius: 100, background: `linear-gradient(90deg, ${BLUE}, #3B82F6)` }} />
        </div>
      </div>
      <div style={{ marginTop: 14, display: "flex", gap: 6, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, color: SLATE[500], fontWeight: 500 }}>Weak areas:</span>
        {["Linked Lists", "Recursion", "Graph Traversal"].map(c => (
          <span key={c} style={{ fontSize: 11, background: SLATE[100], color: SLATE[600], padding: "2px 8px", borderRadius: 6, fontWeight: 500 }}>{c}</span>
        ))}
      </div>
    </div>
  );
}

/* ─── 3. Smart Quizzes ─────────────────────────────────────────── */

export function QuizPreview() {
  const options = [
    { label: "A", text: "In-order", selected: false },
    { label: "B", text: "Pre-order", selected: true },
    { label: "C", text: "Post-order", selected: false },
    { label: "D", text: "Level-order", selected: false },
  ];
  return (
    <div style={{ fontFamily: font, background: "#fff", borderRadius: 16, border: `1px solid ${SLATE[200]}`, padding: 20, height: 380, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: SLATE[500] }}>Question 3 of 10</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: BLUE, background: BLUE_LIGHT, padding: "3px 10px", borderRadius: 100 }}>Adaptive &middot; Medium</span>
      </div>
      <div style={{ height: 4, borderRadius: 100, background: SLATE[100], marginBottom: 14, overflow: "hidden" }}>
        <div style={{ height: "100%", width: "30%", borderRadius: 100, background: BLUE }} />
      </div>
      <span style={{ fontSize: 11, color: SLATE[400], fontWeight: 500, marginBottom: 6 }}>Binary Search Trees</span>
      <p style={{ fontSize: 14, fontWeight: 600, color: SLATE[800], lineHeight: 1.5, margin: "0 0 14px" }}>
        Which traversal algorithm visits the root node before its subtrees?
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {options.map(o => (
          <div key={o.label} style={{
            display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
            borderRadius: 10, border: `1.5px solid ${o.selected ? BLUE : SLATE[200]}`,
            background: o.selected ? BLUE_LIGHT : "#fff",
          }}>
            <div style={{
              width: 20, height: 20, borderRadius: "50%", border: `2px solid ${o.selected ? BLUE : SLATE[300]}`,
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              background: o.selected ? BLUE : "transparent",
            }}>
              {o.selected && <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#fff" }} />}
            </div>
            <span style={{ fontSize: 13, fontWeight: o.selected ? 600 : 400, color: o.selected ? BLUE : SLATE[700] }}>{o.text}</span>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
        <div style={{ background: BLUE, color: "#fff", fontSize: 13, fontWeight: 600, padding: "8px 20px", borderRadius: 10 }}>
          Check Answer
        </div>
      </div>
    </div>
  );
}

/* ─── 4. Daily Study Sessions ──────────────────────────────────── */

export function SessionPreview() {
  const concepts = [
    { name: "Binary Search Trees", status: "weak", color: "#EF4444", bg: "#FEF2F2" },
    { name: "Graph Traversal", status: "developing", color: "#F59E0B", bg: "#FFFBEB" },
    { name: "Sorting Algorithms", status: "strong", color: "#16A34A", bg: "#F0FDF4" },
  ];
  return (
    <div style={{ fontFamily: font, background: "#fff", borderRadius: 16, border: `1px solid ${SLATE[200]}`, padding: 24, height: 380, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h3 style={{ fontSize: 17, fontWeight: 700, color: SLATE[900], margin: 0 }}>Today&apos;s Session</h3>
          <p style={{ fontSize: 12, color: SLATE[500], margin: "2px 0 0" }}>CS 301 &middot; 3 concepts to review</p>
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: SLATE[600], background: SLATE[100], padding: "4px 12px", borderRadius: 100 }}>~15 min</span>
      </div>
      <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
        {["Flash Review", "Concept Brief", "Power Quiz"].map((phase, i) => (
          <div key={phase} style={{
            flex: 1, textAlign: "center" as const, fontSize: 10, fontWeight: 600, padding: "6px 0", borderRadius: 8,
            background: i === 0 ? BLUE : SLATE[50], color: i === 0 ? "#fff" : SLATE[400],
            border: i === 0 ? "none" : `1px solid ${SLATE[200]}`,
          }}>{phase}</div>
        ))}
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
        {concepts.map(c => (
          <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", borderRadius: 12, border: `1px solid ${SLATE[200]}`, background: SLATE[50] }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: c.color, flexShrink: 0 }} />
            <span style={{ flex: 1, fontSize: 13, fontWeight: 500, color: SLATE[700] }}>{c.name}</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: c.color, background: c.bg, padding: "2px 8px", borderRadius: 6, textTransform: "capitalize" as const }}>{c.status}</span>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 16, padding: "12px 16px", borderRadius: 12, background: BLUE_LIGHT }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: BLUE }}>+45 XP</span>
          <span style={{ fontSize: 10, color: SLATE[500] }}>earned this session</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#F59E0B" }}>12 days</span>
          <span style={{ fontSize: 10, color: SLATE[500] }}>streak</span>
        </div>
      </div>
    </div>
  );
}

/* ─── 5. Ask Your Lectures ─────────────────────────────────────── */

export function SearchPreview() {
  return (
    <div style={{ fontFamily: font, background: "#fff", borderRadius: 16, border: `1px solid ${SLATE[200]}`, padding: 24, height: 380, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 12, border: `1.5px solid ${BLUE}`, background: BLUE_LIGHT, marginBottom: 16 }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={BLUE} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
        <span style={{ fontSize: 14, color: SLATE[800], fontWeight: 500 }}>What is dynamic programming?</span>
      </div>
      <span style={{ fontSize: 12, color: SLATE[400], fontWeight: 500, marginBottom: 12 }}>2 results across your lectures</span>
      <div style={{ padding: "14px 16px", borderRadius: 12, border: `1px solid ${SLATE[200]}`, background: "#fff", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: BLUE }} />
          <span style={{ fontSize: 14, fontWeight: 600, color: SLATE[800] }}>Lecture 7 &mdash; Algorithms</span>
        </div>
        <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: SLATE[400], fontWeight: 500 }}>Slide 14</span>
          <span style={{ fontSize: 11, color: SLATE[400], fontWeight: 500 }}>34:20</span>
        </div>
        <p style={{ fontSize: 13, color: SLATE[600], lineHeight: 1.6, margin: 0 }}>
          Dynamic programming breaks complex problems into overlapping subproblems, storing results to avoid redundant computation. Unlike divide-and-conquer, DP leverages <span style={{ background: "#FEF9C3", padding: "0 2px", borderRadius: 2 }}>optimal substructure</span> and <span style={{ background: "#FEF9C3", padding: "0 2px", borderRadius: 2 }}>overlapping subproblems</span>...
        </p>
      </div>
      <div style={{ padding: "14px 16px", borderRadius: 12, border: `1px solid ${SLATE[200]}`, background: SLATE[50], opacity: 0.7 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: SLATE[400] }} />
          <span style={{ fontSize: 14, fontWeight: 600, color: SLATE[700] }}>Lecture 12 &mdash; Advanced Topics</span>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <span style={{ fontSize: 11, color: SLATE[400] }}>Slide 3</span>
          <span style={{ fontSize: 11, color: SLATE[400] }}>8:45</span>
        </div>
      </div>
    </div>
  );
}

/* ─── 6. Syllabus-Aware ────────────────────────────────────────── */

export function SyllabusPreview() {
  const rows = [
    { name: "Midterm Exam", date: "Oct 15", weight: "30%", readiness: 68, color: "#F59E0B" },
    { name: "Quiz 3", date: "Oct 8", weight: "5%", readiness: 91, color: "#16A34A" },
    { name: "Assignment 4", date: "Oct 20", weight: "10%", readiness: 45, color: "#EF4444" },
    { name: "Final Exam", date: "Dec 12", weight: "40%", readiness: null as number | null, color: SLATE[400] },
  ];
  return (
    <div style={{ fontFamily: font, background: "#fff", borderRadius: 16, border: `1px solid ${SLATE[200]}`, padding: 24, height: 380, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <h3 style={{ fontSize: 17, fontWeight: 700, color: SLATE[900], margin: 0 }}>CS 301 &mdash; Schedule</h3>
        <span style={{ fontSize: 10, fontWeight: 600, color: BLUE, background: BLUE_LIGHT, padding: "3px 10px", borderRadius: 100 }}>Auto-extracted</span>
      </div>
      <p style={{ fontSize: 12, color: SLATE[500], margin: "0 0 16px" }}>Extracted from syllabus.pdf</p>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1.2fr", gap: 8, padding: "8px 12px", marginBottom: 4 }}>
        {["Assessment", "Date", "Weight", "Readiness"].map(h => (
          <span key={h} style={{ fontSize: 11, fontWeight: 600, color: SLATE[400], textTransform: "uppercase" as const, letterSpacing: "0.05em" }}>{h}</span>
        ))}
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
        {rows.map((r, i) => (
          <div key={r.name} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1.2fr", gap: 8, padding: "10px 12px", borderRadius: 10, background: i % 2 === 0 ? SLATE[50] : "#fff", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: SLATE[800] }}>{r.name}</span>
            <span style={{ fontSize: 13, color: SLATE[600] }}>{r.date}</span>
            <span style={{ fontSize: 13, color: SLATE[600], fontWeight: 500 }}>{r.weight}</span>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {r.readiness !== null ? (
                <>
                  <div style={{ flex: 1, height: 6, borderRadius: 100, background: SLATE[100], overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${r.readiness}%`, borderRadius: 100, background: r.color }} />
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 600, color: r.color, minWidth: 28, textAlign: "right" as const }}>{r.readiness}%</span>
                </>
              ) : (
                <span style={{ fontSize: 11, color: SLATE[400] }}>&mdash;</span>
              )}
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, padding: "10px 14px", borderRadius: 10, background: BLUE_LIGHT }}>
        <span style={{ fontSize: 12, color: BLUE, fontWeight: 500 }}>Concepts linked to assessments automatically</span>
      </div>
    </div>
  );
}

/* ─── Preview map (keyed by feature id) ────────────────────────── */

export const FEATURE_PREVIEWS: Record<number, React.ReactNode> = {
  1: <TutorPreview />,
  2: <ReadinessPreview />,
  3: <QuizPreview />,
  4: <SessionPreview />,
  5: <SearchPreview />,
  6: <SyllabusPreview />,
};
