"use client";

import { useState } from "react";
import { MessageCircle, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { QAChat } from "@/components/chat/qa-chat";
import { cn } from "@/lib/utils";

interface QAChatButtonProps {
  courseId: string;
  lectureId: string;
}

export function QAChatButton({ courseId, lectureId }: QAChatButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <MessageCircle className="mr-2 h-4 w-4" />
        Ask AI
      </Button>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/20"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Slide-over panel */}
      <div
        className={cn(
          "fixed inset-y-0 right-0 z-50 w-full sm:w-[400px] transform transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="h-full bg-background border-l shadow-xl">
          <QAChat
            courseId={courseId}
            lectureIds={[lectureId]}
            position="panel"
            onClose={() => setOpen(false)}
          />
        </div>
      </div>
    </>
  );
}
