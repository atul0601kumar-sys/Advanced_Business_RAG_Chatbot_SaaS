"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ExportModal } from "@/components/dashboard/export-modal";
import { ErrorState, LoadingGrid } from "@/components/dashboard/page-states";
import {
  BarChartCard,
  ChartPanel,
  DonutChartCard,
  LineChartCard,
} from "@/components/analytics/chart-kit";
import {
  fetchAnalyticsOverview,
  fetchChatAnalytics,
  fetchFeedbackAnalytics,
  fetchLeadAnalytics,
  fetchPerformanceAnalytics,
  fetchQueryAnalytics,
  fetchWorkspaceDocuments,
  fetchWorkspaceMembers,
  fetchWorkspaces,
  type AnalyticsOverviewResponse,
  type AnalyticsView,
  type BreakdownItem,
  type ChatAnalyticsResponse,
  type FeedbackAnalyticsResponse,
  type LeadAnalyticsResponse,
  type PerformanceAnalyticsResponse,
  type QueryAnalyticsResponse,
  type WorkspaceMemberSummary,
  type WorkspaceSummary,
} from "@/lib/analytics";

type AnalyticsDashboardProps = {
  view: AnalyticsView;
};

type DashboardState = {
  overview: AnalyticsOverviewResponse | null;
  chats: ChatAnalyticsResponse | null;
  leads: LeadAnalyticsResponse | null;
  performance: PerformanceAnalyticsResponse | null;
  queries: QueryAnalyticsResponse | null;
  feedback: FeedbackAnalyticsResponse | null;
};

const navItems: Array<{ href: string; label: string; view: AnalyticsView }> = [
  { href: "/dashboard/analytics", label: "Overview", view: "overview" },
  { href: "/dashboard/analytics/chats", label: "Chats", view: "chats" },
  { href: "/dashboard/analytics/leads", label: "Leads", view: "leads" },
  { href: "/dashboard/analytics/performance", label: "AI Performance", view: "performance" },
  { href: "/dashboard/analytics/queries", label: "Query Insights", view: "queries" },
];

export function AnalyticsDashboard({ view }: AnalyticsDashboardProps) {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [members, setMembers] = useState<WorkspaceMemberSummary[]>([]);
  const [documents, setDocuments] = useState<Array<{ id: string; title: string }>>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [state, setState] = useState<DashboardState>({
    overview: null,
    chats: null,
    leads: null,
    performance: null,
    queries: null,
    feedback: null,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      setIsLoading(true);
      try {
        const workspaceList = await fetchWorkspaces();
        if (!active) return;
        setWorkspaces(workspaceList);
        if (workspaceList.length) {
          setSelectedWorkspaceId((current) => current || workspaceList[0].id);
        }
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load analytics workspaces.");
      } finally {
        if (active) {
          setIsLoading(false);
        }
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
    async function loadWorkspaceDependencies() {
      try {
        const [workspaceMembers, workspaceDocuments] = await Promise.all([
          fetchWorkspaceMembers(selectedWorkspaceId).catch(() => []),
          fetchWorkspaceDocuments(selectedWorkspaceId).catch(() => []),
        ]);
        if (!active) return;
        setMembers(workspaceMembers);
        setDocuments(workspaceDocuments.map((document) => ({ id: document.id, title: document.title })));
      } catch {
        if (!active) return;
        setMembers([]);
        setDocuments([]);
      }
    }
    void loadWorkspaceDependencies();
    return () => {
      active = false;
    };
  }, [selectedWorkspaceId]);

  useEffect(() => {
    if (!selectedWorkspaceId) return;
    let cancelled = false;

    async function loadAnalytics(refresh = false) {
      if (refresh) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }
      try {
        const filters = {
          workspaceId: selectedWorkspaceId,
          dateFrom: dateFrom || undefined,
          dateTo: dateTo || undefined,
          userId: selectedUserId || undefined,
          documentId: selectedDocumentId || undefined,
          source: selectedSource || undefined,
        };
        if (view === "overview") {
          const overview = await fetchAnalyticsOverview(filters);
          if (cancelled) return;
          setState((current) => ({ ...current, overview }));
          setLastUpdatedAt(overview.generated_at);
        } else if (view === "chats") {
          const chats = await fetchChatAnalytics(filters);
          if (cancelled) return;
          setState((current) => ({ ...current, chats }));
          setLastUpdatedAt(chats.generated_at);
        } else if (view === "leads") {
          const leads = await fetchLeadAnalytics(filters);
          if (cancelled) return;
          setState((current) => ({ ...current, leads }));
          setLastUpdatedAt(leads.generated_at);
        } else if (view === "performance") {
          const [performance, feedback] = await Promise.all([
            fetchPerformanceAnalytics(filters),
            fetchFeedbackAnalytics(filters),
          ]);
          if (cancelled) return;
          setState((current) => ({ ...current, performance, feedback }));
          setLastUpdatedAt(performance.generated_at);
        } else {
          const queries = await fetchQueryAnalytics(filters);
          if (cancelled) return;
          setState((current) => ({ ...current, queries }));
          setLastUpdatedAt(queries.generated_at);
        }
        setError("");
      } catch (loadError) {
        if (cancelled) return;
        setError(loadError instanceof Error ? loadError.message : "Analytics could not be loaded.");
      } finally {
        if (!cancelled) {
          setIsLoading(false);
          setIsRefreshing(false);
        }
      }
    }

    void loadAnalytics();
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void loadAnalytics(true);
      }
    }, 30000);
    const onFocus = () => {
      void loadAnalytics(true);
    };
    window.addEventListener("focus", onFocus);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [dateFrom, dateTo, selectedDocumentId, selectedSource, selectedUserId, selectedWorkspaceId, view]);

  if (isLoading && !selectedWorkspaceId) {
    return (
      <main className="space-y-6">
        <LoadingGrid rows={2} />
        <LoadingGrid rows={4} />
      </main>
    );
  }

  if (error && !hasAnyPayload(state, view)) {
    return (
      <ErrorState
        actionLabel="Retry loading"
        description={error}
        onAction={() => window.location.reload()}
        title="Analytics dashboard could not be loaded"
      />
    );
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,0.15),transparent_30%),linear-gradient(145deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.35em] text-sky-200/70">Insights control</p>
            <h2 className="mt-3 text-4xl font-semibold text-white">Analytics and Insights</h2>
            <p className="mt-3 text-slate-300">
              Track real chat usage, lead performance, source health, and answer quality without mixing data across workspaces.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-slate-950"
              onClick={() => setExportModalOpen(true)}
              type="button"
            >
              Export Report
            </button>
            <button
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-200"
              onClick={() => window.location.reload()}
              type="button"
            >
              Refresh now
            </button>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3 text-xs text-slate-400">
          <span className="rounded-full border border-white/10 px-3 py-1.5">
            {isRefreshing ? "Refreshing live metrics" : "Auto-refresh every 30 seconds"}
          </span>
          <span className="rounded-full border border-white/10 px-3 py-1.5">
            {lastUpdatedAt ? `Last updated ${new Date(lastUpdatedAt).toLocaleString()}` : "Awaiting first dataset"}
          </span>
        </div>
      </section>

      <nav className="flex flex-wrap gap-3">
        {navItems.map((item) => (
          <Link
            key={item.href}
            className={`rounded-full px-4 py-2 text-sm transition ${
              item.view === view
                ? "bg-white text-slate-950"
                : "border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white"
            }`}
            href={item.href}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <select
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
          onChange={(event) => setSelectedWorkspaceId(event.target.value)}
          value={selectedWorkspaceId}
        >
          {workspaces.map((workspace) => (
            <option key={workspace.id} value={workspace.id}>
              {workspace.name} - {workspace.role}
            </option>
          ))}
        </select>
        <select
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
          onChange={(event) => setSelectedUserId(event.target.value)}
          value={selectedUserId}
        >
          <option value="">All users</option>
          {members.map((member) => (
            <option key={member.id} value={member.user_id}>
              {member.full_name} ({member.role})
            </option>
          ))}
        </select>
        <select
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
          onChange={(event) => setSelectedDocumentId(event.target.value)}
          value={selectedDocumentId}
        >
          <option value="">All documents</option>
          {documents.map((document) => (
            <option key={document.id} value={document.id}>
              {document.title}
            </option>
          ))}
        </select>
        <select
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none"
          onChange={(event) => setSelectedSource(event.target.value)}
          value={selectedSource}
        >
          <option value="">All sources</option>
          <option value="web">Web chat</option>
          <option value="chatbot">Chatbot</option>
          <option value="widget">Widget</option>
        </select>
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

      {error ? (
        <section className="rounded-3xl border border-amber-400/20 bg-amber-400/10 px-5 py-4 text-sm text-amber-100">
          {error}
        </section>
      ) : null}

      {isLoading && !hasAnyPayload(state, view) ? <LoadingGrid rows={4} /> : null}

      {view === "overview" && state.overview ? <OverviewView overview={state.overview} /> : null}
      {view === "chats" && state.chats ? <ChatsView chats={state.chats} /> : null}
      {view === "leads" && state.leads ? <LeadsView leads={state.leads} /> : null}
      {view === "performance" && state.performance && state.feedback ? (
        <PerformanceView feedback={state.feedback} performance={state.performance} />
      ) : null}
      {view === "queries" && state.queries ? <QueriesView queries={state.queries} /> : null}

      <ExportModal
        open={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        exportType="analytics"
        workspaceId={selectedWorkspaceId}
        title="Export analytics report"
        description="Generate a background analytics export with KPI summaries, trends, and a professional PDF report."
        defaultFormat="pdf"
        initialFilters={{
          dateFrom,
          dateTo,
          source: selectedSource,
          userId: selectedUserId,
          documentId: selectedDocumentId,
        }}
      />
    </main>
  );
}

function OverviewView({ overview }: { overview: AnalyticsOverviewResponse }) {
  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {overview.metric_cards.map((card) => (
          <article key={card.label} className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">{card.label}</p>
            <p className="mt-3 text-3xl font-semibold text-white">{card.display_value}</p>
            <p className="mt-2 text-sm text-slate-500">{card.hint}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <LineChartCard
          color="#38bdf8"
          data={overview.daily_chat_volume}
          subtitle="Daily chat sessions in the selected range"
          title="Chat volume trend"
        />
        <LineChartCard
          color="#fb923c"
          data={overview.daily_lead_volume}
          subtitle="Daily lead creation trend"
          title="Lead volume trend"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <DonutChartCard
          colors={["#38bdf8", "#fb923c", "#22c55e", "#facc15"]}
          data={overview.source_distribution}
          subtitle="Combined source mix across chats and leads"
          title="Source distribution"
        />
        <DonutChartCard
          colors={["#22c55e", "#f59e0b", "#ef4444", "#94a3b8"]}
          data={overview.confidence_distribution}
          subtitle="High, medium, and low confidence answers"
          title="Confidence distribution"
        />
        <BarChartCard
          color="linear-gradient(90deg,#38bdf8,#0ea5e9)"
          data={overview.top_knowledge_sources}
          subtitle="Most cited documents and URLs"
          title="Top knowledge sources"
        />
      </section>

      <InsightGrid alerts={overview.alerts} insights={overview.insights} />
    </div>
  );
}

function ChatsView({ chats }: { chats: ChatAnalyticsResponse }) {
  const statItems = [
    { label: "Messages per session", value: chats.messages_per_session.toFixed(2) },
    { label: "Avg session duration", value: `${chats.average_session_duration_minutes.toFixed(2)} min` },
  ];

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2">
        {statItems.map((item) => (
          <article key={item.label} className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">{item.label}</p>
            <p className="mt-3 text-3xl font-semibold text-white">{item.value}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <LineChartCard
          color="#38bdf8"
          data={chats.daily_chat_volume}
          subtitle="Session starts by day"
          title="Daily chat volume"
        />
        <LineChartCard
          color="#22c55e"
          data={chats.active_users_over_time}
          subtitle="Distinct active users by day"
          title="Active users over time"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <BarChartCard
          color="#0ea5e9"
          data={chats.peak_usage_times}
          subtitle="Hours with the heaviest message traffic"
          title="Peak usage times"
        />
        <DonutChartCard
          colors={["#38bdf8", "#22c55e", "#a855f7"]}
          data={chats.message_mix}
          subtitle="User and assistant message balance"
          title="Message mix"
        />
        <BarChartCard
          color="#22c55e"
          data={chats.session_length_distribution}
          subtitle="How long sessions tend to run"
          title="Session length distribution"
        />
      </section>
    </div>
  );
}

function LeadsView({ leads }: { leads: LeadAnalyticsResponse }) {
  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
          <p className="text-sm text-slate-400">Conversion rate</p>
          <p className="mt-3 text-3xl font-semibold text-white">{leads.conversion_rate.toFixed(2)}%</p>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <LineChartCard
          color="#fb923c"
          data={leads.leads_per_day}
          subtitle="Lead creation by day"
          title="Daily lead trend"
        />
        <LineChartCard
          color="#f59e0b"
          data={leads.leads_per_week}
          subtitle="Lead creation grouped by ISO week"
          title="Weekly lead trend"
        />
        <LineChartCard
          color="#f97316"
          data={leads.leads_per_month}
          subtitle="Lead creation grouped by month"
          title="Monthly lead trend"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <DonutChartCard
          colors={["#fb923c", "#f59e0b", "#38bdf8", "#22c55e"]}
          data={leads.lead_sources}
          subtitle="Where leads are being captured"
          title="Lead sources"
        />
        <DonutChartCard
          colors={["#ef4444", "#f59e0b", "#22c55e"]}
          data={leads.lead_priority_distribution}
          subtitle="Priority mix across captured leads"
          title="Priority distribution"
        />
        <BarChartCard
          color="#f97316"
          data={leads.funnel}
          subtitle="Progression from new to converted"
          title="Lead funnel"
        />
      </section>

      <InsightGrid alerts={[]} insights={leads.insights} />
    </div>
  );
}

function PerformanceView({
  performance,
  feedback,
}: {
  performance: PerformanceAnalyticsResponse;
  feedback: FeedbackAnalyticsResponse;
}) {
  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricMiniCard label="Unanswered queries" value={String(performance.unanswered_queries)} />
        <MetricMiniCard label="Retrieval success rate" value={`${performance.retrieval_success_rate.toFixed(2)}%`} />
        <MetricMiniCard label="Avg response time" value={`${performance.average_response_time_ms.toFixed(2)} ms`} />
        <MetricMiniCard label="Avg confidence" value={performance.average_confidence_score.toFixed(2)} />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <DonutChartCard
          colors={["#22c55e", "#f59e0b", "#ef4444"]}
          data={performance.confidence_distribution}
          subtitle="Answer confidence distribution"
          title="Confidence score distribution"
        />
        <DonutChartCard
          colors={["#22c55e", "#ef4444", "#94a3b8"]}
          data={feedback.positive_vs_negative}
          subtitle="Positive and negative response quality signals"
          title="Feedback sentiment"
        />
        <BarChartCard
          color="#22c55e"
          data={performance.feedback_confidence_correlation}
          subtitle="Average feedback rating by confidence tier"
          title="Confidence correlation"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <LineChartCard
          color="#22c55e"
          data={feedback.feedback_trends}
          subtitle="Net feedback trend over time"
          title="Feedback trend"
        />
        <LineChartCard
          color="#38bdf8"
          data={feedback.response_quality_over_time}
          subtitle="Aggregate quality movement over time"
          title="Response quality trend"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1.2fr]">
        <ChartPanel title="Most failed queries" subtitle="Questions most often escalated or left unresolved">
          <SimpleList
            items={performance.failed_queries.map((item) => ({
              title: item.query,
              value: `${item.count} unresolved`,
              meta: item.last_seen_at ? new Date(item.last_seen_at).toLocaleString() : "No timestamp",
            }))}
          />
        </ChartPanel>
        <ChartPanel title="Most disliked responses" subtitle="Responses receiving the highest volume of negative feedback">
          <SimpleList
            items={feedback.most_disliked_responses.map((item) => ({
              title: item.response_excerpt,
              value: `${item.feedback_count} negative signals`,
              meta: item.confidence ?? "Confidence unavailable",
            }))}
          />
        </ChartPanel>
      </section>

      <InsightGrid alerts={performance.alerts} insights={[]} />
    </div>
  );
}

function QueriesView({ queries }: { queries: QueryAnalyticsResponse }) {
  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-2">
        <LineChartCard
          color="#a855f7"
          data={queries.search_trends}
          subtitle="Question volume trend over time"
          title="Search trends"
        />
        <BarChartCard
          color="#8b5cf6"
          data={queries.top_knowledge_sources}
          subtitle="Knowledge sources cited most often"
          title="Top knowledge sources"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <ChartPanel title="Most asked questions" subtitle="Highest-frequency user questions">
          <SimpleList
            items={queries.most_asked_questions.map((item) => ({
              title: item.query,
              value: `${item.count} asks`,
              meta: item.share !== null ? `${item.share.toFixed(2)}% share` : "No share available",
            }))}
          />
        </ChartPanel>
        <ChartPanel title="Repeated queries" subtitle="Questions showing repeat demand">
          <SimpleList
            items={queries.repeated_queries.map((item) => ({
              title: item.query,
              value: `${item.count} repeats`,
              meta: item.last_seen_at ? new Date(item.last_seen_at).toLocaleString() : "No timestamp",
            }))}
          />
        </ChartPanel>
        <ChartPanel title="Keyword extraction" subtitle="Most frequent keywords in user questions">
          <SimpleList
            items={queries.keywords.map((item) => ({
              title: item.keyword,
              value: `${item.count} mentions`,
              meta: "Keyword frequency",
            }))}
          />
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <ChartPanel title="Topic clustering" subtitle="Basic topic buckets inferred from repeated questions">
          <SimpleList
            items={queries.topics.map((item) => ({
              title: item.topic,
              value: `${item.count} questions`,
              meta: item.sample_queries.join(" | "),
            }))}
          />
        </ChartPanel>
        <ChartPanel title="Chunk usage frequency" subtitle="Most referenced chunk excerpts across answers">
          <SimpleList
            items={queries.chunk_usage_frequency.map((item) => ({
              title: item.label,
              value: `${item.value} references`,
              meta: item.hint ?? "Chunk usage",
            }))}
          />
        </ChartPanel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <BarChartCard
          color="#38bdf8"
          data={queries.most_used_documents}
          subtitle="Most cited documents"
          title="Document usage"
        />
        <BarChartCard
          color="#22c55e"
          data={queries.most_used_urls}
          subtitle="Most cited website URLs"
          title="URL usage"
        />
      </section>

      <InsightGrid alerts={[]} insights={queries.insights} />
    </div>
  );
}

function InsightGrid({ alerts, insights }: { alerts: Array<{ title: string; description: string; severity: string }>; insights: Array<{ title: string; description: string; severity: string }> }) {
  const items = [...alerts, ...insights];
  if (!items.length) {
    return null;
  }
  return (
    <section className="grid gap-4 xl:grid-cols-2">
      {items.map((item) => (
        <article
          key={`${item.severity}-${item.title}`}
          className={`rounded-[1.6rem] border p-5 ${
            item.severity === "critical"
              ? "border-red-400/20 bg-red-500/10"
              : item.severity === "warning"
                ? "border-amber-400/20 bg-amber-500/10"
                : "border-sky-400/20 bg-sky-500/10"
          }`}
        >
          <p className="text-xs uppercase tracking-[0.3em] text-white/70">{item.severity}</p>
          <h3 className="mt-3 text-lg font-semibold text-white">{item.title}</h3>
          <p className="mt-2 text-sm text-slate-200">{item.description}</p>
        </article>
      ))}
    </section>
  );
}

function SimpleList({ items }: { items: Array<{ title: string; value: string; meta: string }> }) {
  if (!items.length) {
    return <p className="text-sm text-slate-500">No rows matched the current filters.</p>;
  }
  return (
    <div className="space-y-3">
      {items.map((item, index) => (
        <div key={`${item.title}-${index}`} className="rounded-3xl border border-white/10 bg-slate-950/45 p-4">
          <div className="flex items-start justify-between gap-4">
            <p className="text-sm text-slate-100">{item.title}</p>
            <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">{item.value}</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">{item.meta}</p>
        </div>
      ))}
    </div>
  );
}

function MetricMiniCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
    </article>
  );
}

function hasAnyPayload(state: DashboardState, view: AnalyticsView) {
  if (view === "overview") return Boolean(state.overview);
  if (view === "chats") return Boolean(state.chats);
  if (view === "leads") return Boolean(state.leads);
  if (view === "performance") return Boolean(state.performance);
  return Boolean(state.queries);
}
