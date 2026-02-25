"use client";

import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";
import { CalendarIcon, Loader2, Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Calendar } from "@/components/ui/calendar";
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { cn } from "@/lib/utils";
import { createCourse, updateCourse, type CourseInput } from "@/lib/api";
import type { Course } from "@/types/database";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"] as const;

const GRADE_OPTIONS = [
  { label: "A+ (97%)", value: "0.97" },
  { label: "A (93%)", value: "0.93" },
  { label: "A- (90%)", value: "0.9" },
  { label: "B+ (87%)", value: "0.87" },
  { label: "B (83%)", value: "0.83" },
  { label: "B- (80%)", value: "0.8" },
  { label: "C+ (77%)", value: "0.77" },
  { label: "C (73%)", value: "0.73" },
];

const courseFormSchema = z.object({
  name: z.string().min(1, "Course name is required"),
  code: z.string(),
  semester_start: z.date({ error: "Start date is required" }),
  semester_end: z.date({ error: "End date is required" }),
  meeting_days: z.array(z.string()).min(1, "Select at least one meeting day"),
  meeting_time: z.string(),
  target_grade: z.string(),
  holidays: z.array(
    z.object({
      name: z.string().min(1, "Holiday name is required"),
      start_date: z.date({ error: "Start date is required" }),
      end_date: z.date({ error: "End date is required" }),
    }),
  ),
});

type CourseFormValues = z.infer<typeof courseFormSchema>;

interface CourseFormProps {
  course?: Course;
  onSuccess?: () => void;
}

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function CourseForm({ course, onSuccess }: CourseFormProps) {
  const router = useRouter();
  const isEditing = !!course;

  const form = useForm<CourseFormValues>({
    resolver: zodResolver(courseFormSchema),
    defaultValues: {
      name: course?.name ?? "",
      code: course?.code ?? "",
      semester_start: course?.semester_start
        ? parseLocalDate(course.semester_start)
        : undefined,
      semester_end: course?.semester_end
        ? parseLocalDate(course.semester_end)
        : undefined,
      meeting_days: course?.meeting_days ?? [],
      meeting_time: course?.meeting_time ?? "",
      target_grade: course?.target_grade?.toString() ?? "0.8",
      holidays:
        (
          course?.holidays as
            | { name: string; start_date: string; end_date: string }[]
            | undefined
        )?.map((h) => ({
          name: h.name,
          start_date: parseLocalDate(h.start_date),
          end_date: parseLocalDate(h.end_date),
        })) ?? [],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "holidays",
  });

  async function onSubmit(values: CourseFormValues) {
    const input: CourseInput = {
      name: values.name,
      code: values.code || null,
      semester_start: format(values.semester_start, "yyyy-MM-dd"),
      semester_end: format(values.semester_end, "yyyy-MM-dd"),
      meeting_days: values.meeting_days,
      meeting_time: values.meeting_time || null,
      target_grade: parseFloat(values.target_grade),
      holidays: values.holidays.map((h) => ({
        name: h.name,
        start_date: format(h.start_date, "yyyy-MM-dd"),
        end_date: format(h.end_date, "yyyy-MM-dd"),
      })),
    };

    try {
      if (isEditing) {
        await updateCourse(course.id, input);
        toast.success("Course updated");
        onSuccess?.();
      } else {
        const created = await createCourse(input);
        toast.success("Course created");
        router.push(`/dashboard/courses/${created.id}/onboarding`);
      }
    } catch {
      toast.error(
        isEditing ? "Failed to update course" : "Failed to create course",
      );
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        {/* Name + Code */}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Course Name *</FormLabel>
                <FormControl>
                  <Input
                    placeholder="PHYS 201: Thermodynamics"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="code"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Course Code</FormLabel>
                <FormControl>
                  <Input placeholder="PHYS 201" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Semester Dates */}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="semester_start"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Semester Start *</FormLabel>
                <Popover>
                  <PopoverTrigger asChild>
                    <FormControl>
                      <Button
                        variant="outline"
                        className={cn(
                          "w-full justify-start text-left font-normal",
                          !field.value && "text-muted-foreground",
                        )}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {field.value
                          ? format(field.value, "PPP")
                          : "Pick a date"}
                      </Button>
                    </FormControl>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={field.value}
                      onSelect={field.onChange}
                    />
                  </PopoverContent>
                </Popover>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="semester_end"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Semester End *</FormLabel>
                <Popover>
                  <PopoverTrigger asChild>
                    <FormControl>
                      <Button
                        variant="outline"
                        className={cn(
                          "w-full justify-start text-left font-normal",
                          !field.value && "text-muted-foreground",
                        )}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {field.value
                          ? format(field.value, "PPP")
                          : "Pick a date"}
                      </Button>
                    </FormControl>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={field.value}
                      onSelect={field.onChange}
                    />
                  </PopoverContent>
                </Popover>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Meeting Days */}
        <FormField
          control={form.control}
          name="meeting_days"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Meeting Days *</FormLabel>
              <div className="flex flex-wrap gap-2">
                {DAYS.map((day) => {
                  const selected = field.value.includes(day);
                  return (
                    <Button
                      key={day}
                      type="button"
                      variant={selected ? "default" : "outline"}
                      size="sm"
                      onClick={() => {
                        field.onChange(
                          selected
                            ? field.value.filter((d: string) => d !== day)
                            : [...field.value, day],
                        );
                      }}
                    >
                      {day}
                    </Button>
                  );
                })}
              </div>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Meeting Time + Target Grade */}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="meeting_time"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Meeting Time</FormLabel>
                <FormControl>
                  <Input placeholder="2:00 PM - 3:15 PM" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="target_grade"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Target Grade</FormLabel>
                <Select
                  onValueChange={field.onChange}
                  defaultValue={field.value}
                >
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {GRADE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Holidays */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <FormLabel>Holidays</FormLabel>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                append({
                  name: "",
                  start_date: new Date(),
                  end_date: new Date(),
                })
              }
            >
              <Plus className="mr-2 h-4 w-4" />
              Add Holiday
            </Button>
          </div>
          {fields.map((fieldItem, index) => (
            <div
              key={fieldItem.id}
              className="grid gap-4 items-end rounded-md border p-4 sm:grid-cols-[1fr_1fr_1fr_auto]"
            >
              <FormField
                control={form.control}
                name={`holidays.${index}.name`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Name</FormLabel>
                    <FormControl>
                      <Input placeholder="Spring Break" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name={`holidays.${index}.start_date`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Start</FormLabel>
                    <Popover>
                      <PopoverTrigger asChild>
                        <FormControl>
                          <Button
                            variant="outline"
                            className={cn(
                              "w-full justify-start text-left font-normal",
                              !field.value && "text-muted-foreground",
                            )}
                          >
                            <CalendarIcon className="mr-2 h-4 w-4" />
                            {field.value
                              ? format(field.value, "MMM d")
                              : "Pick date"}
                          </Button>
                        </FormControl>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={field.value}
                          onSelect={field.onChange}
                        />
                      </PopoverContent>
                    </Popover>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name={`holidays.${index}.end_date`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>End</FormLabel>
                    <Popover>
                      <PopoverTrigger asChild>
                        <FormControl>
                          <Button
                            variant="outline"
                            className={cn(
                              "w-full justify-start text-left font-normal",
                              !field.value && "text-muted-foreground",
                            )}
                          >
                            <CalendarIcon className="mr-2 h-4 w-4" />
                            {field.value
                              ? format(field.value, "MMM d")
                              : "Pick date"}
                          </Button>
                        </FormControl>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={field.value}
                          onSelect={field.onChange}
                        />
                      </PopoverContent>
                    </Popover>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => remove(index)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {isEditing ? "Saving..." : "Creating..."}
              </>
            ) : isEditing ? (
              "Save Changes"
            ) : (
              "Create Course"
            )}
          </Button>
          {!isEditing && (
            <Button
              type="button"
              variant="outline"
              onClick={() => router.back()}
            >
              Cancel
            </Button>
          )}
        </div>
      </form>
    </Form>
  );
}
