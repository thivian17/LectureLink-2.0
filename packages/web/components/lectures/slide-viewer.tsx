"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { SlideInfo } from "@/types/database";

interface SlideViewerProps {
  slides: SlideInfo[];
  activeSlideNumber: number | null;
  onSlideChange?: (slideNumber: number) => void;
  className?: string;
}

export function SlideViewer({
  slides,
  activeSlideNumber,
  onSlideChange,
  className,
}: SlideViewerProps) {
  const [currentSlide, setCurrentSlide] = useState(1);
  const [imageLoaded, setImageLoaded] = useState(false);

  // Sync with transcript-driven slide changes (render-time adjustment)
  const [prevActiveSlide, setPrevActiveSlide] = useState(activeSlideNumber);
  if (activeSlideNumber !== prevActiveSlide) {
    setPrevActiveSlide(activeSlideNumber);
    if (activeSlideNumber !== null && activeSlideNumber !== currentSlide) {
      setCurrentSlide(activeSlideNumber);
      setImageLoaded(false);
    }
  }

  const slide = slides.find((s) => s.slide_number === currentSlide) ?? slides[0];
  const totalSlides = slides.length;

  const goTo = (num: number) => {
    const clamped = Math.max(1, Math.min(num, totalSlides));
    setCurrentSlide(clamped);
    setImageLoaded(false);
    onSlideChange?.(clamped);
  };

  if (slides.length === 0) return null;

  return (
    <div className={cn("flex flex-col min-h-0", className)}>
      {/* Slide image area */}
      <div className="flex-1 flex items-center justify-center bg-muted/30 p-4 min-h-0 relative">
        {!imageLoaded && (
          <div className="absolute inset-4 bg-muted animate-pulse rounded-lg" />
        )}
        {slide && (
          <div className="relative w-full h-full flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={slide.image_url}
              alt={slide.title ?? `Slide ${slide.slide_number}`}
              className="max-w-full max-h-full object-contain rounded-lg shadow-sm"
              onLoad={() => setImageLoaded(true)}
              onError={() => setImageLoaded(true)}
            />
            {/* Slide title overlay */}
            {slide.title && imageLoaded && (
              <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white px-3 py-1.5 rounded-b-lg">
                <p className="text-sm font-medium truncate">{slide.title}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Slide text content (fallback when no image / useful context) */}
      {slide?.text_content && (
        <div className="px-4 py-2 border-t bg-muted/20 max-h-24 overflow-auto">
          <p className="text-xs text-muted-foreground whitespace-pre-line">
            {slide.text_content}
          </p>
        </div>
      )}

      {/* Navigation bar */}
      <div className="flex items-center justify-between border-t px-3 py-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => goTo(currentSlide - 1)}
          disabled={currentSlide <= 1}
          className="h-8 w-8 p-0"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        <span className="text-sm text-muted-foreground">
          Slide {currentSlide} of {totalSlides}
        </span>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => goTo(currentSlide + 1)}
          disabled={currentSlide >= totalSlides}
          className="h-8 w-8 p-0"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
