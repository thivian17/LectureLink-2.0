import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: adminRow } = await supabase
    .from("admin_users")
    .select("role")
    .eq("user_id", user.id)
    .single();

  if (!adminRow) redirect("/dashboard");

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b px-6 py-3 flex items-center gap-3">
        <span className="font-semibold text-sm">LectureLink Admin</span>
        <span className="text-xs text-muted-foreground bg-muted rounded px-2 py-0.5">
          {adminRow.role}
        </span>
      </div>
      <div className="container mx-auto py-6 px-4">
        {children}
      </div>
    </div>
  );
}
