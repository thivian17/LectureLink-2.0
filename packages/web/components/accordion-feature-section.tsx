"use client";

import { useState } from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { FEATURE_PREVIEWS } from "@/components/landing/feature-previews";

interface FeatureItem {
  id: number;
  title: string;
  image: string;
  description: string;
}

interface Feature197Props {
  features: FeatureItem[];
}

const Feature197 = ({ features }: Feature197Props) => {
  const [activeTabId, setActiveTabId] = useState<number>(1);

  return (
    <div className="flex w-full items-start justify-between gap-12">
      <div className="w-full md:w-1/2">
        <Accordion type="single" className="w-full" defaultValue="item-1">
          {features.map((tab) => (
            <AccordionItem key={tab.id} value={`item-${tab.id}`}>
              <AccordionTrigger
                onClick={() => setActiveTabId(tab.id)}
                className="cursor-pointer py-5 !no-underline transition"
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
      <div className="relative m-auto hidden w-1/2 md:block">
        {FEATURE_PREVIEWS[activeTabId]}
      </div>
    </div>
  );
};

export { Feature197 };
