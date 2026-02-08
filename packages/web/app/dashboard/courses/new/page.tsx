import { CourseForm } from "@/components/course-form";

export default function NewCoursePage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Create Course</h1>
        <p className="text-muted-foreground">
          Add a new course to track your assessments and study schedule.
        </p>
      </div>
      <CourseForm />
    </div>
  );
}
