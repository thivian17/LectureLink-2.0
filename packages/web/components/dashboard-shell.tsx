"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { getCourses } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  BookOpen,
  Calendar,
  ChevronRight,
  GraduationCap,
  Mic,
  Settings,
  LogOut,
  Menu,
  UserPlus,
  Shield,
  X,
} from "lucide-react";
import Link from "next/link";
import type { User } from "@supabase/supabase-js";
import type { Course } from "@/types/database";
import { MessageSquarePlus } from "lucide-react";
import { FeedbackDrawer } from "@/components/feedback/FeedbackDrawer";
import { FeedbackWidget } from "@/components/feedback/FeedbackWidget";

const navItems = [
  { label: "Study Hub", href: "/dashboard", icon: GraduationCap },
  { label: "Record", href: "/dashboard/record", icon: Mic },
  { label: "Calendar", href: "/dashboard/calendar", icon: Calendar },
  { label: "Invite Classmates", href: "/dashboard/invites", icon: UserPlus },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
];

export function DashboardShell({
  user,
  children,
}: {
  user: User;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [courses, setCourses] = useState<Course[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    getCourses()
      .then(setCourses)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const supabase = createClient();
    supabase
      .from("admin_users")
      .select("role")
      .eq("user_id", user.id)
      .maybeSingle()
      .then(({ data }) => {
        if (data) setIsAdmin(true);
      });
  }, [user.id]);

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-60 flex-col border-r bg-sidebar text-sidebar-foreground transition-transform lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center gap-3 px-4 font-semibold">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary shadow-sm shadow-primary/20">
            <BookOpen className="h-4 w-4 text-primary-foreground" />
          </div>
          <span>LectureLink</span>
        </div>
        <Separator />
        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
          {navItems.map((item) => {
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-brand-light text-brand font-medium"
                    : "text-sidebar-foreground/70 hover:text-brand hover:bg-sidebar-accent font-medium"
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}

          {isAdmin && (
            <Link
              href="/admin"
              onClick={() => setSidebarOpen(false)}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                pathname.startsWith("/admin")
                  ? "bg-brand-light text-brand font-medium"
                  : "text-sidebar-foreground/70 hover:text-brand hover:bg-sidebar-accent font-medium"
              }`}
            >
              <Shield className="h-4 w-4" />
              Admin
            </Link>
          )}

          {courses.length > 0 && (
            <>
              <Separator className="my-2" />
              <p className="px-3 py-1 text-xs font-medium text-sidebar-foreground/50 uppercase tracking-wider">
                Courses
              </p>
              {courses.map((course) => {
                const isActive = pathname.startsWith(
                  `/dashboard/courses/${course.id}`,
                );
                return (
                  <Link
                    key={course.id}
                    href={`/dashboard/courses/${course.id}`}
                    onClick={() => setSidebarOpen(false)}
                    className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? "bg-brand-light text-brand font-medium"
                        : "text-sidebar-foreground/70 hover:text-brand hover:bg-sidebar-accent font-medium"
                    }`}
                  >
                    <div className="w-2 h-2 rounded-full bg-primary/60 shrink-0" />
                    <span className="truncate">{course.name}</span>
                    <ChevronRight className="ml-auto h-3 w-3 shrink-0 opacity-50" />
                  </Link>
                );
              })}
            </>
          )}
        </nav>
        <div className="p-3">
          <button
            onClick={() => setFeedbackOpen(true)}
            className="flex w-full items-center gap-3 rounded-lg border border-dashed border-sidebar-foreground/20 px-3 py-2.5 text-sm text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-brand hover:border-brand/30"
          >
            <MessageSquarePlus className="h-4 w-4 shrink-0" />
            <span className="truncate">Feedback</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        {/* Top bar */}
        <header className="flex h-14 items-center justify-between border-b px-4">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            {sidebarOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </Button>
          <div className="flex-1" />
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {user.email}
            </span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </Button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">{children}</main>
      </div>
      <FeedbackDrawer open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
      <FeedbackWidget />
    </div>
  );
}
