"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";

import { BookingScheduler } from "@/components/scheduling/BookingScheduler";
import { useToast } from "@/components/toast-provider";
import { cancelBooking, fetchBookingByToken, type BookingSummary } from "@/lib/scheduling";

export default function ManageBookingPage() {
  const params = useParams<{ token: string }>();
  const searchParams = useSearchParams();
  const { pushToast } = useToast();
  const [booking, setBooking] = useState<BookingSummary | null>(null);
  const [error, setError] = useState("");

  const token = params?.token ?? "";
  const action = searchParams.get("action") ?? "";

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        if (!token) {
          return;
        }
        const response = await fetchBookingByToken(token);
        if (!active) return;
        setBooking(response);
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load booking.");
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [token]);

  const visitor = useMemo(
    () =>
      booking
        ? {
            name: booking.visitor_name,
            email: booking.visitor_email,
            phone: booking.visitor_phone ?? "",
          }
        : undefined,
    [booking],
  );

  if (error) {
    return <main className="min-h-screen bg-slate-950 p-8 text-white">{error}</main>;
  }

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#02110d_0%,#041b16_40%,#020617_100%)] px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-6xl space-y-8">
        {booking ? (
          <>
            <section className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-8">
              <p className="text-xs uppercase tracking-[0.35em] text-emerald-100/70">Manage booking</p>
              <h1 className="mt-3 text-4xl font-semibold text-white">{booking.meeting_type_title}</h1>
              <p className="mt-3 text-slate-300">
                Current time: {new Date(booking.start_time_utc).toLocaleString()} · {booking.status}
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  className="rounded-full border border-rose-300/20 bg-rose-400/10 px-4 py-2 text-sm text-rose-100"
                  onClick={() =>
                    void cancelBooking({
                      workspace_id: booking.workspace_id,
                      token,
                    }).then(() =>
                      pushToast({
                        title: "Booking cancelled",
                        description: "The cancellation has been recorded and notifications can be sent.",
                        tone: "success",
                      }),
                    )
                  }
                  type="button"
                >
                  Cancel booking
                </button>
              </div>
            </section>
            {action === "reschedule" ? (
              <BookingScheduler
                chatSessionId={booking.chat_session_id}
                existingBookingId={booking.id}
                leadId={booking.lead_id}
                meetingTypeId={booking.meeting_type_id}
                rescheduleToken={token}
                title="Reschedule booking"
                visitor={visitor}
                workspaceId={booking.workspace_id}
              />
            ) : null}
          </>
        ) : (
          <section className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-8 text-white">
            Loading booking...
          </section>
        )}
      </div>
    </main>
  );
}
