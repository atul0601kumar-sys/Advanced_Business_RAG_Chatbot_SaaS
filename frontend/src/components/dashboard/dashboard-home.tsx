"use client";

import { useEffect, useState } from "react";

import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { useToast } from "@/components/toast-provider";
import { apiRequest, fetchCurrentUser } from "@/lib/auth";

type Workspace = {
  id: string;
  name: string;
  role: string;
  status: string;
};

const quickActions = [
  "Import a new knowledge base",
  "Review yesterday's unresolved questions",
  "Invite team members to the workspace",
  "Publish the widget preview to staging",
];

export function DashboardHome() {
  const { pushToast } = useToast();
  const [user, setUser] = useState<Awaited<ReturnType<typeof fetchCurrentUser>> | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadDashboard() {
      setIsLoading(true);
      setIsError(false);

      try {
        const [userJson, workspaceJson] = await Promise.all([
          fetchCurrentUser(),
          apiRequest<Workspace[]>("/api/v1/workspaces"),
        ]);
        if (!active) {
          return;
        }
        setUser(userJson);
        setWorkspaces(workspaceJson);
      } catch {
        if (!active) {
          return;
        }
        setIsError(true);
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void loadDashboard();

    return () => {
      active = false;
    };
  }, []);

  if (isLoading) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={2} />
        <LoadingGrid rows={3} />
      </main>
    );
  }

  if (isError) {
    return (
      <ErrorState
        actionLabel="Retry dashboard"
        description="We could not load your workspace summary from the API. Confirm the backend is running and you are logged in."
        onAction={() => window.location.reload()}
        title="Dashboard data is temporarily unavailable"
      />
    );
  }

  return (
    <main className="space-y-8">
      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_34%),linear-gradient(140deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">Mission control</p>
          <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
            {user ? `Welcome back, ${user.full_name}` : "Welcome back"}
          </h2>
          <p className="mt-4 max-w-2xl text-slate-300">
            Your dashboard shell is ready with source management, chat oversight, and operational controls for the RAG workspace.
          </p>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
              <p className="text-sm text-slate-400">Active workspaces</p>
              <p className="mt-3 text-3xl font-semibold text-white">{workspaces.length}</p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
              <p className="text-sm text-slate-400">Primary role</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {user?.memberships[0]?.role ?? "viewer"}
              </p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
              <p className="text-sm text-slate-400">Response posture</p>
              <p className="mt-3 text-3xl font-semibold text-white">Stable</p>
            </div>
          </div>
        </div>

        <div className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-white">Quick actions</p>
              <p className="mt-1 text-sm text-slate-400">Designed for daily operator flows.</p>
            </div>
          </div>
          <div className="mt-5 space-y-3">
            {quickActions.map((action) => (
              <button
                key={action}
                className="flex w-full items-center justify-between rounded-2xl border border-white/10 bg-slate-900/80 px-4 py-3 text-left text-sm text-slate-200 transition hover:border-cyan-400/20"
                onClick={() =>
                  pushToast({
                    title: action,
                    description: "This quick action is wired into the dashboard shell demo.",
                    tone: "info",
                  })
                }
                type="button"
              >
                <span>{action}</span>
                <span className="text-slate-500">Open</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">Workspace memberships</h3>
              <p className="mt-1 text-sm text-slate-400">Live data from the protected backend endpoints.</p>
            </div>
          </div>
          <div className="mt-5 space-y-3">
            {user?.memberships.map((membership) => (
              <div
                key={`${membership.workspace_name}-${membership.role}`}
                className="rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-4"
              >
                <p className="font-medium text-white">{membership.workspace_name}</p>
                <p className="mt-1 text-sm text-slate-400">Role: {membership.role}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-6">
          <h3 className="text-lg font-semibold text-white">Workspace fleet</h3>
          <p className="mt-1 text-sm text-slate-400">Each workspace remains scoped by the auth module.</p>
          <div className="mt-5 space-y-3">
            {workspaces.map((workspace) => (
              <div
                key={workspace.id}
                className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-4"
              >
                <div>
                  <p className="font-medium text-white">{workspace.name}</p>
                  <p className="mt-1 text-sm text-slate-400">
                    {workspace.role} access • {workspace.status}
                  </p>
                </div>
                <button
                  className="rounded-full border border-white/10 px-3 py-1.5 text-sm text-slate-300"
                  onClick={() =>
                    pushToast({
                      title: `${workspace.name} selected`,
                      description: "Workspace switching can plug into future APIs from this shell.",
                      tone: "success",
                    })
                  }
                  type="button"
                >
                  Focus
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
