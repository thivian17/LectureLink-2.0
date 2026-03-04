import Link from "next/link";
import { Button } from "@/components/ui/button";
import { BookOpen } from "lucide-react";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-4 text-center">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary shadow-lg shadow-primary/25">
          <BookOpen className="h-6 w-6 text-primary-foreground" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight">LectureLink</h1>
      </div>
      <p className="max-w-md text-lg text-muted-foreground">
        AI-powered study planning. Upload your syllabus, track deadlines, and
        focus on what matters most.
      </p>
      <div className="flex gap-3">
        <Button asChild size="lg">
          <Link href="/signup">Get Started</Link>
        </Button>
        <Button variant="outline" asChild size="lg">
          <Link href="/login">Sign In</Link>
        </Button>
      </div>
    </div>
  );
}
