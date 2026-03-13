"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Copy, Link as LinkIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createInvite } from "@/lib/api";
import type { Invite } from "@/types/database";

export default function InvitesPage() {
  const [invite, setInvite] = useState<Invite | null>(null);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState(false);

  async function handleCreate() {
    setCreating(true);
    try {
      const inv = await createInvite({});
      setInvite(inv);
      setCreated(true);
      await navigator.clipboard.writeText(inv.invite_url);
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
          <CardTitle className="text-base">Your invite link</CardTitle>
          <CardDescription>
            Generate a link to share with classmates. It can be used up to 10
            times and expires in 30 days.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {invite ? (
            <div className="flex items-center gap-2 p-3 rounded-lg border">
              <Input
                value={invite.invite_url}
                readOnly
                className="text-xs h-8 flex-1"
              />
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {invite.use_count}/{invite.max_uses} used
              </span>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8 shrink-0"
                onClick={() => copyLink(invite.invite_url)}
              >
                <Copy className="h-3 w-3" />
              </Button>
            </div>
          ) : (
            <Button onClick={handleCreate} disabled={creating || created} size="sm">
              <LinkIcon className="h-4 w-4 mr-2" />
              {creating ? "Creating..." : "Generate invite link"}
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
