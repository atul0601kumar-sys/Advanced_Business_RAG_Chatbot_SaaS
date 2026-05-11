import { BookingScheduler } from "@/components/scheduling/BookingScheduler";
import { fetchPublicBookingWorkspace } from "@/lib/scheduling";

type PublicBookingPageProps = {
  params: Promise<{ workspaceSlug: string }>;
  searchParams: Promise<{ meeting?: string }>;
};

export default async function PublicBookingPage({ params, searchParams }: PublicBookingPageProps) {
  const { workspaceSlug } = await params;
  const { meeting } = await searchParams;
  const workspace = await fetchPublicBookingWorkspace(workspaceSlug);
  const initialMeeting = workspace.meeting_types.find((item) => item.slug === meeting) ?? workspace.meeting_types[0] ?? null;

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#02110d_0%,#041b16_40%,#020617_100%)] px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-6xl space-y-8">
        <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.16),transparent_30%),linear-gradient(145deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
          <p className="text-xs uppercase tracking-[0.35em] text-emerald-100/70">Public booking</p>
          <h1 className="mt-3 text-4xl font-semibold text-white">{workspace.workspace_name}</h1>
          <p className="mt-3 max-w-2xl text-slate-300">
            Choose the right meeting type, see live availability in your timezone, and confirm instantly.
          </p>
        </section>
        <BookingScheduler
          initialMeetingTypes={workspace.meeting_types}
          meetingTypeId={initialMeeting?.id ?? null}
          title="Schedule a call"
          workspaceId={workspace.workspace_id}
        />
      </div>
    </main>
  );
}
