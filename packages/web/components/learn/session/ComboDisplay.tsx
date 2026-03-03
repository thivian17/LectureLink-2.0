"use client";

import { cn } from "@/lib/utils";

interface ComboDisplayProps {
  combo: number;
}

export function ComboDisplay({ combo }: ComboDisplayProps) {
  if (combo < 3) return null;

  const flames = Math.min(combo - 2, 3);

  return (
    <div
      className={cn(
        "flex items-center gap-1 text-sm font-bold text-orange-500 animate-combo-pop",
      )}
    >
      <span>{"🔥".repeat(flames)}</span>
      <span>x{combo}</span>
      <style jsx>{`
        @keyframes comboPop {
          0% { transform: scale(1.2); }
          100% { transform: scale(1); }
        }
        .animate-combo-pop {
          animation: comboPop 0.2s ease-out;
        }
      `}</style>
    </div>
  );
}
