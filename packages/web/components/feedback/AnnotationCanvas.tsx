"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";

interface AnnotationCanvasProps {
  screenshotDataUrl: string;
  onAnnotationComplete: (
    annotatedDataUrl: string,
    bounds: { x: number; y: number; width: number; height: number } | null,
  ) => void;
  onRetake: () => void;
}

export function AnnotationCanvas({
  screenshotDataUrl,
  onAnnotationComplete,
  onRetake,
}: AnnotationCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [drawing, setDrawing] = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(
    null,
  );
  const [bounds, setBounds] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);

  const syncCanvasSize = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
  }, []);

  useEffect(() => {
    syncCanvasSize();
    window.addEventListener("resize", syncCanvasSize);
    return () => window.removeEventListener("resize", syncCanvasSize);
  }, [syncCanvasSize]);

  function getPos(
    e: React.MouseEvent | React.TouchEvent,
  ): { x: number; y: number } {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const clientX =
      "touches" in e ? e.touches[0].clientX : (e as React.MouseEvent).clientX;
    const clientY =
      "touches" in e ? e.touches[0].clientY : (e as React.MouseEvent).clientY;
    return { x: clientX - rect.left, y: clientY - rect.top };
  }

  function drawRect(
    sx: number,
    sy: number,
    ex: number,
    ey: number,
  ) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const x = Math.min(sx, ex);
    const y = Math.min(sy, ey);
    const w = Math.abs(ex - sx);
    const h = Math.abs(ey - sy);
    ctx.fillStyle = "rgba(239, 68, 68, 0.25)";
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = "#EF4444";
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
  }

  function handleStart(e: React.MouseEvent | React.TouchEvent) {
    e.preventDefault();
    const pos = getPos(e);
    setStartPos(pos);
    setDrawing(true);
    setBounds(null);
  }

  function handleMove(e: React.MouseEvent | React.TouchEvent) {
    if (!drawing || !startPos) return;
    e.preventDefault();
    const pos = getPos(e);
    drawRect(startPos.x, startPos.y, pos.x, pos.y);
  }

  function handleEnd(e: React.MouseEvent | React.TouchEvent) {
    if (!drawing || !startPos) return;
    e.preventDefault();
    const pos =
      "changedTouches" in e
        ? {
            x:
              e.changedTouches[0].clientX -
              canvasRef.current!.getBoundingClientRect().left,
            y:
              e.changedTouches[0].clientY -
              canvasRef.current!.getBoundingClientRect().top,
          }
        : getPos(e);
    const x = Math.min(startPos.x, pos.x);
    const y = Math.min(startPos.y, pos.y);
    const w = Math.abs(pos.x - startPos.x);
    const h = Math.abs(pos.y - startPos.y);
    if (w > 5 && h > 5) {
      setBounds({ x, y, width: w, height: h });
    }
    setDrawing(false);
  }

  function handleClear() {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d")!;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    setBounds(null);
    setStartPos(null);
  }

  function handleConfirm() {
    const img = imgRef.current;
    const canvas = canvasRef.current;
    if (!img || !canvas) return;

    const merged = document.createElement("canvas");
    merged.width = img.naturalWidth;
    merged.height = img.naturalHeight;
    const ctx = merged.getContext("2d")!;
    ctx.drawImage(img, 0, 0);
    ctx.drawImage(canvas, 0, 0, merged.width, merged.height);
    onAnnotationComplete(merged.toDataURL("image/png"), bounds);
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Draw to highlight the problem area
      </p>
      <div ref={containerRef} className="relative max-h-64 overflow-hidden">
        <img
          ref={imgRef}
          src={screenshotDataUrl}
          alt="Screenshot"
          className="w-full object-contain"
          onLoad={syncCanvasSize}
          draggable={false}
        />
        <canvas
          ref={canvasRef}
          className="absolute inset-0 cursor-crosshair"
          onMouseDown={handleStart}
          onMouseMove={handleMove}
          onMouseUp={handleEnd}
          onMouseLeave={handleEnd}
          onTouchStart={handleStart}
          onTouchMove={handleMove}
          onTouchEnd={handleEnd}
        />
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={handleClear}>
          Clear
        </Button>
        <Button size="sm" onClick={handleConfirm}>
          Confirm
        </Button>
        <button
          type="button"
          className="ml-auto text-xs text-muted-foreground underline hover:text-foreground"
          onClick={onRetake}
        >
          Retake screenshot
        </button>
      </div>
    </div>
  );
}
