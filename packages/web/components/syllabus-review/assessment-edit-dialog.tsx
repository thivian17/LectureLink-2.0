"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Calendar } from "@/components/ui/calendar";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { ASSESSMENT_TYPES } from "@/types/extraction";
import type { UpdateAssessmentInput } from "@/lib/api";
import type { Assessment } from "@/types/database";

const assessmentSchema = z.object({
  title: z.string().min(1, "Title is required"),
  type: z.string().min(1, "Type is required"),
  due_date: z.date().nullable(),
  weight_percent: z.number().min(0).max(100).nullable(),
  topics: z.string(),
});

type FormValues = z.infer<typeof assessmentSchema>;

interface AssessmentEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assessment: Assessment;
  onSave: (updates: UpdateAssessmentInput) => void;
}

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function AssessmentEditDialog({
  open,
  onOpenChange,
  assessment,
  onSave,
}: AssessmentEditDialogProps) {
  const form = useForm<FormValues>({
    resolver: zodResolver(assessmentSchema),
    defaultValues: {
      title: assessment.title,
      type: assessment.type,
      due_date: assessment.due_date ? parseLocalDate(assessment.due_date) : null,
      weight_percent: assessment.weight_percent,
      topics: assessment.topics?.join(", ") ?? "",
    },
  });

  function handleSubmit(values: FormValues) {
    const updates: UpdateAssessmentInput = {
      title: values.title,
      type: values.type,
      due_date: values.due_date
        ? format(values.due_date, "yyyy-MM-dd")
        : null,
      weight_percent: values.weight_percent,
      topics: values.topics
        ? values.topics.split(",").map((t) => t.trim()).filter(Boolean)
        : null,
    };
    if (assessment.is_date_ambiguous && values.due_date) {
      updates.is_date_ambiguous = false;
    }
    onSave(updates);
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit Assessment</DialogTitle>
          <DialogDescription>
            Update the details for this assessment.
            {assessment.due_date_raw && (
              <span className="block mt-1 text-xs">
                Original text: &ldquo;{assessment.due_date_raw}&rdquo;
              </span>
            )}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="space-y-4"
          >
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Title</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select type" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {ASSESSMENT_TYPES.map((t) => (
                        <SelectItem key={t} value={t}>
                          {t.charAt(0).toUpperCase() + t.slice(1)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="due_date"
              render={({ field }) => (
                <FormItem className="flex flex-col">
                  <FormLabel>Due Date</FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button
                          variant="outline"
                          className={cn(
                            "w-full pl-3 text-left font-normal",
                            !field.value && "text-muted-foreground",
                          )}
                        >
                          {field.value
                            ? format(field.value, "PPP")
                            : "Pick a date"}
                          <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                        </Button>
                      </FormControl>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={field.value ?? undefined}
                        onSelect={field.onChange}
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                  {assessment.due_date_raw && (
                    <FormDescription>
                      Original: &ldquo;{assessment.due_date_raw}&rdquo;
                    </FormDescription>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="weight_percent"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Weight (%)</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      step="0.1"
                      {...field}
                      value={field.value ?? ""}
                      onChange={(e) =>
                        field.onChange(
                          e.target.value === "" ? null : Number(e.target.value),
                        )
                      }
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="topics"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Topics</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Comma-separated topics"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    Separate topics with commas
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit">Save Changes</Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
