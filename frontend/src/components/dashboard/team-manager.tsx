"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { EmptyState, ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { useToast } from "@/components/toast-provider";
import {
  addWorkspaceMember,
  fetchWorkspaceList,
  fetchWorkspaceMembers,
  removeWorkspaceMember,
  updateWorkspaceMemberRole,
  type WorkspaceMemberSummary,
  type WorkspaceSummary,
} from "@/lib/team";

const roleOptions: WorkspaceMemberSummary["role"][] = ["admin", "team_member", "viewer"];

export function TeamManager() {
  const { pushToast } = useToast();
  const emailInputRef = useRef<HTMLInputElement | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [members, setMembers] = useState<WorkspaceMemberSummary[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<WorkspaceMemberSummary["role"]>("team_member");
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isMembersLoading, setIsMembersLoading] = useState(false);
  const [isAddingMember, setIsAddingMember] = useState(false);
  const [busyMemberId, setBusyMemberId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null,
    [selectedWorkspaceId, workspaces],
  );
  const canManageMembers = selectedWorkspace?.role === "admin";
  const adminCount = members.filter((member) => member.role === "admin").length;

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      setIsBootstrapping(true);
      setError("");
      try {
        const workspaceList = await fetchWorkspaceList();
        if (!active) {
          return;
        }
        setWorkspaces(workspaceList);
        setSelectedWorkspaceId((current) => current || workspaceList[0]?.id || "");
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(
          loadError instanceof Error ? loadError.message : "Could not load team workspaces.",
        );
      } finally {
        if (active) {
          setIsBootstrapping(false);
        }
      }
    }

    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setMembers([]);
      return;
    }

    let active = true;

    async function loadMembers() {
      setIsMembersLoading(true);
      setError("");
      try {
        const workspaceMembers = await fetchWorkspaceMembers(selectedWorkspaceId);
        if (!active) {
          return;
        }
        setMembers(workspaceMembers);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(
          loadError instanceof Error ? loadError.message : "Could not load workspace members.",
        );
      } finally {
        if (active) {
          setIsMembersLoading(false);
        }
      }
    }

    void loadMembers();
    return () => {
      active = false;
    };
  }, [selectedWorkspaceId]);

  async function handleAddMember() {
    if (!selectedWorkspaceId) {
      return;
    }
    setIsAddingMember(true);
    try {
      const createdMember = await addWorkspaceMember(selectedWorkspaceId, { email, role });
      setMembers((current) => [...current, createdMember]);
      setEmail("");
      setRole("team_member");
      pushToast({
        title: "Teammate added",
        description: `${createdMember.full_name} now has ${createdMember.role} access.`,
        tone: "success",
      });
    } catch (addError) {
      pushToast({
        title: "Could not add teammate",
        description: addError instanceof Error ? addError.message : "Please try again.",
        tone: "error",
      });
    } finally {
      setIsAddingMember(false);
    }
  }

  async function handleRoleChange(memberId: string, nextRole: WorkspaceMemberSummary["role"]) {
    if (!selectedWorkspaceId) {
      return;
    }
    setBusyMemberId(memberId);
    try {
      const updatedMember = await updateWorkspaceMemberRole(selectedWorkspaceId, memberId, {
        role: nextRole,
      });
      setMembers((current) =>
        current.map((member) => (member.id === memberId ? updatedMember : member)),
      );
      pushToast({
        title: "Role updated",
        description: `${updatedMember.full_name} now has ${updatedMember.role} access.`,
        tone: "success",
      });
    } catch (updateError) {
      pushToast({
        title: "Role update failed",
        description: updateError instanceof Error ? updateError.message : "Please try again.",
        tone: "error",
      });
    } finally {
      setBusyMemberId(null);
    }
  }

  async function handleRemoveMember(member: WorkspaceMemberSummary) {
    if (!selectedWorkspaceId) {
      return;
    }
    setBusyMemberId(member.id);
    try {
      await removeWorkspaceMember(selectedWorkspaceId, member.id);
      setMembers((current) => current.filter((item) => item.id !== member.id));
      pushToast({
        title: "Member removed",
        description: `${member.full_name} no longer has workspace access.`,
        tone: "success",
      });
    } catch (removeError) {
      pushToast({
        title: "Remove failed",
        description: removeError instanceof Error ? removeError.message : "Please try again.",
        tone: "error",
      });
    } finally {
      setBusyMemberId(null);
    }
  }

  if (isBootstrapping) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={2} />
        <LoadingGrid rows={4} />
      </main>
    );
  }

  if (error && !selectedWorkspaceId) {
    return (
      <ErrorState
        actionLabel="Retry loading"
        description={error}
        onAction={() => window.location.reload()}
        title="Team directory is unavailable"
      />
    );
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(6,182,212,0.14),transparent_30%),linear-gradient(140deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">
              Access and roles
            </p>
            <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
              Workspace Crew
            </h2>
            <p className="mt-4 text-base text-slate-300">
              Manage who can administer, operate, or observe the workspace. Teammates must already
              have an account before they can be added here.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <select
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none"
              onChange={(event) => setSelectedWorkspaceId(event.target.value)}
              value={selectedWorkspaceId}
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name} - {workspace.role}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Workspace members</p>
            <p className="mt-3 text-3xl font-semibold text-white">{members.length}</p>
            <p className="mt-2 text-sm text-slate-500">Current operators and observers</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Admins</p>
            <p className="mt-3 text-3xl font-semibold text-white">{adminCount}</p>
            <p className="mt-2 text-sm text-slate-500">At least one admin must remain</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">Your access</p>
            <p className="mt-3 text-3xl font-semibold text-white">
              {selectedWorkspace?.role ?? "viewer"}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              Only workspace admins can manage members
            </p>
          </div>
        </div>
      </section>

      {error && selectedWorkspaceId ? (
        <ErrorState
          actionLabel="Retry loading"
          description={error}
          onAction={() => window.location.reload()}
          title="Team access details could not be loaded"
        />
      ) : null}

      <section className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
        <div className="flex flex-col gap-6">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Add teammate</p>
            <h3 className="mt-3 text-2xl font-semibold text-white">Grant workspace access</h3>
            <p className="mt-2 text-sm text-slate-400">
              Enter the email of an existing account and choose the role to assign.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-[1.6fr_1fr_auto]">
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
              disabled={!canManageMembers || isAddingMember}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="teammate@example.com"
              ref={emailInputRef}
              type="email"
              value={email}
            />
            <select
              className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-white outline-none"
              disabled={!canManageMembers || isAddingMember}
              onChange={(event) =>
                setRole(event.target.value as WorkspaceMemberSummary["role"])
              }
              value={role}
            >
              {roleOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <button
              className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canManageMembers || !email.trim() || isAddingMember}
              onClick={() => void handleAddMember()}
              type="button"
            >
              {isAddingMember ? "Adding..." : "Add teammate"}
            </button>
          </div>

          {!canManageMembers ? (
            <p className="text-sm text-amber-200">
              You need admin access in this workspace to add, update, or remove members.
            </p>
          ) : null}
        </div>
      </section>

      {isMembersLoading ? <LoadingGrid rows={4} /> : null}

      {!isMembersLoading && !members.length ? (
        <EmptyState
          actionLabel={canManageMembers ? "Add teammate" : undefined}
          description="No collaborators have joined this workspace yet. Add the first registered teammate to begin shared operations."
          onAction={canManageMembers ? () => emailInputRef.current?.focus() : undefined}
          title="Your team roster is empty"
        />
      ) : null}

      {!isMembersLoading && members.length ? (
        <section className="grid gap-4">
          {members.map((member) => {
            const isBusy = busyMemberId === member.id;
            return (
              <article
                key={member.id}
                className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6"
              >
                <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{member.full_name}</h3>
                    <p className="mt-2 text-sm text-slate-400">{member.email}</p>
                  </div>

                  <div className="flex flex-col gap-3 md:flex-row md:items-center">
                    <select
                      className="rounded-full border border-white/10 bg-slate-950/50 px-4 py-2 text-sm text-white outline-none disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!canManageMembers || isBusy}
                      onChange={(event) =>
                        void handleRoleChange(
                          member.id,
                          event.target.value as WorkspaceMemberSummary["role"],
                        )
                      }
                      value={member.role}
                    >
                      {roleOptions.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                    <button
                      className="rounded-full border border-rose-400/20 bg-rose-500/10 px-4 py-2 text-sm text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!canManageMembers || isBusy}
                      onClick={() => void handleRemoveMember(member)}
                      type="button"
                    >
                      {isBusy ? "Working..." : "Remove"}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      ) : null}
    </main>
  );
}
