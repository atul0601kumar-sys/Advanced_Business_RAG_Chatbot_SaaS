"use client";

import { useEffect, useMemo, useState } from "react";

import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import { useToast } from "@/components/toast-provider";
import { apiRequest } from "@/lib/auth";
import { fetchWorkspaceMembers, type WorkspaceMemberSummary } from "@/lib/team";
import {
  cancelBooking,
  connectCalendar,
  createBlackout,
  createMeetingType,
  deleteBlackout,
  deleteMeetingType,
  disconnectCalendar,
  fetchAvailability,
  fetchCalendarStatus,
  listBlackouts,
  listBookings,
  listMeetingTypes,
  setAvailability,
  type AvailabilityResponse,
  type BlackoutDateSummary,
  type BookingSummary,
  type CalendarConnectionSummary,
  type MeetingTypeSummary,
} from "@/lib/scheduling";

type Workspace = {
  id: string;
  name: string;
  role: string;
  slug: string;
};

type TabKey = "connections" | "meeting-types" | "availability" | "bookings" | "blackouts" | "settings";

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "connections", label: "Calendar connection" },
  { key: "meeting-types", label: "Meeting types" },
  { key: "availability", label: "Availability" },
  { key: "bookings", label: "Bookings" },
  { key: "blackouts", label: "Blackout dates" },
  { key: "settings", label: "Settings" },
];

export function SchedulingManager() {
  const { pushToast } = useToast();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [members, setMembers] = useState<WorkspaceMemberSummary[]>([]);
  const [connections, setConnections] = useState<CalendarConnectionSummary[]>([]);
  const [meetingTypes, setMeetingTypes] = useState<MeetingTypeSummary[]>([]);
  const [availability, setAvailabilityState] = useState<AvailabilityResponse | null>(null);
  const [bookings, setBookings] = useState<BookingSummary[]>([]);
  const [blackouts, setBlackouts] = useState<BlackoutDateSummary[]>([]);
  const [activeTab, setActiveTab] = useState<TabKey>("connections");
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [assignedFilter, setAssignedFilter] = useState("");
  const [provider, setProvider] = useState<"calcom" | "external_link">("calcom");
  const [providerSecret, setProviderSecret] = useState("");
  const [weeklyRules, setWeeklyRules] = useState([
    { weekday: 0, start_time: "09:00", end_time: "17:00", is_enabled: true },
    { weekday: 1, start_time: "09:00", end_time: "17:00", is_enabled: true },
    { weekday: 2, start_time: "09:00", end_time: "17:00", is_enabled: true },
    { weekday: 3, start_time: "09:00", end_time: "17:00", is_enabled: true },
    { weekday: 4, start_time: "09:00", end_time: "17:00", is_enabled: true },
  ]);
  const [timezone, setTimezone] = useState("UTC");
  const [meetingTitle, setMeetingTitle] = useState("");
  const [meetingDescription, setMeetingDescription] = useState("");
  const [meetingDuration, setMeetingDuration] = useState("30");
  const [meetingLocationType, setMeetingLocationType] = useState("manual");
  const [meetingAssignedUserId, setMeetingAssignedUserId] = useState("");
  const [meetingAssignmentMode, setMeetingAssignmentMode] = useState("specific");
  const [meetingLocationValue, setMeetingLocationValue] = useState("");
  const [blackoutTitle, setBlackoutTitle] = useState("");
  const [blackoutStart, setBlackoutStart] = useState("");
  const [blackoutEnd, setBlackoutEnd] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null,
    [selectedWorkspaceId, workspaces],
  );

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      try {
        const workspaceList = await apiRequest<Workspace[]>("/api/v1/workspaces");
        if (!active) return;
        setWorkspaces(workspaceList);
        setSelectedWorkspaceId(workspaceList[0]?.id ?? "");
        setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load workspaces.");
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
    async function loadWorkspaceData() {
      setIsLoading(true);
      setError("");
      try {
        const [memberList, connectionStatus, meetingTypeList, availabilityResponse, bookingList, blackoutList] =
          await Promise.all([
            fetchWorkspaceMembers(selectedWorkspaceId),
            fetchCalendarStatus(selectedWorkspaceId),
            listMeetingTypes(selectedWorkspaceId),
            fetchAvailability(selectedWorkspaceId),
            listBookings({
              workspace_id: selectedWorkspaceId,
              status: statusFilter || undefined,
              date_from: dateFilter ? new Date(`${dateFilter}T00:00:00`).toISOString() : undefined,
              date_to: dateFilter ? new Date(`${dateFilter}T23:59:59`).toISOString() : undefined,
              assigned_user_id: assignedFilter || undefined,
            }),
            listBlackouts(selectedWorkspaceId),
          ]);
        if (!active) return;
        setMembers(memberList);
        setConnections(connectionStatus.items);
        setMeetingTypes(meetingTypeList.items);
        setAvailabilityState(availabilityResponse);
        setWeeklyRules(availabilityResponse.rules);
        setTimezone(availabilityResponse.settings.timezone);
        setBookings(bookingList.items);
        setBlackouts(blackoutList);
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load scheduling data.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadWorkspaceData();
    return () => {
      active = false;
    };
  }, [assignedFilter, dateFilter, selectedWorkspaceId, statusFilter]);

  async function handleConnectCalendar() {
    if (!selectedWorkspaceId || !providerSecret.trim()) return;
    await connectCalendar({
      workspace_id: selectedWorkspaceId,
      provider,
      api_key: provider === "calcom" ? providerSecret.trim() : undefined,
      external_booking_url: provider === "external_link" ? providerSecret.trim() : undefined,
    });
    pushToast({ title: "Calendar connected", description: "Scheduling provider credentials were saved securely.", tone: "success" });
    const status = await fetchCalendarStatus(selectedWorkspaceId);
    setConnections(status.items);
    setProviderSecret("");
  }

  async function handleSaveMeetingType() {
    if (!selectedWorkspaceId || !meetingTitle.trim()) return;
    await createMeetingType({
      workspace_id: selectedWorkspaceId,
      title: meetingTitle.trim(),
      description: meetingDescription.trim() || null,
      duration_minutes: Number(meetingDuration),
      location_type: meetingLocationType,
      assigned_user_id: meetingAssignedUserId || null,
      assignment_mode: meetingAssignmentMode,
      provider_preference: provider,
      external_location_url: meetingLocationType === "external_url" ? meetingLocationValue.trim() || null : null,
      manual_location_text: meetingLocationType !== "external_url" ? meetingLocationValue.trim() || null : null,
    });
    pushToast({ title: "Meeting type created", description: "The booking surface is live for this meeting type.", tone: "success" });
    setMeetingTitle("");
    setMeetingDescription("");
    setMeetingLocationValue("");
    const response = await listMeetingTypes(selectedWorkspaceId);
    setMeetingTypes(response.items);
  }

  async function handleSaveAvailability() {
    if (!selectedWorkspaceId) return;
    const response = await setAvailability({
      workspace_id: selectedWorkspaceId,
      rules: weeklyRules,
      settings: {
        timezone,
        buffer_before_minutes: availability?.settings.buffer_before_minutes ?? 15,
        buffer_after_minutes: availability?.settings.buffer_after_minutes ?? 15,
        duration_options: availability?.settings.duration_options ?? [15, 30, 45, 60],
        max_bookings_per_day: availability?.settings.max_bookings_per_day ?? 12,
        minimum_notice_minutes: availability?.settings.minimum_notice_minutes ?? 60,
        future_booking_window_days: availability?.settings.future_booking_window_days ?? 30,
        fallback_owner_user_id: availability?.settings.fallback_owner_user_id ?? null,
        reminder_in_app_enabled: availability?.settings.reminder_in_app_enabled ?? false,
      },
    });
    setAvailabilityState(response);
    pushToast({ title: "Availability saved", description: "The slot engine will use the updated business hours immediately.", tone: "success" });
  }

  async function handleCreateBlackout() {
    if (!selectedWorkspaceId || !blackoutStart || !blackoutEnd) return;
    await createBlackout({
      workspace_id: selectedWorkspaceId,
      title: blackoutTitle.trim() || null,
      start_time: new Date(blackoutStart).toISOString(),
      end_time: new Date(blackoutEnd).toISOString(),
      timezone,
    });
    pushToast({ title: "Blackout date added", description: "Those times are now blocked from booking.", tone: "success" });
    setBlackoutTitle("");
    setBlackoutStart("");
    setBlackoutEnd("");
    setBlackouts(await listBlackouts(selectedWorkspaceId));
  }

  if (isLoading && !workspaces.length) {
    return <LoadingGrid rows={4} />;
  }

  if (error) {
    return (
      <ErrorState
        title="Scheduling settings could not be loaded"
        description={error}
        actionLabel="Retry loading"
        onAction={() => window.location.reload()}
      />
    );
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.16),transparent_35%),linear-gradient(145deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-emerald-200/70">Human scheduling</p>
            <h2 className="mt-3 text-4xl font-semibold text-white">Appointment Engine</h2>
            <p className="mt-3 max-w-3xl text-slate-300">
              Configure provider connections, meeting types, working hours, blackout dates, and live bookings from one scheduling console.
            </p>
          </div>
          <select
            className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none"
            onChange={(event) => setSelectedWorkspaceId(event.target.value)}
            value={selectedWorkspaceId}
          >
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name} · {workspace.role}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="flex flex-wrap gap-3">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`rounded-full px-4 py-2 text-sm transition ${
              activeTab === tab.key ? "bg-white text-slate-950" : "border border-white/10 bg-white/5 text-slate-200"
            }`}
            onClick={() => setActiveTab(tab.key)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </section>

      {activeTab === "connections" ? (
        <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
            <h3 className="text-2xl font-semibold text-white">Connect provider</h3>
            <div className="mt-5 space-y-4">
              <select className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" value={provider} onChange={(event) => setProvider(event.target.value as "calcom" | "external_link")}>
                <option value="calcom">Cal.com API</option>
                <option value="external_link">External booking link</option>
              </select>
              <input className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" placeholder={provider === "calcom" ? "Cal.com API key" : "External booking URL"} value={providerSecret} onChange={(event) => setProviderSecret(event.target.value)} />
              <button className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleConnectCalendar()} type="button">
                Save connection
              </button>
            </div>
          </div>
          <div className="space-y-4">
            {connections.map((connection) => (
              <article key={connection.id} className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h4 className="text-lg font-semibold text-white">{connection.provider}</h4>
                    <p className="mt-2 text-sm text-slate-400">{connection.external_account_email ?? "Connected for workspace-level scheduling"}</p>
                  </div>
                  <button className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300" onClick={() => void disconnectCalendar({ workspace_id: selectedWorkspaceId, provider: connection.provider }).then(async () => setConnections((await fetchCalendarStatus(selectedWorkspaceId)).items))} type="button">
                    Disconnect
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "meeting-types" ? (
        <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
            <h3 className="text-2xl font-semibold text-white">Create meeting type</h3>
            <div className="mt-5 space-y-4">
              <input className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" placeholder="Sales demo" value={meetingTitle} onChange={(event) => setMeetingTitle(event.target.value)} />
              <textarea className="min-h-28 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" placeholder="Describe this meeting type" value={meetingDescription} onChange={(event) => setMeetingDescription(event.target.value)} />
              <div className="grid gap-4 md:grid-cols-2">
                <select className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" value={meetingDuration} onChange={(event) => setMeetingDuration(event.target.value)}>
                  {[15, 30, 45, 60].map((duration) => <option key={duration} value={duration}>{duration} minutes</option>)}
                </select>
                <select className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" value={meetingLocationType} onChange={(event) => setMeetingLocationType(event.target.value)}>
                  <option value="manual">Manual link/text</option>
                  <option value="external_url">External meeting URL</option>
                  <option value="phone">Phone</option>
                </select>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <select className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" value={meetingAssignmentMode} onChange={(event) => setMeetingAssignmentMode(event.target.value)}>
                  <option value="specific">Specific assignee</option>
                  <option value="round_robin">Round robin</option>
                </select>
                <select className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" value={meetingAssignedUserId} onChange={(event) => setMeetingAssignedUserId(event.target.value)}>
                  <option value="">Auto / fallback</option>
                  {members.map((member) => <option key={member.user_id} value={member.user_id}>{member.full_name}</option>)}
                </select>
              </div>
              <input className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" placeholder={meetingLocationType === "external_url" ? "https://meet.example.com/demo" : "Manual location text"} value={meetingLocationValue} onChange={(event) => setMeetingLocationValue(event.target.value)} />
              <button className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleSaveMeetingType()} type="button">Save meeting type</button>
            </div>
          </div>
          <div className="space-y-4">
            {meetingTypes.map((meetingType) => (
              <article key={meetingType.id} className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h4 className="text-lg font-semibold text-white">{meetingType.title}</h4>
                    <p className="mt-2 text-sm text-slate-300">{meetingType.description ?? "No description."}</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.25em] text-slate-500">{meetingType.duration_minutes} min · {meetingType.assignment_mode} · {meetingType.location_type}</p>
                    <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-xs text-slate-300">{meetingType.booking_link}</div>
                  </div>
                  <button className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300" onClick={() => void deleteMeetingType(selectedWorkspaceId, meetingType.id).then(async () => setMeetingTypes((await listMeetingTypes(selectedWorkspaceId)).items))} type="button">Delete</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "availability" ? (
        <section className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-2xl font-semibold text-white">Weekly availability</h3>
              <p className="mt-2 text-sm text-slate-300">Slots are stored in UTC but managed in your admin timezone.</p>
            </div>
            <input className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" value={timezone} onChange={(event) => setTimezone(event.target.value)} />
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {weeklyRules.map((rule, index) => (
              <div key={`${rule.weekday}-${index}`} className="rounded-3xl border border-white/10 bg-slate-950/40 p-4">
                <p className="text-sm font-medium text-white">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][rule.weekday]}</p>
                <div className="mt-3 space-y-3">
                  <input className="w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none" value={rule.start_time} onChange={(event) => setWeeklyRules((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, start_time: event.target.value } : item))} />
                  <input className="w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none" value={rule.end_time} onChange={(event) => setWeeklyRules((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, end_time: event.target.value } : item))} />
                </div>
              </div>
            ))}
          </div>
          <button className="mt-6 rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleSaveAvailability()} type="button">Save availability</button>
        </section>
      ) : null}

      {activeTab === "bookings" ? (
        <section className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <select className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All statuses</option>
              {["pending", "confirmed", "cancelled", "rescheduled", "completed", "no_show"].map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
            <input className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" type="date" value={dateFilter} onChange={(event) => setDateFilter(event.target.value)} />
            <select className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" value={assignedFilter} onChange={(event) => setAssignedFilter(event.target.value)}>
              <option value="">All team members</option>
              {members.map((member) => <option key={member.user_id} value={member.user_id}>{member.full_name}</option>)}
            </select>
          </div>
          <div className="space-y-4">
            {bookings.map((booking) => (
              <article key={booking.id} className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                  <div>
                    <h4 className="text-lg font-semibold text-white">{booking.meeting_type_title}</h4>
                    <p className="mt-2 text-sm text-slate-300">{booking.visitor_name} · {booking.visitor_email} · {new Date(booking.start_time_utc).toLocaleString()}</p>
                    <p className="mt-2 text-xs uppercase tracking-[0.25em] text-slate-500">{booking.status} · {booking.assigned_user_name ?? "Unassigned"} · {booking.provider}</p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300" onClick={() => navigator.clipboard.writeText(booking.management_url)} type="button">Copy link</button>
                    <button className="rounded-full border border-rose-300/20 bg-rose-400/10 px-4 py-2 text-sm text-rose-100" onClick={() => void cancelBooking({ workspace_id: selectedWorkspaceId, booking_id: booking.id }).then(async () => setBookings((await listBookings({ workspace_id: selectedWorkspaceId })).items))} type="button">Cancel</button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "blackouts" ? (
        <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
            <h3 className="text-2xl font-semibold text-white">Create blackout</h3>
            <div className="mt-5 space-y-4">
              <input className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" placeholder="Holiday, offsite, holiday cover..." value={blackoutTitle} onChange={(event) => setBlackoutTitle(event.target.value)} />
              <input className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" type="datetime-local" value={blackoutStart} onChange={(event) => setBlackoutStart(event.target.value)} />
              <input className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none" type="datetime-local" value={blackoutEnd} onChange={(event) => setBlackoutEnd(event.target.value)} />
              <button className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleCreateBlackout()} type="button">Save blackout</button>
            </div>
          </div>
          <div className="space-y-4">
            {blackouts.map((blackout) => (
              <article key={blackout.id} className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h4 className="text-lg font-semibold text-white">{blackout.title ?? "Blocked time"}</h4>
                    <p className="mt-2 text-sm text-slate-300">{new Date(blackout.start_time_utc).toLocaleString()} → {new Date(blackout.end_time_utc).toLocaleString()}</p>
                  </div>
                  <button className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300" onClick={() => void deleteBlackout(selectedWorkspaceId, blackout.id).then(async () => setBlackouts(await listBlackouts(selectedWorkspaceId)))} type="button">Delete</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "settings" ? (
        <section className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] p-6">
          <h3 className="text-2xl font-semibold text-white">Scheduling links</h3>
          <p className="mt-3 text-sm text-slate-300">
            Public booking page: {selectedWorkspace ? `${window.location.origin}/book/${selectedWorkspace.slug}` : "Select a workspace"}
          </p>
        </section>
      ) : null}
    </main>
  );
}
