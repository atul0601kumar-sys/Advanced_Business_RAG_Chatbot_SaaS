from __future__ import annotations

import logging
from time import perf_counter
import uuid

from sqlalchemy.orm import Session

from app.schemas.analytics import (
    AnalyticsFilters,
    AnalyticsOverviewResponse,
    BreakdownItem,
    ChatAnalyticsResponse,
    FeedbackAnalyticsResponse,
    InsightItem,
    LeadAnalyticsResponse,
    MetricCard,
    OverviewMetrics,
    PerformanceAnalyticsResponse,
    QueryAnalyticsResponse,
    QueryInsightItem,
)
from app.services.metrics_calculator import MetricsCalculator
from app.services.query_analyzer import QueryAnalyzer
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(
        self,
        metrics_calculator: MetricsCalculator | None = None,
        query_analyzer: QueryAnalyzer | None = None,
        report_generator: ReportGenerator | None = None,
    ) -> None:
        self.metrics_calculator = metrics_calculator or MetricsCalculator()
        self.query_analyzer = query_analyzer or QueryAnalyzer()
        self.report_generator = report_generator or ReportGenerator()
        self._cache: dict[tuple[str, str], tuple[float, dict]] = {}
        self._cache_ttl_seconds = 20.0

    def get_overview(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        date_from,
        date_to,
        user_id,
        document_id,
        source,
    ) -> AnalyticsOverviewResponse:
        context, filters = self._build_context(
            workspace_id=workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        )

        def builder() -> AnalyticsOverviewResponse:
            sessions = self.metrics_calculator._load_sessions(db, context)
            messages = self.metrics_calculator._load_messages(db, context)
            leads = self.metrics_calculator._load_leads(db, context)
            _, _, _, top_sources = self.metrics_calculator.knowledge_source_usage(messages)
            confidence_distribution = self.metrics_calculator.confidence_distribution(messages)
            metrics = OverviewMetrics(
                total_chats=self.metrics_calculator.count_chat_sessions(db, context),
                total_users=self.metrics_calculator.count_workspace_users(db, context),
                total_messages=self.metrics_calculator.count_messages(db, context),
                total_documents=self.metrics_calculator.count_documents(db, context),
                total_website_sources=self.metrics_calculator.count_website_sources(db, context),
                total_leads=self.metrics_calculator.count_leads(db, context),
                conversion_rate=self.metrics_calculator.conversion_rate(leads),
                average_response_time_ms=self.metrics_calculator.average_response_time(messages),
                average_confidence_score=self.metrics_calculator.average_confidence(messages),
            )
            alerts, insights = self._overview_insights(messages=messages, leads=leads, confidence_distribution=confidence_distribution)
            return AnalyticsOverviewResponse(
                generated_at=self._now(),
                filters=filters,
                metrics=metrics,
                metric_cards=[
                    MetricCard(label="Total chats", value=float(metrics.total_chats), display_value=str(metrics.total_chats), hint="Chat sessions in range"),
                    MetricCard(label="Total users", value=float(metrics.total_users), display_value=str(metrics.total_users), hint="Workspace members covered"),
                    MetricCard(label="Total messages", value=float(metrics.total_messages), display_value=str(metrics.total_messages), hint="User and assistant messages"),
                    MetricCard(label="Total documents", value=float(metrics.total_documents), display_value=str(metrics.total_documents), hint="Knowledge files available"),
                    MetricCard(label="Conversion rate", value=metrics.conversion_rate, display_value=f"{metrics.conversion_rate:.2f}%", hint="Leads converted"),
                    MetricCard(label="Avg confidence", value=metrics.average_confidence_score, display_value=f"{metrics.average_confidence_score:.2f}", hint="0.3 low, 0.9 high"),
                ],
                daily_chat_volume=self.metrics_calculator.daily_chat_volume(sessions),
                daily_lead_volume=self.metrics_calculator.daily_lead_volume(leads),
                source_distribution=self.metrics_calculator.source_distribution_from_sessions_and_leads(sessions, leads),
                confidence_distribution=confidence_distribution,
                top_knowledge_sources=top_sources,
                alerts=alerts,
                insights=insights,
            )

        return AnalyticsOverviewResponse.model_validate(self._cached("overview", filters, builder))

    def get_chat_analytics(self, db: Session, **filters) -> ChatAnalyticsResponse:
        context, analytics_filters = self._build_context(**filters)

        def builder() -> ChatAnalyticsResponse:
            sessions = self.metrics_calculator._load_sessions(db, context)
            messages = self.metrics_calculator._load_messages(db, context)
            return ChatAnalyticsResponse(
                generated_at=self._now(),
                filters=analytics_filters,
                daily_chat_volume=self.metrics_calculator.daily_chat_volume(sessions),
                messages_per_session=self.metrics_calculator.messages_per_session(sessions, messages),
                average_session_duration_minutes=self.metrics_calculator.average_session_duration_minutes(sessions, messages),
                peak_usage_times=self.metrics_calculator.peak_usage_times(messages),
                active_users_over_time=self.metrics_calculator.active_users_over_time(sessions),
                message_mix=self.metrics_calculator.message_mix(messages),
                session_length_distribution=self.metrics_calculator.session_length_distribution(sessions, messages),
            )

        return ChatAnalyticsResponse.model_validate(self._cached("chats", analytics_filters, builder))

    def get_lead_analytics(self, db: Session, **filters) -> LeadAnalyticsResponse:
        context, analytics_filters = self._build_context(**filters)

        def builder() -> LeadAnalyticsResponse:
            leads = self.metrics_calculator._load_leads(db, context)
            conversion_rate = self.metrics_calculator.conversion_rate(leads)
            insights: list[InsightItem] = []
            if conversion_rate < 10 and leads:
                insights.append(
                    InsightItem(
                        title="Lead conversion is below target",
                        description="A low share of captured leads are reaching converted status. Review handoff speed and follow-up quality.",
                        severity="warning",
                    )
                )
            if any(lead.priority == "high" for lead in leads):
                insights.append(
                    InsightItem(
                        title="High-priority demand is active",
                        description="High-priority leads are present in this filtered range. Prioritize outreach to protect conversion.",
                        severity="info",
                    )
                )
            return LeadAnalyticsResponse(
                generated_at=self._now(),
                filters=analytics_filters,
                conversion_rate=conversion_rate,
                leads_per_day=self.metrics_calculator.grouped_leads(leads, "day"),
                leads_per_week=self.metrics_calculator.grouped_leads(leads, "week"),
                leads_per_month=self.metrics_calculator.grouped_leads(leads, "month"),
                lead_sources=self.metrics_calculator.lead_sources(leads),
                lead_priority_distribution=self.metrics_calculator.lead_priority_distribution(leads),
                funnel=self.metrics_calculator.lead_funnel(leads),
                insights=insights,
            )

        return LeadAnalyticsResponse.model_validate(self._cached("leads", analytics_filters, builder))

    def get_performance_analytics(self, db: Session, **filters) -> PerformanceAnalyticsResponse:
        context, analytics_filters = self._build_context(**filters)

        def builder() -> PerformanceAnalyticsResponse:
            messages = self.metrics_calculator._load_messages(db, context)
            feedback_entries = self.metrics_calculator.feedback_entries(db, context)
            messages_by_id = {message.id: message for message in messages}
            failed_queries = [
                QueryInsightItem(query=query, count=count, last_seen_at=last_seen)
                for query, count, last_seen in self.metrics_calculator.failed_queries(db, context)
            ]
            unanswered = self.metrics_calculator.unanswered_queries(db, context)
            alerts: list[InsightItem] = []
            retrieval_success_rate = self.metrics_calculator.retrieval_success_rate(messages)
            avg_confidence = self.metrics_calculator.average_confidence(messages)
            if unanswered >= 5:
                alerts.append(
                    InsightItem(
                        title="Unanswered question volume is elevated",
                        description=f"{unanswered} unresolved questions were recorded in the selected range.",
                        severity="critical",
                    )
                )
            if retrieval_success_rate < 70 and messages:
                alerts.append(
                    InsightItem(
                        title="Retrieval success rate has dropped",
                        description="A large share of assistant messages did not cite retrieved knowledge. Review indexing health and chunk coverage.",
                        severity="warning",
                    )
                )
            return PerformanceAnalyticsResponse(
                generated_at=self._now(),
                filters=analytics_filters,
                confidence_distribution=self.metrics_calculator.confidence_distribution(messages),
                unanswered_queries=unanswered,
                failed_queries=failed_queries,
                response_quality=self.metrics_calculator.response_quality(feedback_entries),
                retrieval_success_rate=retrieval_success_rate,
                average_response_time_ms=self.metrics_calculator.average_response_time(messages),
                average_confidence_score=avg_confidence,
                feedback_confidence_correlation=self.metrics_calculator.feedback_confidence_correlation(feedback_entries, messages_by_id),
                alerts=alerts,
            )

        return PerformanceAnalyticsResponse.model_validate(self._cached("performance", analytics_filters, builder))

    def get_query_analytics(self, db: Session, **filters) -> QueryAnalyticsResponse:
        context, analytics_filters = self._build_context(**filters)

        def builder() -> QueryAnalyticsResponse:
            events = self.metrics_calculator.analytics_events(db, context, event_type="message_sent")
            records = self.query_analyzer.build_query_records(
                [
                    ((event.properties_json or {}).get("query") or "", event.occurred_at)
                    for event in events
                    if event.properties_json
                ]
            )
            messages = self.metrics_calculator._load_messages(db, context)
            most_used_documents, most_used_urls, chunk_usage_frequency, top_knowledge_sources = self.metrics_calculator.knowledge_source_usage(messages)
            insights: list[InsightItem] = []
            keywords = self.query_analyzer.extract_keywords(records)
            if keywords:
                insights.append(
                    InsightItem(
                        title="Strongest recurring demand",
                        description=f"Most users are asking about {keywords[0].keyword}.",
                        severity="info",
                    )
                )
            trend_counter: dict[str, int] = {}
            for record in records:
                if record.occurred_at is None:
                    continue
                bucket = self.metrics_calculator._format_bucket(record.occurred_at, "day")
                trend_counter[bucket] = trend_counter.get(bucket, 0) + 1
            search_trends = [
                {"bucket": bucket, "value": float(value), "label": bucket, "secondary_value": None}
                for bucket, value in sorted(trend_counter.items())
            ]
            return QueryAnalyticsResponse(
                generated_at=self._now(),
                filters=analytics_filters,
                most_asked_questions=self.query_analyzer.top_questions(records),
                search_trends=search_trends,
                repeated_queries=self.query_analyzer.repeated_queries(records),
                keywords=keywords,
                topics=self.query_analyzer.cluster_topics(records),
                most_used_documents=most_used_documents,
                most_used_urls=most_used_urls,
                chunk_usage_frequency=chunk_usage_frequency,
                top_knowledge_sources=top_knowledge_sources,
                insights=insights,
            )

        return QueryAnalyticsResponse.model_validate(self._cached("queries", analytics_filters, builder))

    def get_feedback_analytics(self, db: Session, **filters) -> FeedbackAnalyticsResponse:
        context, analytics_filters = self._build_context(**filters)

        def builder() -> FeedbackAnalyticsResponse:
            feedback_entries = self.metrics_calculator.feedback_entries(db, context)
            messages = self.metrics_calculator._load_messages(db, context)
            messages_by_id = {message.id: message for message in messages}
            return FeedbackAnalyticsResponse(
                generated_at=self._now(),
                filters=analytics_filters,
                positive_vs_negative=self.metrics_calculator.response_quality(feedback_entries),
                feedback_trends=self.metrics_calculator.feedback_trends(feedback_entries),
                most_disliked_responses=self.metrics_calculator.most_disliked_responses(feedback_entries, messages_by_id),
                confidence_correlation=self.metrics_calculator.feedback_confidence_correlation(feedback_entries, messages_by_id),
                response_quality_over_time=self.metrics_calculator.feedback_trends(feedback_entries),
            )

        return FeedbackAnalyticsResponse.model_validate(self._cached("feedback", analytics_filters, builder))

    def export_csv(self, payload) -> str:
        return self.report_generator.to_csv(payload)

    def _build_context(self, *, workspace_id, date_from, date_to, user_id, document_id, source):
        context = self.metrics_calculator.build_context(
            workspace_id=workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        )
        filters = AnalyticsFilters(
            workspace_id=workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        )
        return context, filters

    def _cached(self, report_name: str, filters: AnalyticsFilters, builder):
        key = (report_name, filters.model_dump_json())
        started = perf_counter()
        cached = self._cache.get(key)
        now = perf_counter()
        if cached and now - cached[0] <= self._cache_ttl_seconds:
            return cached[1]
        payload = builder().model_dump(mode="json")
        self._cache[key] = (now, payload)
        elapsed = perf_counter() - started
        if elapsed > 0.75:
            logger.warning(
                "Analytics report generation was slow",
                extra={"report_name": report_name, "elapsed_ms": round(elapsed * 1000, 2)},
            )
        else:
            logger.info(
                "Analytics report generated",
                extra={"report_name": report_name, "elapsed_ms": round(elapsed * 1000, 2)},
            )
        return payload

    def _overview_insights(self, *, messages, leads, confidence_distribution: list[BreakdownItem]):
        alerts: list[InsightItem] = []
        insights: list[InsightItem] = []
        low_confidence = next((item.value for item in confidence_distribution if item.label == "Low"), 0.0)
        if low_confidence >= 5:
            alerts.append(
                InsightItem(
                    title="Low-confidence answers are rising",
                    description="A meaningful share of assistant replies are landing in the low-confidence band.",
                    severity="warning",
                )
            )
        if len(messages) >= 20:
            insights.append(
                InsightItem(
                    title="Usage spike detected",
                    description="Message volume is high enough in this range to justify checking staffing and source freshness.",
                    severity="info",
                )
            )
        if any(lead.status == "qualified" for lead in leads):
            insights.append(
                InsightItem(
                    title="Pipeline is moving beyond capture",
                    description="Qualified leads are present, which is a positive sign that the handoff path is working.",
                    severity="info",
                )
            )
        return alerts, insights

    def _now(self):
        from datetime import UTC, datetime

        return datetime.now(UTC)
