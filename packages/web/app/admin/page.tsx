"use client";

import { useState, useEffect, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Users, Bug, MessageSquare, BarChart3, RefreshCw } from "lucide-react";
import {
  adminApi,
  type AdminOverview, type AdminUser, type BugReport, type UserFeedback,
} from "@/lib/admin-api";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-slate-100 text-slate-700 border-slate-200",
};

const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  resolved: "bg-green-100 text-green-800",
  wont_fix: "bg-slate-100 text-slate-600",
};

function KpiCard({ title, value, sub }: { title: string; value: number | string; sub?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function OverviewTab({ overview }: { overview: AdminOverview | null }) {
  if (!overview) return <p className="text-muted-foreground text-sm">Loading...</p>;
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Active Users</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard title="Daily Active (DAU)" value={overview.dau} sub="last 24h" />
          <KpiCard title="Weekly Active (WAU)" value={overview.wau} sub="last 7 days" />
          <KpiCard title="Monthly Active (MAU)" value={overview.mau} sub="last 30 days" />
          <KpiCard title="Total Users" value={overview.total_users} />
        </div>
      </div>
      <div>
        <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">This Week</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard title="Learn Sessions" value={overview.learn_sessions_week} />
          <KpiCard title="Quiz Attempts" value={overview.quiz_attempts_week} />
          <KpiCard title="Open Bugs" value={overview.bugs_open} sub="needs attention" />
          <KpiCard title="Unread Feedback" value={overview.feedback_unread} sub="needs review" />
        </div>
      </div>
    </div>
  );
}

function UsersTab({ users }: { users: AdminUser[] }) {
  return (
    <div className="rounded-md border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-3 font-medium">Email</th>
            <th className="text-left p-3 font-medium hidden md:table-cell">Joined</th>
            <th className="text-left p-3 font-medium hidden md:table-cell">Last Active</th>
            <th className="text-right p-3 font-medium">Sessions</th>
            <th className="text-right p-3 font-medium">Level</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {users.map((u) => (
            <tr key={u.id} className="hover:bg-muted/20 transition-colors">
              <td className="p-3 font-mono text-xs">{u.email}</td>
              <td className="p-3 text-muted-foreground hidden md:table-cell">
                {new Date(u.created_at).toLocaleDateString()}
              </td>
              <td className="p-3 text-muted-foreground hidden md:table-cell">
                {u.last_active ? new Date(u.last_active).toLocaleDateString() : "Never"}
              </td>
              <td className="p-3 text-right">{u.session_count}</td>
              <td className="p-3 text-right text-xs font-medium">Lv {u.level.current_level}</td>
            </tr>
          ))}
          {users.length === 0 && (
            <tr><td colSpan={5} className="p-6 text-center text-muted-foreground">No users found</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function BugsTab({ bugs, onUpdateBug }: {
  bugs: BugReport[];
  onUpdateBug: (id: string, status: string) => Promise<void>;
}) {
  return (
    <div className="space-y-3">
      {bugs.map((bug) => (
        <Card key={bug.id}>
          <CardContent className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded border ${SEVERITY_COLORS[bug.severity] ?? ""}`}>
                    {bug.severity}
                  </span>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${STATUS_COLORS[bug.status] ?? ""}`}>
                    {bug.status.replace("_", " ")}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(bug.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="font-medium mt-1">{bug.title}</p>
                <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{bug.description}</p>
                {bug.page_path && (
                  <p className="text-xs font-mono text-muted-foreground mt-1">{bug.page_path}</p>
                )}
                {bug.admin_notes && (
                  <p className="text-xs bg-muted rounded px-2 py-1 mt-2">Notes: {bug.admin_notes}</p>
                )}
              </div>
              <Select value={bug.status} onValueChange={(v) => onUpdateBug(bug.id, v)}>
                <SelectTrigger className="w-32 h-7 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="in_progress">In Progress</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                  <SelectItem value="wont_fix">Won&#39;t Fix</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      ))}
      {bugs.length === 0 && (
        <p className="text-center text-muted-foreground py-8">No bugs found</p>
      )}
    </div>
  );
}

function FeedbackTab({ feedback, onMarkRead }: {
  feedback: UserFeedback[];
  onMarkRead: (id: string) => Promise<void>;
}) {
  const npsScores = feedback.filter((f) => f.feedback_type === "nps" && f.rating);
  const avgNps = npsScores.length
    ? (npsScores.reduce((s, f) => s + (f.rating ?? 0), 0) / npsScores.length).toFixed(1)
    : null;

  return (
    <div className="space-y-6">
      {avgNps !== null && (
        <Card>
          <CardContent className="p-4 flex items-center gap-6">
            <div>
              <p className="text-xs text-muted-foreground">Average NPS Score</p>
              <p className="text-3xl font-bold">{avgNps}<span className="text-base text-muted-foreground">/10</span></p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Responses</p>
              <p className="text-3xl font-bold">{npsScores.length}</p>
            </div>
          </CardContent>
        </Card>
      )}
      <div className="space-y-3">
        {feedback.map((f) => (
          <Card key={f.id} className={f.status === "unread" ? "border-blue-200" : ""}>
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline" className="text-xs">{f.feedback_type}</Badge>
                    {f.feature_tag && <Badge variant="secondary" className="text-xs">{f.feature_tag}</Badge>}
                    {f.rating !== undefined && f.rating !== null && (
                      <span className={`text-xs font-bold ${
                        f.rating >= 9 ? "text-green-600" : f.rating >= 7 ? "text-amber-600" : "text-red-600"
                      }`}>{f.rating}/10</span>
                    )}
                    {f.status === "unread" && (
                      <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">New</span>
                    )}
                    <span className="text-xs text-muted-foreground ml-auto">
                      {new Date(f.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {f.message && <p className="text-sm mt-2">{f.message}</p>}
                </div>
                {f.status === "unread" && (
                  <Button size="sm" variant="ghost" className="text-xs h-7" onClick={() => onMarkRead(f.id)}>
                    Mark read
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
        {feedback.length === 0 && (
          <p className="text-center text-muted-foreground py-8">No feedback yet</p>
        )}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [bugs, setBugs] = useState<BugReport[]>([]);
  const [feedback, setFeedback] = useState<UserFeedback[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [unauthorized, setUnauthorized] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, bu, fb] = await Promise.all([
        adminApi.getOverview(),
        adminApi.listBugs(),
        adminApi.listFeedback(),
      ]);
      setOverview(ov);
      setBugs(bu.bugs);
      setFeedback(fb.feedback);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("Not authorized")) setUnauthorized(true);
      else toast.error("Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadUsers = useCallback(async () => {
    try {
      const res = await adminApi.listUsers();
      setUsers(res.users);
    } catch {
      toast.error("Failed to load users");
    }
  }, []);

  useEffect(() => { void loadAll(); }, [loadAll]);

  useEffect(() => {
    if (activeTab === "users" && users.length === 0) void loadUsers();
  }, [activeTab, users.length, loadUsers]);

  async function handleUpdateBug(id: string, newStatus: string) {
    try {
      await adminApi.updateBug(id, newStatus);
      setBugs((prev) => prev.map((b) => b.id === id ? { ...b, status: newStatus as BugReport["status"] } : b));
      toast.success("Bug status updated");
    } catch { toast.error("Failed to update bug"); }
  }

  async function handleMarkFeedbackRead(id: string) {
    try {
      await adminApi.updateFeedbackStatus(id, "read");
      setFeedback((prev) => prev.map((f) => f.id === id ? { ...f, status: "read" as const } : f));
    } catch { toast.error("Failed to update feedback"); }
  }

  if (unauthorized) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <p className="text-lg font-medium">Access Denied</p>
        <p className="text-muted-foreground text-sm">You need admin access to view this page.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <Button variant="outline" size="sm" onClick={loadAll} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-4 w-full max-w-lg">
          <TabsTrigger value="overview" className="gap-1.5">
            <BarChart3 className="h-3.5 w-3.5" /> Overview
          </TabsTrigger>
          <TabsTrigger value="users" className="gap-1.5">
            <Users className="h-3.5 w-3.5" /> Users
          </TabsTrigger>
          <TabsTrigger value="bugs" className="relative gap-1.5">
            <Bug className="h-3.5 w-3.5" /> Bugs
            {overview && overview.bugs_open > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
                {overview.bugs_open > 9 ? "9+" : overview.bugs_open}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="feedback" className="relative gap-1.5">
            <MessageSquare className="h-3.5 w-3.5" /> Feedback
            {overview && overview.feedback_unread > 0 && (
              <span className="absolute -top-1 -right-1 bg-blue-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
                {overview.feedback_unread > 9 ? "9+" : overview.feedback_unread}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <OverviewTab overview={overview} />
        </TabsContent>
        <TabsContent value="users" className="mt-6">
          <UsersTab users={users} />
        </TabsContent>
        <TabsContent value="bugs" className="mt-6">
          <BugsTab bugs={bugs} onUpdateBug={handleUpdateBug} />
        </TabsContent>
        <TabsContent value="feedback" className="mt-6">
          <FeedbackTab feedback={feedback} onMarkRead={handleMarkFeedbackRead} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
