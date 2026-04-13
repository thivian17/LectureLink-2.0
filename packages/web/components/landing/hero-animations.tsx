"use client";

import { useEffect, useRef, useState } from "react";

// ─── Pill data ────────────────────────────────────────────────────────

const CONCEPTS = [
  "Supply & Demand", "Cognitive Bias", "Cellular Respiration",
  "The French Revolution", "Opportunity Cost", "Quantum Mechanics",
  "Mitosis", "Game Theory", "Natural Selection", "Net Present Value",
  "Standard Deviation", "Ohm's Law", "The Enlightenment",
  "Market Equilibrium", "DNA Replication", "Marginal Utility",
  "Newton's Laws", "Photosynthesis", "Keynesian Theory", "Ethical Dilemmas",
];

const PILL_COLORS = [
  { bg: "#E6F1FB", text: "#0C447C", border: "#B5D4F4" },
  { bg: "#E1F5EE", text: "#085041", border: "#9FE1CB" },
  { bg: "#EEEDFE", text: "#3C3489", border: "#CECBF6" },
  { bg: "#FAEEDA", text: "#633806", border: "#FAC775" },
  { bg: "#FBEAF0", text: "#72243E", border: "#F4C0D1" },
  { bg: "#EAF3DE", text: "#27500A", border: "#C0DD97" },
  { bg: "#FAECE7", text: "#4A1B0C", border: "#F5C4B3" },
];

const PILL_LANES = [3, 9, 16, 22, 29, 36, 44, 51, 58, 65, 72, 79, 86, 92];

// ─── FloatingConcepts ─────────────────────────────────────────────────

interface Pill {
  id: number;
  concept: string;
  color: (typeof PILL_COLORS)[number];
  left: number;
  duration: number;
}

export function FloatingConcepts() {
  const [pills, setPills] = useState<Pill[]>([]);
  const counterRef = useRef(0);

  useEffect(() => {
    function spawnPill() {
      const id = counterRef.current++;
      const pill: Pill = {
        id,
        concept: CONCEPTS[Math.floor(Math.random() * CONCEPTS.length)],
        color: PILL_COLORS[Math.floor(Math.random() * PILL_COLORS.length)],
        left: PILL_LANES[Math.floor(Math.random() * PILL_LANES.length)],
        duration: 6 + Math.random() * 5,
      };
      setPills((prev) => [...prev, pill]);
      setTimeout(() => {
        setPills((prev) => prev.filter((p) => p.id !== id));
      }, pill.duration * 1000 + 100);
    }

    for (let i = 0; i < 5; i++) {
      setTimeout(spawnPill, i * 200);
    }
    const interval = setInterval(spawnPill, 750);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 overflow-hidden pointer-events-none"
      style={{ zIndex: 0 }}
    >
      {pills.map((pill) => (
        <span
          key={pill.id}
          className="absolute rounded-full px-2.5 py-0.5 text-[10px] whitespace-nowrap"
          style={{
            left: `${pill.left}%`,
            bottom: "-28px",
            backgroundColor: pill.color.bg,
            color: pill.color.text,
            border: `0.5px solid ${pill.color.border}`,
            animation: `ll-float-up ${pill.duration}s linear forwards`,
          }}
        >
          {pill.concept}
        </span>
      ))}
    </div>
  );
}

// ─── TypewriterHeadline ───────────────────────────────────────────────

export function TypewriterHeadline() {
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [line3, setLine3] = useState("");
  const [showCursor2, setShowCursor2] = useState(false);
  const [showCursor3, setShowCursor3] = useState(false);

  useEffect(() => {
    const L1 = "Your lectures, analyzed.";
    const L2 = "Your gaps, exposed.";
    const L3 = "Your exam, handled.";
    let i = 0;
    let j = 0;
    let k = 0;
    let t: ReturnType<typeof setTimeout>;

    function typeLine1() {
      if (i < L1.length) {
        i++;
        setLine1(L1.slice(0, i));
        t = setTimeout(typeLine1, 52);
      } else {
        t = setTimeout(() => {
          setShowCursor2(true);
          typeLine2();
        }, 380);
      }
    }

    function typeLine2() {
      if (j < L2.length) {
        j++;
        setLine2(L2.slice(0, j));
        t = setTimeout(typeLine2, 52);
      } else {
        t = setTimeout(() => {
          setShowCursor2(false);
          setShowCursor3(true);
          typeLine3();
        }, 500);
      }
    }

    function typeLine3() {
      if (k < L3.length) {
        k++;
        setLine3(L3.slice(0, k));
        t = setTimeout(typeLine3, 80);
      }
    }

    t = setTimeout(typeLine1, 400);
    return () => clearTimeout(t);
  }, []);

  const L3_COLOR_START = 11; // index where "handled." begins in "Your exam, handled."

  return (
    <h1 className="text-5xl sm:text-6xl lg:text-7xl font-[800] tracking-tight leading-[1.08]">
      <span>
        {line1}
        {line1.length > 0 && line2.length === 0 && (
          <span className="inline-block w-[2px] h-[0.85em] bg-primary align-middle ml-0.5 animate-[blink_0.8s_step-end_infinite]" />
        )}
      </span>
      <br />
      <span>
        {showCursor2 && line2.length === 0 && (
          <span className="inline-block w-[2px] h-[0.85em] bg-primary align-middle mr-0.5 animate-[blink_0.8s_step-end_infinite]" />
        )}
        {line2}
        {line2.length > 0 && !showCursor3 && (
          <span className="inline-block w-[2px] h-[0.85em] bg-primary align-middle ml-0.5 animate-[blink_0.8s_step-end_infinite]" />
        )}
      </span>
      <br />
      <span>
        {showCursor3 && line3.length === 0 && (
          <span className="inline-block w-[2px] h-[0.85em] bg-primary align-middle mr-0.5 animate-[blink_0.8s_step-end_infinite]" />
        )}
        {line3.slice(0, Math.min(line3.length, L3_COLOR_START))}
        {line3.length > L3_COLOR_START && (
          <span className="text-primary font-[800]">
            {line3.slice(L3_COLOR_START)}
          </span>
        )}
        {line3.length > 0 && (
          <span className="inline-block w-[2px] h-[0.85em] bg-primary align-middle ml-0.5 animate-[blink_0.8s_step-end_infinite]" />
        )}
      </span>
    </h1>
  );
}
