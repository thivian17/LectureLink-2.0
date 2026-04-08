"use client";

import { useEffect, useRef, useState } from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { FEATURE_PREVIEWS } from "@/components/landing/feature-previews";
import { useIntersectionObserver } from "@/hooks/use-intersection-observer";

interface FeatureItem {
  id: number;
  title: string;
  description: string;
}

interface Feature197Props {
  features: FeatureItem[];
}

const Feature197 = ({ features }: Feature197Props) => {
  const [activeTabId, setActiveTabId] = useState<number>(1);
  const { ref, isVisible } = useIntersectionObserver({ threshold: 0.05, triggerOnce: true });
  const sectionRef = useRef<HTMLDivElement>(null);
  const userClicked = useRef(false);
  const clickTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Scroll-driven accordion cycling
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    function onScroll() {
      // Skip scroll-driven updates briefly after user clicks
      if (userClicked.current) return;

      const rect = el!.getBoundingClientRect();
      const viewportH = window.innerHeight;

      // Progress: 0 when section top hits viewport bottom, 1 when section bottom leaves viewport top
      // Using the full scroll range of the section through the viewport
      const scrollRange = rect.height + viewportH;
      const scrolled = viewportH - rect.top;
      const progress = Math.max(0, Math.min(1, scrolled / scrollRange));

      // Map 20%-80% of scroll range to features (generous entry/exit edges)
      const mapped = Math.max(0, Math.min(1, (progress - 0.2) / 0.6));

      // Non-linear mapping: give first and last items more scroll room
      // Breakpoints give ~20% scroll each to first/last, ~15% to middle items
      const breakpoints = [0.20, 0.35, 0.50, 0.65, 0.80, 1.0];
      let idx = features.length - 1;
      for (let b = 0; b < breakpoints.length; b++) {
        if (mapped < breakpoints[b]) {
          idx = b;
          break;
        }
      }
      const newId = features[idx]?.id ?? 1;
      setActiveTabId(newId);
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [features]);

  function handleClick(id: number) {
    setActiveTabId(id);
    // Pause scroll-driven updates for 3s after a manual click
    userClicked.current = true;
    if (clickTimer.current) clearTimeout(clickTimer.current);
    clickTimer.current = setTimeout(() => {
      userClicked.current = false;
    }, 3000);
  }

  return (
    <div ref={sectionRef} style={{ minHeight: "150vh" }}>
      <div
        ref={ref as React.RefObject<HTMLDivElement>}
        className="sticky top-24 flex w-full items-start justify-between gap-12"
        style={{
          opacity: isVisible ? 1 : 0,
          transform: isVisible ? "translateY(0)" : "translateY(24px)",
          transition: "opacity 600ms ease, transform 600ms ease",
        }}
      >
        <div className="w-full md:w-1/2">
          <Accordion
            type="single"
            className="w-full"
            value={`item-${activeTabId}`}
            onValueChange={(val) => {
              if (val) {
                const id = Number(val.replace("item-", ""));
                handleClick(id);
              }
            }}
          >
            {features.map((tab, i) => (
              <AccordionItem key={tab.id} value={`item-${tab.id}`}>
                <AccordionTrigger
                  onClick={() => handleClick(tab.id)}
                  className="cursor-pointer py-5 !no-underline transition"
                  style={{
                    opacity: isVisible ? 1 : 0,
                    transform: isVisible ? "translateX(0)" : "translateX(-16px)",
                    transition: `opacity 450ms ease ${200 + i * 80}ms, transform 450ms ease ${200 + i * 80}ms`,
                  }}
                >
                  <h6
                    className={`text-xl font-semibold ${tab.id === activeTabId ? "text-foreground" : "text-muted-foreground"}`}
                  >
                    {tab.title}
                  </h6>
                </AccordionTrigger>
                <AccordionContent>
                  <p className="mt-3 text-muted-foreground">
                    {tab.description}
                  </p>
                  {/* Mobile: show preview inline */}
                  <div className="mt-4 md:hidden">
                    {FEATURE_PREVIEWS[tab.id]}
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
        {/* Desktop: show preview in right panel */}
        <div
          className="relative m-auto hidden w-1/2 md:block"
          style={{
            opacity: isVisible ? 1 : 0,
            transform: isVisible ? "translateY(0) scale(1)" : "translateY(16px) scale(0.97)",
            transition: "opacity 600ms ease 300ms, transform 600ms ease 300ms",
          }}
        >
          {FEATURE_PREVIEWS[activeTabId]}
        </div>
      </div>
    </div>
  );
};

export { Feature197 };
