from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import statistics
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AnalyticsEvent, ChatMessage, ChatSession, Document, Feedback, Lead, UnresolvedQuestion, WebsiteSource, WorkspaceMember
from app.schemas.analytics import BreakdownItem, TimeSeriesPoint


@dataclass
class MetricsContext:
    workspace_id: uuid.UUID
    date_from: datetime | None = None
    date_to: datetime | None = None
    user_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    source: str | None = None


class MetricsCalculator:
    def build_context(
        self,
        *,
        workspace_id: uuid.UUID,
        date_from: datetime | None,
        date_to: datetime | None,
        user_id: uuid.UUID | None,
        document_id: uuid.UUID | None,
        source: str | None,
    ) -> MetricsContext:
        return MetricsContext(
            workspace_id=workspace_id,
            date_from=date_from,
            date_to=date_to,
            user_id=user_id,
            document_id=document_id,
            source=source,
        )

    def count_chat_sessions(self, db: Session, context: MetricsContext) -> int:
        sessions = self._load_sessions(db, context)
        return len(sessions)

    def count_workspace_users(self, db: Session, context: MetricsContext) -> int:
        query = select(func.count(func.distinct(WorkspaceMember.user_id))).where(
            WorkspaceMember.workspace_id == context.workspace_id
        )
        if context.user_id:
            query = query.where(WorkspaceMember.user_id == context.user_id)
        return int(db.scalar(query) or 0)

    def count_messages(self, db: Session, context: MetricsContext) -> int:
        return len(self._load_messages(db, context))

    def count_documents(self, db: Session, context: MetricsContext) -> int:
        query = select(func.count(Document.id)).where(Document.workspace_id == context.workspace_id)
        if context.document_id:
            query = query.where(Document.id == context.document_id)
        return int(db.scalar(query) or 0)

    def count_website_sources(self, db: Session, context: MetricsContext) -> int:
        query = select(func.count(WebsiteSource.id)).where(WebsiteSource.workspace_id == context.workspace_id)
        if context.document_id:
            query = query.where(WebsiteSource.document_id == context.document_id)
        return int(db.scalar(query) or 0)

    def count_leads(self, db: Session, context: MetricsContext) -> int:
        leads = self._load_leads(db, context)
        return len(leads)

    def conversion_rate(self, leads: list[Lead]) -> float:
        if not leads:
            return 0.0
        converted = sum(1 for lead in leads if lead.status == "converted")
        return round((converted / len(leads)) * 100, 2)

    def average_response_time(self, messages: list[ChatMessage]) -> float:
        values = [float(message.response_time_ms) for message in messages if message.role == "assistant" and message.response_time_ms]
        return round(sum(values) / len(values), 2) if values else 0.0

    def average_confidence(self, messages: list[ChatMessage]) -> float:
        values: list[float] = []
        for message in messages:
            if message.role != "assistant" or not message.token_usage_json:
                continue
            confidence = message.token_usage_json.get("confidence")
            if confidence == "High":
                values.append(0.9)
            elif confidence == "Medium":
                values.append(0.6)
            elif confidence == "Low":
                values.append(0.3)
        return round(sum(values) / len(values), 3) if values else 0.0

    def daily_chat_volume(self, sessions: list[ChatSession]) -> list[TimeSeriesPoint]:
        counter = Counter(self._format_bucket(session.started_at, "day") for session in sessions if session.started_at)
        return [TimeSeriesPoint(bucket=bucket, value=float(count), label=bucket) for bucket, count in sorted(counter.items())]

    def daily_lead_volume(self, leads: list[Lead]) -> list[TimeSeriesPoint]:
        counter = Counter(self._format_bucket(lead.created_at, "day") for lead in leads if lead.created_at)
        return [TimeSeriesPoint(bucket=bucket, value=float(count), label=bucket) for bucket, count in sorted(counter.items())]

    def grouped_leads(self, leads: list[Lead], granularity: str) -> list[TimeSeriesPoint]:
        counter = Counter(self._format_bucket(lead.created_at, granularity) for lead in leads if lead.created_at)
        return [TimeSeriesPoint(bucket=bucket, value=float(count), label=bucket) for bucket, count in sorted(counter.items())]

    def source_distribution_from_sessions_and_leads(self, sessions: list[ChatSession], leads: list[Lead]) -> list[BreakdownItem]:
        counter: Counter[str] = Counter()
        counter.update(session.channel or "unknown" for session in sessions)
        counter.update(lead.source or "unknown" for lead in leads)
        return [BreakdownItem(label=label, value=float(value)) for label, value in counter.most_common()]

    def confidence_distribution(self, messages: list[ChatMessage]) -> list[BreakdownItem]:
        counter: Counter[str] = Counter()
        for message in messages:
            if message.role != "assistant" or not message.token_usage_json:
                continue
            counter.update([message.token_usage_json.get("confidence") or "Unknown"])
        return [BreakdownItem(label=label, value=float(value)) for label, value in counter.items()]

    def message_mix(self, messages: list[ChatMessage]) -> list[BreakdownItem]:
        counter = Counter(message.role for message in messages)
        return [BreakdownItem(label=label, value=float(value)) for label, value in counter.items()]

    def messages_per_session(self, sessions: list[ChatSession], messages: list[ChatMessage]) -> float:
        return round(len(messages) / len(sessions), 2) if sessions else 0.0

    def average_session_duration_minutes(self, sessions: list[ChatSession], messages: list[ChatMessage]) -> float:
        message_groups: defaultdict[uuid.UUID, list[datetime]] = defaultdict(list)
        for message in messages:
            message_groups[message.chat_session_id].append(message.created_at)
        durations: list[float] = []
        for session in sessions:
            timestamps = sorted(message_groups.get(session.id, []))
            if timestamps:
                end_time = timestamps[-1]
            else:
                end_time = session.last_message_at or session.started_at
            if end_time and session.started_at:
                durations.append(max((end_time - session.started_at).total_seconds(), 0.0) / 60)
        return round(sum(durations) / len(durations), 2) if durations else 0.0

    def peak_usage_times(self, messages: list[ChatMessage]) -> list[BreakdownItem]:
        counter = Counter(f"{message.created_at.hour:02d}:00" for message in messages if message.created_at)
        return [BreakdownItem(label=label, value=float(value)) for label, value in counter.most_common(8)]

    def active_users_over_time(self, sessions: list[ChatSession]) -> list[TimeSeriesPoint]:
        grouped: defaultdict[str, set[uuid.UUID]] = defaultdict(set)
        for session in sessions:
            if session.user_id:
                grouped[self._format_bucket(session.started_at, "day")].add(session.user_id)
        return [
            TimeSeriesPoint(bucket=bucket, value=float(len(user_ids)), label=bucket)
            for bucket, user_ids in sorted(grouped.items())
        ]

    def session_length_distribution(self, sessions: list[ChatSession], messages: list[ChatMessage]) -> list[BreakdownItem]:
        message_groups: defaultdict[uuid.UUID, int] = defaultdict(int)
        for message in messages:
            message_groups[message.chat_session_id] += 1
        buckets = {"1-2": 0, "3-5": 0, "6-10": 0, "10+": 0}
        for session in sessions:
            count = message_groups.get(session.id, 0)
            if count <= 2:
                buckets["1-2"] += 1
            elif count <= 5:
                buckets["3-5"] += 1
            elif count <= 10:
                buckets["6-10"] += 1
            else:
                buckets["10+"] += 1
        return [BreakdownItem(label=label, value=float(value)) for label, value in buckets.items()]

    def lead_sources(self, leads: list[Lead]) -> list[BreakdownItem]:
        counter = Counter(lead.source or "unknown" for lead in leads)
        return [BreakdownItem(label=label, value=float(value)) for label, value in counter.items()]

    def lead_priority_distribution(self, leads: list[Lead]) -> list[BreakdownItem]:
        counter = Counter(lead.priority or "unknown" for lead in leads)
        return [BreakdownItem(label=label, value=float(value)) for label, value in counter.items()]

    def lead_funnel(self, leads: list[Lead]) -> list[BreakdownItem]:
        ordered = ["new", "contacted", "qualified", "converted", "closed"]
        counter = Counter(lead.status or "unknown" for lead in leads)
        return [BreakdownItem(label=status.title(), value=float(counter.get(status, 0))) for status in ordered]

    def unanswered_queries(self, db: Session, context: MetricsContext) -> int:
        return len(self._load_unresolved_questions(db, context))

    def failed_queries(self, db: Session, context: MetricsContext) -> list[tuple[str, int, datetime | None]]:
        grouped: defaultdict[str, list[datetime | None]] = defaultdict(list)
        for item in self._load_unresolved_questions(db, context):
            normalized = " ".join((item.normalized_question or item.question or "").split())
            if not normalized:
                continue
            grouped[normalized].append(item.created_at)
        rows = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
        return [(question, len(occurrences), max(occurrences)) for question, occurrences in rows[:10]]

    def response_quality(self, feedback_entries: list[Feedback]) -> list[BreakdownItem]:
        positive = sum(1 for item in feedback_entries if item.rating > 0)
        negative = sum(1 for item in feedback_entries if item.rating < 0)
        neutral = sum(1 for item in feedback_entries if item.rating == 0)
        return [
            BreakdownItem(label="Positive", value=float(positive)),
            BreakdownItem(label="Negative", value=float(negative)),
            BreakdownItem(label="Neutral", value=float(neutral)),
        ]

    def retrieval_success_rate(self, messages: list[ChatMessage]) -> float:
        assistant_messages = [message for message in messages if message.role == "assistant"]
        if not assistant_messages:
            return 0.0
        successes = 0
        for message in assistant_messages:
            retrieved = 0
            if message.token_usage_json:
                retrieved = int(message.token_usage_json.get("retrieved_chunks") or 0)
            if retrieved > 0 or message.citations_json:
                successes += 1
        return round((successes / len(assistant_messages)) * 100, 2)

    def feedback_confidence_correlation(self, feedback_entries: list[Feedback], messages_by_id: dict[uuid.UUID, ChatMessage]) -> list[BreakdownItem]:
        grouped: defaultdict[str, list[int]] = defaultdict(list)
        for entry in feedback_entries:
            if not entry.chat_message_id:
                continue
            message = messages_by_id.get(entry.chat_message_id)
            confidence = None
            if message and message.token_usage_json:
                confidence = message.token_usage_json.get("confidence")
            grouped[confidence or "Unknown"].append(entry.rating)
        rows: list[BreakdownItem] = []
        for label, ratings in grouped.items():
            rows.append(
                BreakdownItem(
                    label=label,
                    value=round(sum(ratings) / len(ratings), 2),
                    hint=f"{len(ratings)} feedback events",
                )
            )
        return rows

    def feedback_trends(self, feedback_entries: list[Feedback]) -> list[TimeSeriesPoint]:
        grouped: defaultdict[str, list[int]] = defaultdict(list)
        for entry in feedback_entries:
            grouped[self._format_bucket(entry.created_at, "day")].append(entry.rating)
        return [
            TimeSeriesPoint(bucket=bucket, value=float(sum(values)), secondary_value=float(len(values)), label=bucket)
            for bucket, values in sorted(grouped.items())
        ]

    def most_disliked_responses(self, feedback_entries: list[Feedback], messages_by_id: dict[uuid.UUID, ChatMessage]) -> list[dict]:
        grouped: defaultdict[uuid.UUID, list[Feedback]] = defaultdict(list)
        for entry in feedback_entries:
            if entry.rating < 0 and entry.chat_message_id:
                grouped[entry.chat_message_id].append(entry)
        rows = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
        results: list[dict] = []
        for message_id, entries in rows[:8]:
            message = messages_by_id.get(message_id)
            confidence = None
            if message and message.token_usage_json:
                confidence = message.token_usage_json.get("confidence")
            results.append(
                {
                    "message_id": message.id if message else None,
                    "session_id": message.chat_session_id if message else None,
                    "response_excerpt": (message.content[:220] if message else "Response unavailable."),
                    "feedback_count": len(entries),
                    "confidence": confidence,
                    "latest_feedback_at": max(entry.created_at for entry in entries if entry.created_at) if entries else None,
                }
            )
        return results

    def knowledge_source_usage(self, messages: list[ChatMessage]) -> tuple[list[BreakdownItem], list[BreakdownItem], list[BreakdownItem], list[BreakdownItem]]:
        documents = Counter()
        urls = Counter()
        chunks = Counter()
        combined = Counter()
        for message in messages:
            if message.role != "assistant":
                continue
            for citation in message.citations_json or []:
                doc_label = citation.get("file_name") or citation.get("document_id")
                url_label = citation.get("url")
                page = citation.get("page_number")
                preview = (citation.get("chunk_preview") or "")[:80]
                if doc_label:
                    documents[doc_label] += 1
                    combined[doc_label] += 1
                if url_label:
                    urls[url_label] += 1
                    combined[url_label] += 1
                chunk_label = " | ".join(part for part in [doc_label or url_label, str(page) if page is not None else None, preview] if part)
                if chunk_label:
                    chunks[chunk_label] += 1
        return (
            [BreakdownItem(label=label, value=float(value)) for label, value in documents.most_common(8)],
            [BreakdownItem(label=label, value=float(value)) for label, value in urls.most_common(8)],
            [BreakdownItem(label=label, value=float(value)) for label, value in chunks.most_common(10)],
            [BreakdownItem(label=label, value=float(value)) for label, value in combined.most_common(10)],
        )

    def feedback_entries(self, db: Session, context: MetricsContext) -> list[Feedback]:
        query = select(Feedback).where(Feedback.workspace_id == context.workspace_id)
        if context.date_from:
            query = query.where(Feedback.created_at >= context.date_from)
        if context.date_to:
            query = query.where(Feedback.created_at <= context.date_to)
        if context.user_id:
            query = query.where(Feedback.user_id == context.user_id)
        return db.scalars(query.order_by(Feedback.created_at.asc())).all()

    def analytics_events(self, db: Session, context: MetricsContext, event_type: str | None = None) -> list[AnalyticsEvent]:
        query = select(AnalyticsEvent).where(AnalyticsEvent.workspace_id == context.workspace_id)
        if context.date_from:
            query = query.where(AnalyticsEvent.occurred_at >= context.date_from)
        if context.date_to:
            query = query.where(AnalyticsEvent.occurred_at <= context.date_to)
        if context.user_id:
            query = query.where(AnalyticsEvent.user_id == context.user_id)
        if event_type:
            query = query.where(AnalyticsEvent.event_type == event_type)
        events = db.scalars(query.order_by(AnalyticsEvent.occurred_at.asc())).all()
        if context.source or context.document_id:
            return [event for event in events if self._event_matches_filters(event, context)]
        return events

    def _load_sessions(self, db: Session, context: MetricsContext) -> list[ChatSession]:
        query = select(ChatSession).where(ChatSession.workspace_id == context.workspace_id)
        if context.date_from:
            query = query.where(ChatSession.started_at >= context.date_from)
        if context.date_to:
            query = query.where(ChatSession.started_at <= context.date_to)
        if context.user_id:
            query = query.where(ChatSession.user_id == context.user_id)
        if context.source:
            query = query.where(ChatSession.channel == context.source)
        sessions = db.scalars(query.order_by(ChatSession.started_at.asc())).all()
        if not context.document_id:
            return sessions
        session_ids = {event.chat_session_id for event in self.analytics_events(db, context) if event.chat_session_id}
        return [session for session in sessions if session.id in session_ids]

    def _load_messages(self, db: Session, context: MetricsContext) -> list[ChatMessage]:
        query = (
            select(ChatMessage)
            .join(ChatSession, ChatSession.id == ChatMessage.chat_session_id)
            .where(ChatSession.workspace_id == context.workspace_id)
        )
        if context.date_from:
            query = query.where(ChatMessage.created_at >= context.date_from)
        if context.date_to:
            query = query.where(ChatMessage.created_at <= context.date_to)
        if context.user_id:
            query = query.where(ChatSession.user_id == context.user_id)
        if context.source:
            query = query.where(ChatSession.channel == context.source)
        messages = db.scalars(query.order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())).all()
        if not context.document_id:
            return messages
        document_id = str(context.document_id)
        filtered: list[ChatMessage] = []
        for message in messages:
            if message.role == "assistant":
                cited_ids = {str(item.get("document_id")) for item in (message.citations_json or []) if item.get("document_id")}
                if document_id in cited_ids:
                    filtered.append(message)
                    continue
            if message.role == "user":
                filtered.append(message)
        return filtered

    def _load_leads(self, db: Session, context: MetricsContext) -> list[Lead]:
        query = select(Lead).where(Lead.workspace_id == context.workspace_id)
        if context.date_from:
            query = query.where(Lead.created_at >= context.date_from)
        if context.date_to:
            query = query.where(Lead.created_at <= context.date_to)
        if context.source:
            query = query.where(Lead.source == context.source)
        leads = db.scalars(query.order_by(Lead.created_at.asc())).all()
        if not context.user_id and not context.document_id:
            return leads
        filtered: list[Lead] = []
        event_session_ids = {event.chat_session_id for event in self.analytics_events(db, context) if event.chat_session_id}
        for lead in leads:
            if context.document_id and lead.chat_session_id not in event_session_ids:
                continue
            filtered.append(lead)
        return filtered

    def _load_unresolved_questions(self, db: Session, context: MetricsContext) -> list[UnresolvedQuestion]:
        query = select(UnresolvedQuestion).where(UnresolvedQuestion.workspace_id == context.workspace_id)
        if context.date_from:
            query = query.where(UnresolvedQuestion.created_at >= context.date_from)
        if context.date_to:
            query = query.where(UnresolvedQuestion.created_at <= context.date_to)
        rows = db.scalars(query.order_by(UnresolvedQuestion.created_at.asc())).all()
        if not context.document_id and not context.source and not context.user_id:
            return rows
        events = self.analytics_events(db, context, event_type="unanswered_question")
        allowed_message_ids = {event.properties_json.get("message_id") for event in events if event.properties_json}
        return [row for row in rows if str(row.chat_message_id) in allowed_message_ids or row.chat_message_id in allowed_message_ids]

    def _event_matches_filters(self, event: AnalyticsEvent, context: MetricsContext) -> bool:
        props = event.properties_json or {}
        if context.source:
            if props.get("source") != context.source:
                return False
        if context.document_id:
            target = str(context.document_id)
            document_ids = {str(item) for item in props.get("document_ids", []) if item}
            if props.get("document_id"):
                document_ids.add(str(props.get("document_id")))
            citations = props.get("citations") or []
            for citation in citations:
                if citation.get("document_id"):
                    document_ids.add(str(citation.get("document_id")))
            if target not in document_ids:
                return False
        return True

    def _format_bucket(self, value: datetime | None, granularity: str) -> str:
        if value is None:
            return "unknown"
        aware_value = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        if granularity == "month":
            return aware_value.strftime("%Y-%m")
        if granularity == "week":
            iso_year, iso_week, _ = aware_value.isocalendar()
            return f"{iso_year}-W{iso_week:02d}"
        return aware_value.strftime("%Y-%m-%d")

