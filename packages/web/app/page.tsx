import Link from "next/link";
import { Button } from "@/components/ui/button";
import { BookOpen } from "lucide-react";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="flex items-center gap-2">
        <BookOpen className="h-8 w-8" />
        <h1 className="text-4xl font-bold tracking-tight">LectureLink</h1>
      </div>
      <p className="max-w-md text-lg text-muted-foreground">
        AI-powered study planning. Upload your syllabus, track deadlines, and
        focus on what matters most.
      </p>
      <div className="flex gap-3">
        <Button asChild>
          <Link href="/signup">Get Started</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/login">Sign In</Link>
        </Button>
      </div>
    </div>
  );
}
