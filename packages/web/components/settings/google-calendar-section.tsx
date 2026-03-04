"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { GoogleIcon } from "@/components/icons/google";
import { toast } from "sonner";
import {
  getGoogleSyncStatus,
  triggerCalendarSync,
  toggleCalendarSync,
  disconnectGoogle,
} from "@/lib/api";
import { Calendar, RefreshCw, Unlink } from "lucide-react";

export function GoogleCalendarSection() {
  const [connected, setConnected] = useState(false);
  const [syncEnabled, setSyncEnabled] = useState(false);
  const [hasRefreshToken, setHasRefreshToken] = useState(false);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  async function loadStatus() {
    try {
      const status = await getGoogleSyncStatus();
      setConnected(status.connected);
      setSyncEnabled(status.calendar_sync_enabled);
      setHasRefreshToken(status.has_refresh_token);
    } catch {
      // Silently fail — user can retry
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function handleConnect() {
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        scopes: "https://www.googleapis.com/auth/calendar.events",
        redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: { access_type: "offline", prompt: "consent" },
      },
    });
    if (error) toast.error(error.message);
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await triggerCalendarSync();
      toast.success(
        `Sync complete: ${result.created} created, ${result.updated} updated` +
          (result.errors > 0 ? `, ${result.errors} errors` : ""),
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function handleToggle() {
    setToggling(true);
    try {
      await toggleCalendarSync(!syncEnabled);
      setSyncEnabled(!syncEnabled);
      toast.success(
        syncEnabled ? "Auto-sync disabled" : "Auto-sync enabled",
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setToggling(false);
    }
  }

  async function handleDisconnect() {
    setDisconnecting(true);
    try {
      await disconnectGoogle();
      setConnected(false);
      setSyncEnabled(false);
      setHasRefreshToken(false);
      toast.success("Google Calendar disconnected");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to disconnect");
    } finally {
      setDisconnecting(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Google Calendar
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          Google Calendar
        </CardTitle>
        <CardDescription>
          Sync your assessment due dates to Google Calendar
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!connected ? (
          <Button variant="outline" onClick={handleConnect}>
            <GoogleIcon className="mr-2 h-4 w-4" />
            Connect Google Calendar
          </Button>
        ) : (
          <>
            <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
              <div className="h-2 w-2 rounded-full bg-green-500" />
              Connected
              {!hasRefreshToken && (
                <span className="text-yellow-600 dark:text-yellow-400">
                  (limited — reconnect for full access)
                </span>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                variant={syncEnabled ? "default" : "outline"}
                size="sm"
                onClick={handleToggle}
                disabled={toggling}
              >
                {toggling
                  ? "Updating..."
                  : syncEnabled
                    ? "Auto-sync: On"
                    : "Auto-sync: Off"}
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={handleSync}
                disabled={syncing}
              >
                <RefreshCw
                  className={`mr-2 h-3 w-3 ${syncing ? "animate-spin" : ""}`}
                />
                {syncing ? "Syncing..." : "Sync Now"}
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleDisconnect}
                disabled={disconnecting}
                className="text-destructive hover:text-destructive"
              >
                <Unlink className="mr-2 h-3 w-3" />
                Disconnect
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
