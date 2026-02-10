"use client";

import React from "react";
import { Check, Clock, Loader2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type ProcessingStatus = "pending" | "processing" | "completed" | "failed";

const STATUS_CONFIG: Record<
  ProcessingStatus,
  { label: string; className: string; icon: React.ElementType }
> = {
  pending: {
    label: "Pending",
    className: "bg-gray-100 text-gray-700 border-gray-200",
    icon: Clock,
  },
  processing: {
    label: "Processing...",
    className: "bg-blue-100 text-blue-700 border-blue-200",
    icon: Loader2,
  },
  completed: {
    label: "Ready",
    className: "bg-green-100 text-green-700 border-green-200",
    icon: Check,
  },
  failed: {
    label: "Failed",
    className: "bg-red-100 text-red-700 border-red-200",
    icon: XCircle,
  },
};

interface StatusBadgeProps {
  status: ProcessingStatus;
  className?: string;
}

export const StatusBadge = React.memo(function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      className={cn("gap-1 font-medium", config.className, className)}
    >
      <Icon
        className={cn("h-3 w-3", status === "processing" && "animate-spin")}
      />
      {config.label}
    </Badge>
  );
});
