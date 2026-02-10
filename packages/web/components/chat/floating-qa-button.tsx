"use client";

import { useState } from "react";
import { MessageCircle, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { QAChat } from "@/components/chat/qa-chat";
import { cn } from "@/lib/utils";

interface FloatingQAButtonProps {
  courseId: string;
}

export function FloatingQAButton({ courseId }: FloatingQAButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Floating panel */}
      {open && (
        <div className="fixed bottom-20 right-6 z-50 w-[380px] h-[500px] shadow-xl rounded-lg border">
          <QAChat
            courseId={courseId}
            position="floating"
            onClose={() => setOpen(false)}
          />
        </div>
      )}

      {/* Floating action button */}
      <Button
        size="icon"
        className={cn(
          "fixed bottom-6 right-6 z-40 h-12 w-12 rounded-full shadow-lg",
          open && "bg-muted text-muted-foreground hover:bg-muted/80",
        )}
        onClick={() => setOpen((prev) => !prev)}
      >
        {open ? (
          <X className="h-5 w-5" />
        ) : (
          <MessageCircle className="h-5 w-5" />
        )}
      </Button>
    </>
  );
}
