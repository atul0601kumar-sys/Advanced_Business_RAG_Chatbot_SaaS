import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


AnalyticsSeverity = Literal["info", "warning", "critical"]


class AnalyticsFilters(BaseModel):
    workspace_id: uuid.UUID
    date_from: datetime | None = None
    date_to: datetime | None = None
    user_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    source: str | None = None


class MetricCard(BaseModel):
    label: str
    value: float
    display_value: str
    hint: str | None = None


class TimeSeriesPoint(BaseModel):
    bucket: str
    value: float
    label: str | None = None
    secondary_value: float | None = None


class BreakdownItem(BaseModel):
    label: str
    value: float
    hint: str | None = None
    extra: dict | None = None


class InsightItem(BaseModel):
    title: str
    description: str
    severity: AnalyticsSeverity = "info"


class QueryInsightItem(BaseModel):
    query: str
    count: int
    share: float | None = None
    last_seen_at: datetime | None = None


class KeywordInsightItem(BaseModel):
    keyword: str
    count: int


class TopicClusterItem(BaseModel):
    topic: str
    count: int
    sample_queries: list[str] = Field(default_factory=list)


class DislikedResponseItem(BaseModel):
    message_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    response_excerpt: str
    feedback_count: int
    confidence: str | None = None
    latest_feedback_at: datetime | None = None


class OverviewMetrics(BaseModel):
    total_chats: int
    total_users: int
    total_messages: int
    total_documents: int
    total_website_sources: int
    total_leads: int
    conversion_rate: float
    average_response_time_ms: float
    average_confidence_score: float


class AnalyticsOverviewResponse(BaseModel):
    generated_at: datetime
    filters: AnalyticsFilters
    metrics: OverviewMetrics
    metric_cards: list[MetricCard]
    daily_chat_volume: list[TimeSeriesPoint]
    daily_lead_volume: list[TimeSeriesPoint]
    source_distribution: list[BreakdownItem]
    confidence_distribution: list[BreakdownItem]
    top_knowledge_sources: list[BreakdownItem]
    alerts: list[InsightItem]
    insights: list[InsightItem]


class ChatAnalyticsResponse(BaseModel):
    generated_at: datetime
    filters: AnalyticsFilters
    daily_chat_volume: list[TimeSeriesPoint]
    messages_per_session: float
    average_session_duration_minutes: float
    peak_usage_times: list[BreakdownItem]
    active_users_over_time: list[TimeSeriesPoint]
    message_mix: list[BreakdownItem]
    session_length_distribution: list[BreakdownItem]


class LeadAnalyticsResponse(BaseModel):
    generated_at: datetime
    filters: AnalyticsFilters
    conversion_rate: float
    leads_per_day: list[TimeSeriesPoint]
    leads_per_week: list[TimeSeriesPoint]
    leads_per_month: list[TimeSeriesPoint]
    lead_sources: list[BreakdownItem]
    lead_priority_distribution: list[BreakdownItem]
    funnel: list[BreakdownItem]
    insights: list[InsightItem]


class PerformanceAnalyticsResponse(BaseModel):
    generated_at: datetime
    filters: AnalyticsFilters
    confidence_distribution: list[BreakdownItem]
    unanswered_queries: int
    failed_queries: list[QueryInsightItem]
    response_quality: list[BreakdownItem]
    retrieval_success_rate: float
    average_response_time_ms: float
    average_confidence_score: float
    feedback_confidence_correlation: list[BreakdownItem]
    alerts: list[InsightItem]


class QueryAnalyticsResponse(BaseModel):
    generated_at: datetime
    filters: AnalyticsFilters
    most_asked_questions: list[QueryInsightItem]
    search_trends: list[TimeSeriesPoint]
    repeated_queries: list[QueryInsightItem]
    keywords: list[KeywordInsightItem]
    topics: list[TopicClusterItem]
    most_used_documents: list[BreakdownItem]
    most_used_urls: list[BreakdownItem]
    chunk_usage_frequency: list[BreakdownItem]
    top_knowledge_sources: list[BreakdownItem]
    insights: list[InsightItem]


class FeedbackAnalyticsResponse(BaseModel):
    generated_at: datetime
    filters: AnalyticsFilters
    positive_vs_negative: list[BreakdownItem]
    feedback_trends: list[TimeSeriesPoint]
    most_disliked_responses: list[DislikedResponseItem]
    confidence_correlation: list[BreakdownItem]
    response_quality_over_time: list[TimeSeriesPoint]

