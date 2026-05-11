"use client";

import { useEffect, useMemo, useState } from "react";

import { useToast } from "@/components/toast-provider";
import {
  createBooking,
  fetchBookingSlots,
  listMeetingTypes,
  rescheduleBooking,
  type BookingSummary,
  type MeetingTypeSummary,
} from "@/lib/scheduling";

type BookingSchedulerProps = {
  workspaceId: string;
  initialMeetingTypes?: MeetingTypeSummary[];
  meetingTypeId?: string | null;
  leadId?: string | null;
  chatSessionId?: string | null;
  visitor?: {
    name?: string;
    email?: string;
    phone?: string;
  };
  existingBookingId?: string | null;
  rescheduleToken?: string | null;
  title?: string;
  onBooked?: (booking: BookingSummary) => void;
};

export function BookingScheduler({
  workspaceId,
  initialMeetingTypes,
  meetingTypeId,
  leadId,
  chatSessionId,
  visitor,
  existingBookingId,
  rescheduleToken,
  title = "Book time with the team",
  onBooked,
}: BookingSchedulerProps) {
  const { pushToast } = useToast();
  const [meetingTypes, setMeetingTypes] = useState<MeetingTypeSummary[]>(initialMeetingTypes ?? []);
  const [selectedMeetingTypeId, setSelectedMeetingTypeId] = useState<string>(meetingTypeId ?? initialMeetingTypes?.[0]?.id ?? "");
  const [timezone, setTimezone] = useState("UTC");
  const [dateAnchor, setDateAnchor] = useState(() => new Date().toISOString().slice(0, 10));
  const [slots, setSlots] = useState<
    Array<{
      start_time_utc: string;
      end_time_utc: string;
      display_time: string;
    }>
  >([]);
  const [selectedSlot, setSelectedSlot] = useState<string>("");
  const [name, setName] = useState(visitor?.name ?? "");
  const [email, setEmail] = useState(visitor?.email ?? "");
  const [phone, setPhone] = useState(visitor?.phone ?? "");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const selectedMeetingType = useMemo(
    () => meetingTypes.find((item) => item.id === selectedMeetingTypeId) ?? null,
    [meetingTypes, selectedMeetingTypeId],
  );

  useEffect(() => {
    setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  }, []);

  useEffect(() => {
    if (initialMeetingTypes?.length) {
      return;
    }
    let active = true;
    async function loadMeetingTypes() {
      try {
        const response = await listMeetingTypes(workspaceId);
        if (!active) return;
        setMeetingTypes(response.items);
        setSelectedMeetingTypeId((current) => current || response.items[0]?.id || "");
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load meeting types.");
      }
    }
    void loadMeetingTypes();
    return () => {
      active = false;
    };
  }, [initialMeetingTypes, workspaceId]);

  useEffect(() => {
    if (!selectedMeetingTypeId || !timezone) return;
    let active = true;
    async function loadSlots() {
      setIsLoading(true);
      setError("");
      try {
        const startDate = new Date(`${dateAnchor}T00:00:00`).toISOString();
        const endDate = new Date(`${dateAnchor}T23:59:59`).toISOString();
        const response = await fetchBookingSlots({
          workspace_id: workspaceId,
          meeting_type_id: selectedMeetingTypeId,
          timezone,
          start_date: startDate,
          end_date: endDate,
          lead_id: leadId ?? null,
          chat_session_id: chatSessionId ?? null,
          reschedule_booking_id: existingBookingId ?? null,
        });
        if (!active) return;
        setSlots(response.slots);
        setSelectedSlot((current) => current && response.slots.some((slot) => slot.start_time_utc === current) ? current : response.slots[0]?.start_time_utc ?? "");
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load available slots.");
        setSlots([]);
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadSlots();
    return () => {
      active = false;
    };
  }, [chatSessionId, dateAnchor, leadId, selectedMeetingTypeId, timezone, workspaceId]);

  async function handleBook() {
    if (!selectedMeetingTypeId || !selectedSlot || !name.trim() || !email.trim()) {
      setError("Choose a meeting type and slot, then provide your name and email.");
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      const booking = existingBookingId || rescheduleToken
        ? await rescheduleBooking({
            workspace_id: workspaceId,
            booking_id: existingBookingId ?? null,
            token: rescheduleToken ?? null,
            start_time_utc: selectedSlot,
            timezone,
          })
        : await createBooking({
            workspace_id: workspaceId,
            meeting_type_id: selectedMeetingTypeId,
            lead_id: leadId ?? null,
            chat_session_id: chatSessionId ?? null,
            visitor_name: name.trim(),
            visitor_email: email.trim(),
            visitor_phone: phone.trim() || null,
            start_time_utc: selectedSlot,
            timezone,
          });
      pushToast({
        title: existingBookingId || rescheduleToken ? "Booking rescheduled" : "Booking confirmed",
        description: `${booking.meeting_type_title} is scheduled and the confirmation details are ready.`,
        tone: "success",
      });
      onBooked?.(booking);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Could not create booking.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="rounded-[1.8rem] border border-emerald-300/20 bg-emerald-400/10 p-5 text-white">
      <div className="flex flex-col gap-2">
        <p className="text-xs uppercase tracking-[0.3em] text-emerald-100/70">Scheduling</p>
        <h3 className="text-2xl font-semibold">{title}</h3>
        <p className="text-sm text-emerald-50/80">
          Pick a meeting type, choose a real available slot, and confirm the booking without leaving the product.
        </p>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_0.9fr]">
        <div className="space-y-4">
          <select
            className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
            onChange={(event) => setSelectedMeetingTypeId(event.target.value)}
            value={selectedMeetingTypeId}
          >
            {meetingTypes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title} · {item.duration_minutes} min
              </option>
            ))}
          </select>
          <div className="grid gap-4 md:grid-cols-2">
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
              onChange={(event) => setDateAnchor(event.target.value)}
              type="date"
              value={dateAnchor}
            />
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
              onChange={(event) => setTimezone(event.target.value)}
              placeholder="Timezone"
              value={timezone}
            />
          </div>
          {selectedMeetingType ? (
            <div className="rounded-3xl border border-white/10 bg-slate-950/35 p-4">
              <p className="text-sm font-medium text-white">{selectedMeetingType.title}</p>
              <p className="mt-2 text-sm text-slate-300">{selectedMeetingType.description ?? "A human teammate will join this conversation."}</p>
              <p className="mt-3 text-xs uppercase tracking-[0.25em] text-slate-400">
                {selectedMeetingType.duration_minutes} min · {selectedMeetingType.location_type.replaceAll("_", " ")}
              </p>
            </div>
          ) : null}
          <div className="space-y-3">
            <p className="text-sm font-medium text-white">Available slots</p>
            {isLoading ? <p className="text-sm text-slate-300">Loading real availability...</p> : null}
            {!isLoading && !slots.length ? (
              <p className="rounded-2xl border border-white/10 bg-slate-950/35 px-4 py-3 text-sm text-slate-300">
                No slots are open for this date. Try another day or timezone.
              </p>
            ) : null}
            <div className="grid gap-3 md:grid-cols-2">
              {slots.map((slot) => (
                <button
                  key={slot.start_time_utc}
                  className={`rounded-2xl border px-4 py-3 text-left text-sm transition ${
                    selectedSlot === slot.start_time_utc
                      ? "border-white bg-white text-slate-950"
                      : "border-white/10 bg-slate-950/35 text-slate-100 hover:border-emerald-200/40"
                  }`}
                  onClick={() => setSelectedSlot(slot.start_time_utc)}
                  type="button"
                >
                  {slot.display_time}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4 rounded-[1.6rem] border border-white/10 bg-slate-950/35 p-5">
          <div>
            <p className="text-sm font-medium text-white">Contact details</p>
            <p className="mt-1 text-sm text-slate-300">
              We use these details for confirmations, reminders, and reschedule links.
            </p>
          </div>
          <input
            className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
            onChange={(event) => setName(event.target.value)}
            placeholder="Name"
            value={name}
          />
          <input
            className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Email"
            value={email}
          />
          <input
            className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
            onChange={(event) => setPhone(event.target.value)}
            placeholder="Phone"
            value={phone}
          />
          {selectedSlot ? (
            <div className="rounded-3xl border border-emerald-200/20 bg-emerald-300/10 p-4 text-sm text-emerald-50">
              Selected slot: {slots.find((slot) => slot.start_time_utc === selectedSlot)?.display_time}
            </div>
          ) : null}
          {error ? <p className="text-sm text-rose-200">{error}</p> : null}
          <button
            className="w-full rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60"
            disabled={isSubmitting || !selectedSlot}
            onClick={() => void handleBook()}
            type="button"
          >
            {isSubmitting ? "Confirming..." : "Confirm booking"}
          </button>
        </div>
      </div>
    </section>
  );
}
