"use client";

import { AlertCircle, RefreshCcw, WifiOff, Clock, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  AuthError,
  RateLimitError,
  NotFoundError,
  ApiError,
} from "@/lib/api-errors";

interface ErrorStateProps {
  error: Error;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ error, onRetry, className }: ErrorStateProps) {
  const config = getErrorConfig(error);

  return (
    <Card className={className}>
      <CardContent className="flex flex-col items-center justify-center py-12 text-center">
        <config.icon className="h-10 w-10 text-muted-foreground/50" />
        <h3 className="mt-4 text-lg font-medium">{config.title}</h3>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          {config.description}
        </p>
        {config.showRetry && onRetry && (
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={onRetry}
          >
            <RefreshCcw className="mr-2 h-4 w-4" />
            {config.retryLabel}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function getErrorConfig(error: Error) {
  if (error instanceof AuthError) {
    return {
      icon: Lock,
      title: "Session Expired",
      description: "Your session has expired. Please log in again.",
      showRetry: true,
      retryLabel: "Log In",
    };
  }
  if (error instanceof RateLimitError) {
    const minutes = Math.ceil(error.retryAfterSeconds / 60);
    return {
      icon: Clock,
      title: "Too Many Requests",
      description: `You've hit the rate limit. Please try again in ${minutes} minute${minutes !== 1 ? "s" : ""}.`,
      showRetry: true,
      retryLabel: "Try Again",
    };
  }
  if (error instanceof NotFoundError) {
    return {
      icon: AlertCircle,
      title: "Not Found",
      description:
        error.detail ?? "The resource you're looking for doesn't exist.",
      showRetry: false,
      retryLabel: "",
    };
  }
  if (error instanceof ApiError) {
    return {
      icon: AlertCircle,
      title: "Something Went Wrong",
      description: error.detail ?? error.message,
      showRetry: true,
      retryLabel: "Retry",
    };
  }
  // Network error
  if (error instanceof TypeError && error.message.includes("fetch")) {
    return {
      icon: WifiOff,
      title: "Connection Error",
      description: "Unable to reach the server. Check your internet connection.",
      showRetry: true,
      retryLabel: "Retry",
    };
  }
  return {
    icon: AlertCircle,
    title: "Something Went Wrong",
    description: error.message || "An unexpected error occurred.",
    showRetry: true,
    retryLabel: "Retry",
  };
}
