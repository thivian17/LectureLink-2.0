"use client";

import { useState } from "react";
import { MessageCircle, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

export function QAChatButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        onClick={() => setOpen(true)}
        className="fixed bottom-20 right-4 z-40 rounded-full h-12 w-12 p-0 shadow-lg"
        title="Ask about this lecture"
      >
        <MessageCircle className="h-5 w-5" />
      </Button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="w-[400px] sm:w-[400px] flex flex-col">
          <SheetHeader>
            <SheetTitle>Ask about this lecture</SheetTitle>
          </SheetHeader>

          {/* Empty chat area — stub for C3 */}
          <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
            <p>Q&A coming soon...</p>
          </div>

          {/* Input area */}
          <div className="flex items-center gap-2 border-t pt-3">
            <Input
              placeholder="Ask a question..."
              className="flex-1"
              disabled
            />
            <Button size="sm" disabled className="h-9 w-9 p-0">
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
