import { apiRequest } from "@/lib/auth";

export type CalendarProvider = "google" | "outlook" | "calcom" | "external_link";
export type BookingStatus =
  | "pending"
  | "confirmed"
  | "cancelled"
  | "rescheduled"
  | "completed"
  | "no_show";

export type CalendarConnectionSummary = {
  id: string;
  workspace_id: string;
  user_id: string | null;
  provider: CalendarProvider;
  status: string;
  external_account_id: string | null;
  external_account_email: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type MeetingTypeSummary = {
  id: string;
  workspace_id: string;
  title: string;
  slug: string;
  description: string | null;
  duration_minutes: number;
  location_type: "google_meet" | "external_url" | "manual" | "phone" | "in_person";
  assigned_user_id: string | null;
  assignment_mode: "specific" | "round_robin";
  provider_preference: CalendarProvider | null;
  external_location_url: string | null;
  manual_location_text: string | null;
  booking_link: string;
  availability_rules: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AvailabilityRule = {
  weekday: number;
  start_time: string;
  end_time: string;
  is_enabled: boolean;
};

export type AvailabilitySettings = {
  timezone: string;
  buffer_before_minutes: number;
  buffer_after_minutes: number;
  duration_options: number[];
  max_bookings_per_day: number;
  minimum_notice_minutes: number;
  future_booking_window_days: number;
  fallback_owner_user_id: string | null;
  reminder_in_app_enabled: boolean;
};

export type AvailabilityResponse = {
  workspace_id: string;
  meeting_type_id: string | null;
  user_id: string | null;
  rules: AvailabilityRule[];
  settings: AvailabilitySettings;
};

export type BlackoutDateSummary = {
  id: string;
  workspace_id: string;
  meeting_type_id: string | null;
  user_id: string | null;
  title: string | null;
  reason: string | null;
  start_time_utc: string;
  end_time_utc: string;
  timezone: string;
  created_at: string;
};

export type AvailableSlot = {
  start_time_utc: string;
  end_time_utc: string;
  display_time: string;
  timezone: string;
  provider: string;
  assigned_user_id: string | null;
};

export type BookingSummary = {
  id: string;
  workspace_id: string;
  lead_id: string | null;
  chat_session_id: string | null;
  meeting_type_id: string;
  meeting_type_title: string;
  assigned_user_id: string | null;
  assigned_user_name: string | null;
  visitor_name: string;
  visitor_email: string;
  visitor_phone: string | null;
  start_time_utc: string;
  end_time_utc: string;
  timezone: string;
  status: BookingStatus;
  provider: string;
  external_event_id: string | null;
  meeting_link: string | null;
  management_url: string;
  public_reschedule_url: string;
  public_cancel_url: string;
  attendees: Array<{
    id: string;
    name: string;
    email: string;
    phone: string | null;
    timezone: string | null;
    is_primary: boolean;
  }>;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type PublicBookingWorkspaceResponse = {
  workspace_id: string;
  workspace_name: string;
  workspace_slug: string;
  admin_timezone: string;
  meeting_types: MeetingTypeSummary[];
};

export async function fetchCalendarStatus(workspaceId: string) {
  return apiRequest<{ workspace_id: string; items: CalendarConnectionSummary[] }>(
    `/api/v1/calendar/status?workspace_id=${encodeURIComponent(workspaceId)}`,
  );
}

export async function connectCalendar(payload: {
  workspace_id: string;
  provider: CalendarProvider;
  user_id?: string | null;
  api_key?: string;
  external_booking_url?: string;
  external_account_email?: string;
}) {
  return apiRequest<CalendarConnectionSummary>("/api/v1/calendar/connect", {
    method: "POST",
    json: payload,
  });
}

export async function disconnectCalendar(payload: {
  workspace_id: string;
  provider: CalendarProvider;
  user_id?: string | null;
}) {
  return apiRequest<{ message: string }>("/api/v1/calendar/disconnect", {
    method: "DELETE",
    json: payload,
  });
}

export async function listMeetingTypes(workspaceId: string) {
  return apiRequest<{ items: MeetingTypeSummary[] }>(
    `/api/v1/meeting-types/list?workspace_id=${encodeURIComponent(workspaceId)}`,
  );
}

export async function createMeetingType(payload: Record<string, unknown>) {
  return apiRequest<MeetingTypeSummary>("/api/v1/meeting-types/create", {
    method: "POST",
    json: payload,
  });
}

export async function updateMeetingType(id: string, payload: Record<string, unknown>) {
  return apiRequest<MeetingTypeSummary>(`/api/v1/meeting-types/${encodeURIComponent(id)}`, {
    method: "PUT",
    json: payload,
  });
}

export async function deleteMeetingType(workspaceId: string, id: string) {
  return apiRequest<{ message: string }>(
    `/api/v1/meeting-types/${encodeURIComponent(id)}?workspace_id=${encodeURIComponent(workspaceId)}`,
    { method: "DELETE" },
  );
}

export async function fetchAvailability(workspaceId: string) {
  return apiRequest<AvailabilityResponse>(
    `/api/v1/availability/get?workspace_id=${encodeURIComponent(workspaceId)}`,
  );
}

export async function setAvailability(payload: Record<string, unknown>) {
  return apiRequest<AvailabilityResponse>("/api/v1/availability/set", {
    method: "POST",
    json: payload,
  });
}

export async function listBlackouts(workspaceId: string) {
  return apiRequest<BlackoutDateSummary[]>(
    `/api/v1/availability/blackout/list?workspace_id=${encodeURIComponent(workspaceId)}`,
  );
}

export async function createBlackout(payload: Record<string, unknown>) {
  return apiRequest<BlackoutDateSummary>("/api/v1/availability/blackout", {
    method: "POST",
    json: payload,
  });
}

export async function deleteBlackout(workspaceId: string, blackoutId: string) {
  return apiRequest<{ message: string }>(
    `/api/v1/availability/blackout/${encodeURIComponent(blackoutId)}?workspace_id=${encodeURIComponent(workspaceId)}`,
    { method: "DELETE" },
  );
}

export async function fetchBookingSlots(params: {
  workspace_id: string;
  meeting_type_id: string;
  timezone: string;
  start_date?: string;
  end_date?: string;
  lead_id?: string | null;
  chat_session_id?: string | null;
  reschedule_booking_id?: string | null;
}) {
  const query = new URLSearchParams({
    workspace_id: params.workspace_id,
    meeting_type_id: params.meeting_type_id,
    timezone: params.timezone,
  });
  if (params.start_date) query.set("start_date", params.start_date);
  if (params.end_date) query.set("end_date", params.end_date);
  if (params.lead_id) query.set("lead_id", params.lead_id);
  if (params.chat_session_id) query.set("chat_session_id", params.chat_session_id);
  if (params.reschedule_booking_id) query.set("reschedule_booking_id", params.reschedule_booking_id);
  return apiRequest<{ workspace_id: string; meeting_type_id: string; timezone: string; slots: AvailableSlot[] }>(
    `/api/v1/booking/slots?${query.toString()}`,
  );
}

export async function createBooking(payload: Record<string, unknown>) {
  return apiRequest<BookingSummary>("/api/v1/booking/create", {
    method: "POST",
    json: payload,
  });
}

export async function rescheduleBooking(payload: Record<string, unknown>) {
  return apiRequest<BookingSummary>("/api/v1/booking/reschedule", {
    method: "POST",
    json: payload,
  });
}

export async function cancelBooking(payload: Record<string, unknown>) {
  return apiRequest<{ message: string }>("/api/v1/booking/cancel", {
    method: "POST",
    json: payload,
  });
}

export async function listBookings(params: {
  workspace_id: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  assigned_user_id?: string;
}) {
  const query = new URLSearchParams({ workspace_id: params.workspace_id });
  if (params.status) query.set("status", params.status);
  if (params.date_from) query.set("date_from", params.date_from);
  if (params.date_to) query.set("date_to", params.date_to);
  if (params.assigned_user_id) query.set("assigned_user_id", params.assigned_user_id);
  return apiRequest<{ items: BookingSummary[]; total: number }>(`/api/v1/booking/list?${query.toString()}`);
}

export async function fetchBooking(workspaceId: string, bookingId: string, token?: string) {
  const query = new URLSearchParams({ workspace_id: workspaceId });
  if (token) query.set("token", token);
  return apiRequest<BookingSummary>(`/api/v1/booking/${encodeURIComponent(bookingId)}?${query.toString()}`);
}

export async function fetchBookingByToken(token: string) {
  return apiRequest<BookingSummary>(`/api/v1/booking/manage/${encodeURIComponent(token)}`);
}

export async function fetchPublicBookingWorkspace(workspaceSlug: string) {
  return apiRequest<PublicBookingWorkspaceResponse>(
    `/api/v1/booking/public/${encodeURIComponent(workspaceSlug)}`,
  );
}
