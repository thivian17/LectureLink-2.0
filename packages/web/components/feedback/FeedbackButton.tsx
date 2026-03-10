"use client";

import { MessageSquarePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface FeedbackButtonProps {
  onOpen: () => void;
}

export function FeedbackButton({ onOpen }: FeedbackButtonProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            onClick={onOpen}
            className="fixed bottom-6 right-6 z-50 h-12 w-12 rounded-full shadow-lg hover:scale-105 transition-transform"
            size="icon"
          >
            <MessageSquarePlus className="h-5 w-5" />
            <span className="sr-only">Send Feedback</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="left">Send Feedback</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
