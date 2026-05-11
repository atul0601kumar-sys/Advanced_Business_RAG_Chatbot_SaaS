export type DashboardCard = {
  id: string;
  title: string;
  subtitle: string;
  meta: string;
  badge?: string;
};

export type DashboardMetric = {
  label: string;
  value: string;
  hint: string;
};

export const documentsMetrics: DashboardMetric[] = [
  { label: "Indexed files", value: "128", hint: "Across PDF, DOCX, and CSV inputs" },
  { label: "Fresh today", value: "12", hint: "New uploads in the last 24 hours" },
  { label: "Coverage", value: "91%", hint: "Chunks linked to active retrieval profiles" },
];

export const documentsItems: DashboardCard[] = [
  {
    id: "doc-1",
    title: "Board Reporting Pack",
    subtitle: "Quarterly operating plan with revenue commentary and escalations.",
    meta: "Updated 18 minutes ago",
    badge: "Indexed",
  },
  {
    id: "doc-2",
    title: "Sales Playbook 2026",
    subtitle: "Objection handling, ICP guidance, and lead qualification rules.",
    meta: "Synced from local upload",
    badge: "Ready",
  },
  {
    id: "doc-3",
    title: "Support SLA Policy",
    subtitle: "Customer-facing service commitments and routing workflows.",
    meta: "Version 7 active",
  },
];

export const websiteMetrics: DashboardMetric[] = [
  { label: "Tracked domains", value: "14", hint: "Public pages in the crawler map" },
  { label: "Last crawl success", value: "98.2%", hint: "Successful pulls over the last week" },
  { label: "Pending changes", value: "6", hint: "Pages flagged for recrawl" },
];

export const websiteItems: DashboardCard[] = [
  {
    id: "web-1",
    title: "Pricing Portal",
    subtitle: "Captures plan comparisons and enterprise contact flows.",
    meta: "Crawled 43 minutes ago",
    badge: "Healthy",
  },
  {
    id: "web-2",
    title: "Knowledge Center",
    subtitle: "Help articles, product guides, and onboarding flows.",
    meta: "2 pages changed since last sync",
    badge: "Recrawl",
  },
  {
    id: "web-3",
    title: "Partner Docs",
    subtitle: "Partner-facing API and enablement pages.",
    meta: "Scope limited to /partners/*",
  },
];

export const chatMetrics: DashboardMetric[] = [
  { label: "Active conversations", value: "23", hint: "Sessions currently open in the widget" },
  { label: "Median latency", value: "1.2s", hint: "Across recent completions" },
  { label: "Grounded answers", value: "94%", hint: "Responses with source citations attached" },
];

export const chatItems: DashboardCard[] = [
  {
    id: "chat-1",
    title: "Enterprise pricing clarification",
    subtitle: "Visitor is comparing annual billing and custom security add-ons.",
    meta: "Live now",
    badge: "Escalate",
  },
  {
    id: "chat-2",
    title: "Onboarding checklist request",
    subtitle: "User wants a step-by-step implementation summary from indexed docs.",
    meta: "Assigned to AI assistant",
    badge: "Live",
  },
  {
    id: "chat-3",
    title: "ROI case study lookup",
    subtitle: "Prospect is searching for industry-specific success stories.",
    meta: "Awaiting human review",
  },
];

export const historyMetrics: DashboardMetric[] = [
  { label: "Stored sessions", value: "1,284", hint: "Searchable transcripts and summaries" },
  { label: "Escalations", value: "47", hint: "Chats transferred to humans this month" },
  { label: "Repeat visitors", value: "32%", hint: "Users with returning conversations" },
];

export const historyItems: DashboardCard[] = [
  {
    id: "hist-1",
    title: "Procurement workflow session",
    subtitle: "Conversation tagged with contract review and procurement blockers.",
    meta: "Yesterday at 6:14 PM",
    badge: "Resolved",
  },
  {
    id: "hist-2",
    title: "Implementation FAQ session",
    subtitle: "Transcript includes architecture and deployment questions.",
    meta: "Yesterday at 2:09 PM",
  },
];

export const leadsMetrics: DashboardMetric[] = [
  { label: "Qualified leads", value: "38", hint: "Passed intent and profile scoring" },
  { label: "Pipeline value", value: "$412K", hint: "Estimated influenced revenue" },
  { label: "Follow-up due", value: "9", hint: "Leads awaiting human response" },
];

export const leadsItems: DashboardCard[] = [
  {
    id: "lead-1",
    title: "Northwind Capital",
    subtitle: "Requested enterprise pricing deck and SOC2 addendum.",
    meta: "Owner: Revenue Ops",
    badge: "High intent",
  },
  {
    id: "lead-2",
    title: "BluePeak Logistics",
    subtitle: "Interested in multi-workspace controls and audit visibility.",
    meta: "Next follow-up in 3 hours",
  },
];

export const analyticsMetrics: DashboardMetric[] = [
  { label: "Questions answered", value: "9.8K", hint: "Across all channels this month" },
  { label: "Deflection rate", value: "61%", hint: "Support load handled without escalation" },
  { label: "Source utilization", value: "83%", hint: "Chunks referenced in final answers" },
];

export const analyticsItems: DashboardCard[] = [
  {
    id: "ana-1",
    title: "Traffic by source cluster",
    subtitle: "Top entry pages are pricing, help center, and integration docs.",
    meta: "Updated every 15 minutes",
    badge: "Live",
  },
  {
    id: "ana-2",
    title: "Intent trendline",
    subtitle: "Budget, security, and onboarding intents are climbing this week.",
    meta: "Week-over-week comparison ready",
  },
];

export const settingsMetrics: DashboardMetric[] = [
  { label: "Active policies", value: "11", hint: "Prompt and workspace controls in force" },
  { label: "Guardrails", value: "6", hint: "Safety and routing conditions enabled" },
  { label: "Sync cadence", value: "Hourly", hint: "Knowledge refresh frequency" },
];

export const settingsItems: DashboardCard[] = [
  {
    id: "set-1",
    title: "Assistant behavior",
    subtitle: "Tune prompt tone, escalation rules, and lead capture behavior.",
    meta: "Last modified by admin",
    badge: "Priority",
  },
  {
    id: "set-2",
    title: "Domain and widget controls",
    subtitle: "Configure embedding targets, brand styling, and access boundaries.",
    meta: "2 domains allowlisted",
  },
];

export const teamMetrics: DashboardMetric[] = [
  { label: "Workspace members", value: "12", hint: "Operators, admins, and viewers" },
  { label: "Admins", value: "3", hint: "Users with configuration access" },
  { label: "Pending invites", value: "2", hint: "Awaiting acceptance" },
];

export const teamItems: DashboardCard[] = [
  {
    id: "team-1",
    title: "Aarav Singh",
    subtitle: "Revenue systems owner managing ingestion and reporting.",
    meta: "Role: admin",
    badge: "Admin",
  },
  {
    id: "team-2",
    title: "Nina Patel",
    subtitle: "Customer success lead reviewing chat escalations daily.",
    meta: "Role: team_member",
  },
  {
    id: "team-3",
    title: "Marco Chen",
    subtitle: "Executive observer monitoring workspace analytics.",
    meta: "Role: viewer",
  },
];

export const widgetMetrics: DashboardMetric[] = [
  { label: "Theme variants", value: "4", hint: "Preview states ready for handoff" },
  { label: "Embed targets", value: "3", hint: "Marketing site, app, help center" },
  { label: "Mobile readiness", value: "100%", hint: "Preview layout adapted for smaller screens" },
];

export const widgetItems: DashboardCard[] = [
  {
    id: "widget-1",
    title: "Marketing site launcher",
    subtitle: "Compact bubble with bold header and pricing-first quick prompts.",
    meta: "Desktop preview ready",
    badge: "Primary",
  },
  {
    id: "widget-2",
    title: "Product support drawer",
    subtitle: "Right-aligned panel optimized for authenticated user support questions.",
    meta: "Mobile breakpoint checked",
  },
];

