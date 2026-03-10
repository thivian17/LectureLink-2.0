"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Copy, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createInvite, listInvites } from "@/lib/api";
import type { Invite } from "@/types/database";

export default function InvitesPage() {
  const [invites, setInvites] = useState<Invite[]>([]);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadInvites = useCallback(async () => {
    try {
      const data = await listInvites();
      setInvites(data);
    } catch {
      toast.error("Failed to load invites");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInvites();
  }, [loadInvites]);

  async function handleCreate() {
    setCreating(true);
    try {
      const invite = await createInvite({});
      setInvites((prev) => [invite, ...prev]);
      await navigator.clipboard.writeText(invite.invite_url);
      toast.success("Invite link created and copied!");
    } catch {
      toast.error("Failed to create invite");
    } finally {
      setCreating(false);
    }
  }

  function copyLink(url: string) {
    navigator.clipboard.writeText(url);
    toast.success("Copied to clipboard");
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Invite Classmates
        </h1>
        <p className="text-muted-foreground mt-1">
          Share LectureLink with classmates using a personal invite link.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Your invite links</CardTitle>
          <CardDescription>
            Each link can be used up to 10 times and expires in 30 days.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button onClick={handleCreate} disabled={creating} size="sm">
            <Plus className="h-4 w-4 mr-2" />
            {creating ? "Creating..." : "Create invite link"}
          </Button>

          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : invites.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No invite links yet.
            </p>
          ) : (
            <div className="space-y-2">
              {invites.map((inv) => (
                <div
                  key={inv.invite_code}
                  className="flex items-center gap-2 p-3 rounded-lg border"
                >
                  <Input
                    value={inv.invite_url}
                    readOnly
                    className="text-xs h-8 flex-1"
                  />
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {inv.use_count}/{inv.max_uses} used
                  </span>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 shrink-0"
                    onClick={() => copyLink(inv.invite_url)}
                  >
                    <Copy className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
