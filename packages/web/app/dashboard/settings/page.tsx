"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { GoogleCalendarSection } from "@/components/settings/google-calendar-section";
import { Settings, User } from "lucide-react";
import type { User as SupabaseUser } from "@supabase/supabase-js";

export default function SettingsPage() {
  const [user, setUser] = useState<SupabaseUser | null>(null);

  useEffect(() => {
    createClient()
      .auth.getUser()
      .then(({ data }) => setUser(data.user));
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-2">
        <Settings className="h-6 w-6" />
        <h1 className="text-2xl font-bold">Settings</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Account
          </CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-sm">
            <p className="text-muted-foreground">Email</p>
            <p className="font-medium">{user?.email ?? "..."}</p>
          </div>
        </CardContent>
      </Card>

      <GoogleCalendarSection />
    </div>
  );
}
