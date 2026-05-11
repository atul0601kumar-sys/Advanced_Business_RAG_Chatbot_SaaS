"use client";

import { useEffect, useState } from "react";

import { ExportModal } from "@/components/dashboard/export-modal";
import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { useToast } from "@/components/toast-provider";
import { apiRequest } from "@/lib/auth";
import {
  fetchLeadCaptureSettings,
  fetchLeadDetail,
  listLeads,
  updateLead,
  updateLeadCaptureSettings,
  type LeadCaptureSettings,
  type LeadDetailResponse,
  type LeadSummary,
} from "@/lib/chat";

type Workspace = {
  id: string;
  name: string;
  role: string;
};

export function LeadsManager() {
  const { pushToast } = useToast();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [leads, setLeads] = useState<LeadSummary[]>([]);
  const [selectedLead, setSelectedLead] = useState<LeadDetailResponse | null>(null);
  const [notesDraft, setNotesDraft] = useState("");
  const [leadSettings, setLeadSettings] = useState<LeadCaptureSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [exportModalOpen, setExportModalOpen] = useState(false);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      setIsLoading(true);
      try {
        const workspaceList = await apiRequest<Workspace[]>("/api/v1/workspaces");
        if (!active) return;
        setWorkspaces(workspaceList);
        if (workspaceList.length) {
          setSelectedWorkspaceId((current) => current || workspaceList[0].id);
        }
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load workspaces.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) return;
    let active = true;
    async function loadLeads() {
      setIsLoading(true);
      try {
        const response = await listLeads({
          workspaceId: selectedWorkspaceId,
          status: statusFilter || undefined,
          priority: priorityFilter || undefined,
          search: search || undefined,
          dateFrom: dateFrom || undefined,
          dateTo: dateTo || undefined,
        });
        if (!active) return;
        setLeads(response.items);
        const settings = await fetchLeadCaptureSettings(selectedWorkspaceId);
        if (!active) return;
        setLeadSettings(settings);
        if (response.items.length && !selectedLead) {
          const detail = await fetchLeadDetail(selectedWorkspaceId, response.items[0].id);
          if (!active) return;
          setSelectedLead(detail);
          setNotesDraft(detail.lead.notes ?? "");
        }
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load leads.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadLeads();
    return () => {
      active = false;
    };
  }, [dateFrom, dateTo, priorityFilter, search, selectedWorkspaceId, statusFilter]);

  async function openLead(leadId: string) {
    if (!selectedWorkspaceId) return;
    const detail = await fetchLeadDetail(selectedWorkspaceId, leadId);
    setSelectedLead(detail);
    setNotesDraft(detail.lead.notes ?? "");
  }

  async function updateSelectedLead(payload: { status?: LeadSummary["status"]; priority?: LeadSummary["priority"]; notes?: string }) {
    if (!selectedLead || !selectedWorkspaceId) return;
    const updated = await updateLead(selectedWorkspaceId, selectedLead.lead.id, payload);
    setLeads((current) => current.map((lead) => (lead.id === updated.id ? updated : lead)));
    setSelectedLead((current) => (current ? { ...current, lead: updated } : current));
    pushToast({
      title: "Lead updated",
      description: "The lead record was updated successfully.",
      tone: "success",
    });
  }

  async function saveLeadSettings() {
    if (!leadSettings) return;
    const updated = await updateLeadCaptureSettings(leadSettings);
    setLeadSettings(updated);
    pushToast({
      title: "Lead settings saved",
      description: "Capture triggers and notification preferences were updated.",
      tone: "success",
    });
  }

  if (isLoading && !workspaces.length && !leads.length) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={2} />
        <LoadingGrid rows={4} />
      </main>
    );
  }

  if (error) {
    return (
      <ErrorState
        actionLabel="Retry loading"
        description={error}
        onAction={() => window.location.reload()}
        title="Leads dashboard could not be loaded"
      />
    );
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(249,115,22,0.14),transparent_35%),linear-gradient(145deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-orange-200/70">Revenue signals</p>
            <h2 className="mt-3 text-4xl font-semibold text-white">Pipeline Pulse</h2>
            <p className="mt-3 text-slate-300">
              Review captured leads, inspect full conversations, and hand qualified follow-up to a human team without slowing chat UX.
            </p>
          </div>
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
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-950"
            onClick={() => setExportModalOpen(true)}
            type="button"
          >
            Export Data
          </button>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_1fr_1.2fr_0.9fr_0.9fr]">
        <select
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
          onChange={(event) => setStatusFilter(event.target.value)}
          value={statusFilter}
        >
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="qualified">Qualified</option>
          <option value="converted">Converted</option>
          <option value="closed">Closed</option>
        </select>
        <select
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
          onChange={(event) => setPriorityFilter(event.target.value)}
          value={priorityFilter}
        >
          <option value="">All priorities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <input
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search lead, company, or message"
          value={search}
        />
        <input
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
          onChange={(event) => setDateFrom(event.target.value)}
          type="date"
          value={dateFrom}
        />
        <input
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
          onChange={(event) => setDateTo(event.target.value)}
          type="date"
          value={dateTo}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <div className="space-y-4">
          {leads.map((lead) => (
            <button
              key={lead.id}
              className="w-full rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5 text-left transition hover:border-orange-300/20"
              onClick={() => void openLead(lead.id)}
              type="button"
            >
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="text-lg font-semibold text-white">{lead.name ?? lead.email}</h3>
                <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
                  {lead.status}
                </span>
                <span className="rounded-full border border-orange-300/20 bg-orange-400/10 px-3 py-1 text-xs text-orange-100">
                  {lead.priority}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-400">{lead.company ?? "No company provided"}</p>
              <p className="mt-3 line-clamp-2 text-sm text-slate-300">{lead.message ?? "No message captured."}</p>
            </button>
          ))}
        </div>

        <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
          {selectedLead ? (
            <div className="space-y-5">
              <div>
                <h3 className="text-2xl font-semibold text-white">{selectedLead.lead.name ?? selectedLead.lead.email}</h3>
                <p className="mt-2 text-sm text-slate-400">
                  {selectedLead.lead.email} · {selectedLead.lead.company ?? "No company"} · {selectedLead.lead.tag}
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <select
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white outline-none"
                  onChange={(event) => void updateSelectedLead({ status: event.target.value as LeadSummary["status"] })}
                  value={selectedLead.lead.status}
                >
                  <option value="new">new</option>
                  <option value="contacted">contacted</option>
                  <option value="qualified">qualified</option>
                  <option value="converted">converted</option>
                  <option value="closed">closed</option>
                </select>
                <select
                  className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white outline-none"
                  onChange={(event) => void updateSelectedLead({ priority: event.target.value as LeadSummary["priority"] })}
                  value={selectedLead.lead.priority}
                >
                  <option value="high">high</option>
                  <option value="medium">medium</option>
                  <option value="low">low</option>
                </select>
              </div>

              <div>
                <p className="text-sm text-slate-400">Conversation</p>
                <div className="mt-3 max-h-80 space-y-3 overflow-y-auto rounded-3xl border border-white/10 bg-slate-950/50 p-4">
                  {selectedLead.conversation.map((message) => (
                    <div key={message.id} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                      <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{message.role}</p>
                      <p className="mt-2 text-sm text-slate-200">{message.content}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-sm text-slate-400">Notes</p>
                <textarea
                  className="mt-3 min-h-32 w-full rounded-3xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-white outline-none"
                  onChange={(event) => setNotesDraft(event.target.value)}
                  value={notesDraft}
                />
                <button
                  className="mt-3 rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-950"
                  onClick={() => void updateSelectedLead({ notes: notesDraft })}
                  type="button"
                >
                  Save notes
                </button>
              </div>
            </div>
          ) : (
            <div className="text-center text-slate-400">Select a lead to view conversation details.</div>
          )}
        </div>
      </section>

      {leadSettings ? (
        <section className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex flex-col gap-6">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-orange-200/70">Lead settings</p>
              <h3 className="mt-3 text-2xl font-semibold text-white">Capture configuration</h3>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex items-center gap-3 text-sm text-slate-300">
                <input
                  checked={leadSettings.lead_capture_enabled}
                  onChange={(event) =>
                    setLeadSettings((current) => (current ? { ...current, lead_capture_enabled: event.target.checked } : current))
                  }
                  type="checkbox"
                />
                Enable lead capture
              </label>
              <label className="flex items-center gap-3 text-sm text-slate-300">
                <input
                  checked={leadSettings.force_lead_before_chat}
                  onChange={(event) =>
                    setLeadSettings((current) => (current ? { ...current, force_lead_before_chat: event.target.checked } : current))
                  }
                  type="checkbox"
                />
                Force lead before chat
              </label>
              <label className="flex items-center gap-3 text-sm text-slate-300">
                <input
                  checked={leadSettings.lead_capture_on_first_message}
                  onChange={(event) =>
                    setLeadSettings((current) => (current ? { ...current, lead_capture_on_first_message: event.target.checked } : current))
                  }
                  type="checkbox"
                />
                Trigger on first message
              </label>
              <label className="flex items-center gap-3 text-sm text-slate-300">
                <input
                  checked={leadSettings.lead_capture_on_low_confidence}
                  onChange={(event) =>
                    setLeadSettings((current) => (current ? { ...current, lead_capture_on_low_confidence: event.target.checked } : current))
                  }
                  type="checkbox"
                />
                Trigger on low confidence
              </label>
              <label className="flex items-center gap-3 text-sm text-slate-300">
                <input
                  checked={leadSettings.schedule_call_enabled}
                  onChange={(event) =>
                    setLeadSettings((current) => (current ? { ...current, schedule_call_enabled: event.target.checked } : current))
                  }
                  type="checkbox"
                />
                Allow schedule call request
              </label>
              <label className="flex items-center gap-3 text-sm text-slate-300">
                <input
                  checked={leadSettings.lead_notifications_enabled}
                  onChange={(event) =>
                    setLeadSettings((current) => (current ? { ...current, lead_notifications_enabled: event.target.checked } : current))
                  }
                  type="checkbox"
                />
                Enable notifications
              </label>
              <input
                className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-white outline-none"
                min="1"
                onChange={(event) =>
                  setLeadSettings((current) =>
                    current ? { ...current, lead_capture_after_message_count: Number(event.target.value) || 1 } : current,
                  )
                }
                type="number"
                value={leadSettings.lead_capture_after_message_count}
              />
              <input
                className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-white outline-none"
                onChange={(event) =>
                  setLeadSettings((current) => (current ? { ...current, admin_notification_email: event.target.value } : current))
                }
                placeholder="Admin notification email"
                value={leadSettings.admin_notification_email ?? ""}
              />
              <input
                className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-white outline-none md:col-span-2"
                onChange={(event) =>
                  setLeadSettings((current) =>
                    current
                      ? {
                          ...current,
                          required_fields: event.target.value
                            .split(",")
                            .map((value) => value.trim())
                            .filter(Boolean),
                        }
                      : current,
                  )
                }
                placeholder="Required fields: name,email"
                value={leadSettings.required_fields.join(", ")}
              />
              <textarea
                className="min-h-28 rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-white outline-none md:col-span-2"
                onChange={(event) =>
                  setLeadSettings((current) => (current ? { ...current, auto_response_message: event.target.value } : current))
                }
                placeholder="Auto response message after lead submission"
                value={leadSettings.auto_response_message ?? ""}
              />
            </div>
            <div>
              <button
                className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-950"
                onClick={() => void saveLeadSettings()}
                type="button"
              >
                Save lead settings
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <ExportModal
        open={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        exportType="lead"
        workspaceId={selectedWorkspaceId}
        title="Export lead pipeline"
        description="Create a background export for filtered leads in CSV, JSON, or PDF without blocking the dashboard."
        initialFilters={{
          dateFrom,
          dateTo,
          status: statusFilter,
          priority: priorityFilter,
        }}
      />
    </main>
  );
}
