"use client";

interface XPPopupProps {
  xp: number;
  trigger: number;
}

export function XPPopup({ xp, trigger }: XPPopupProps) {
  if (trigger === 0) return null;

  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center z-10">
      <span key={trigger} className="animate-xp-float text-lg font-bold text-emerald-500">
        +{xp} XP
      </span>
      <style jsx>{`
        @keyframes xpFloat {
          0% { opacity: 1; transform: translateY(0) scale(1); }
          70% { opacity: 1; transform: translateY(-30px) scale(1.1); }
          100% { opacity: 0; transform: translateY(-50px) scale(0.9); }
        }
        .animate-xp-float {
          animation: xpFloat 1.2s ease-out forwards;
        }
      `}</style>
    </div>
  );
}
