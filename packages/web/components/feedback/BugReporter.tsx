"use client";

import { useState } from "react";
import { Bug, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { submitBugReport, collectBrowserInfo } from "@/lib/feedback-api";

type Severity = "critical" | "high" | "medium" | "low";

export function BugReporter() {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    if (!title.trim() || !description.trim()) {
      toast.error("Please fill in title and description");
      return;
    }
    setSubmitting(true);
    try {
      await submitBugReport({
        title: title.trim(),
        description: description.trim(),
        severity,
        browserInfo: collectBrowserInfo(),
      });
      toast.success("Bug report submitted — thanks!");
      setOpen(false);
      setTitle("");
      setDescription("");
      setSeverity("medium");
    } catch {
      toast.error("Failed to submit report. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="fixed bottom-6 left-6 z-50">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setOpen(true)}
          className="shadow-md gap-2"
          aria-label="Report a bug"
        >
          <Bug className="h-4 w-4" />
          <span className="hidden sm:inline">Report Bug</span>
        </Button>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Report a Bug</DialogTitle>
            <DialogDescription>
              Found something broken? Let us know and we&apos;ll fix it fast.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="bug-title">What&apos;s broken?</Label>
              <Input
                id="bug-title"
                placeholder="e.g. Quiz doesn't load on mobile"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="bug-desc">Steps to reproduce</Label>
              <textarea
                id="bug-desc"
                className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                placeholder={"1. Go to quiz page\n2. Click Start\n3. See error"}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={5000}
              />
            </div>

            <div className="space-y-1">
              <Label>How bad is it?</Label>
              <Select
                value={severity}
                onValueChange={(v) => setSeverity(v as Severity)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Minor — cosmetic issue</SelectItem>
                  <SelectItem value="medium">
                    Moderate — feature partially broken
                  </SelectItem>
                  <SelectItem value="high">
                    High — can&apos;t complete a task
                  </SelectItem>
                  <SelectItem value="critical">
                    Critical — app is unusable
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <p className="text-xs text-muted-foreground">
              Browser info and current page are automatically included.
            </p>

            <div className="flex gap-2 justify-end">
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={submitting}>
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Submit Report"
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
