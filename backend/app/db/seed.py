from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AccessLog,
    AnalyticsEvent,
    ChatMessage,
    ChatSession,
    ChatbotSetting,
    Document,
    DocumentChunk,
    Feedback,
    Lead,
    UnresolvedQuestion,
    User,
    WebsiteSource,
    Workspace,
    WorkspaceMember,
)


def seed_demo_data(db: Session) -> None:
    existing_user = db.scalar(select(User).where(User.email == "demo.owner@example.com"))
    if existing_user:
        return

    owner = User(
        email="demo.owner@example.com",
        full_name="Demo Owner",
        password_hash=hash_password("DemoPassword123!"),
        is_active=True,
        is_superuser=True,
    )
    analyst = User(
        email="demo.analyst@example.com",
        full_name="Demo Analyst",
        password_hash=hash_password("DemoPassword123!"),
        is_active=True,
        is_superuser=False,
    )
    db.add_all([owner, analyst])
    db.flush()

    workspace = Workspace(
        name="Demo Workspace",
        slug="demo-workspace",
        description="Demo tenant for local development and schema validation.",
        status="active",
        owner_user_id=owner.id,
    )
    db.add(workspace)
    db.flush()

    db.add_all(
        [
            WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role="admin"),
            WorkspaceMember(workspace_id=workspace.id, user_id=analyst.id, role="team_member"),
        ]
    )

    document = Document(
        workspace_id=workspace.id,
        uploaded_by_user_id=owner.id,
        title="Q2 Product Overview",
        source_type="upload",
        storage_path="storage/uploads/demo-product-overview.pdf",
        mime_type="application/pdf",
        file_size=245760,
        checksum="demo-checksum-001",
        ingestion_status="indexed",
        summary="Overview of product positioning, pricing, and onboarding.",
        metadata_json={"department": "sales", "language": "en"},
    )
    db.add(document)
    db.flush()

    chunk_one = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="The product is positioned for mid-market teams that need searchable business knowledge.",
        token_count=16,
        embedding_model="text-embedding-3-small",
        qdrant_point_id="demo-point-001",
        metadata_json={"page": 1},
    )
    chunk_two = DocumentChunk(
        document_id=document.id,
        chunk_index=1,
        content="Pricing begins with a base subscription and usage-based overages for advanced analytics.",
        token_count=15,
        embedding_model="text-embedding-3-small",
        qdrant_point_id="demo-point-002",
        metadata_json={"page": 2},
    )
    db.add_all([chunk_one, chunk_two])

    website_source = WebsiteSource(
        workspace_id=workspace.id,
        document_id=document.id,
        url="https://example.com/pricing",
        title="Pricing Page",
        crawl_status="indexed",
        last_crawled_at=datetime.now(UTC),
        checksum="website-demo-checksum",
        content_snapshot="Pricing details for demo testing.",
        metadata_json={"source": "marketing-site"},
    )
    db.add(website_source)

    chat_session = ChatSession(
        workspace_id=workspace.id,
        user_id=analyst.id,
        title="Pricing FAQ Session",
        status="active",
        channel="web",
        last_message_at=datetime.now(UTC),
        session_summary="Conversation about pricing questions.",
        needs_human_review=True,
    )
    db.add(chat_session)
    db.flush()

    user_message = ChatMessage(
        chat_session_id=chat_session.id,
        role="user",
        content="What is the starting price for the product?",
    )
    assistant_message = ChatMessage(
        chat_session_id=chat_session.id,
        role="assistant",
        content="The document says pricing starts with a base subscription plus usage-based analytics overages.",
        citations_json=[{"document_title": document.title, "chunk_index": 1}],
        token_usage_json={"prompt_tokens": 120, "completion_tokens": 28, "total_tokens": 148},
        response_time_ms=950,
    )
    db.add_all([user_message, assistant_message])
    db.flush()

    db.add(
        Lead(
            workspace_id=workspace.id,
            chat_session_id=chat_session.id,
            name="Priya Sharma",
            email="priya@example.com",
            company="Example Corp",
            use_case="demo",
            message="Please contact me about enterprise pricing.",
            status="new",
            source="chatbot",
            priority="high",
            tag="sales",
            high_intent=True,
            notes="Requested enterprise pricing follow-up.",
            metadata_json={"source": "chatbot", "priority_score": 9},
        )
    )

    db.add(
        Feedback(
            workspace_id=workspace.id,
            chat_session_id=chat_session.id,
            chat_message_id=assistant_message.id,
            user_id=analyst.id,
            rating=5,
            category="answer_quality",
            comment="Helpful grounded response.",
        )
    )

    db.add(
        AnalyticsEvent(
            workspace_id=workspace.id,
            user_id=analyst.id,
            chat_session_id=chat_session.id,
            event_type="chat",
            event_name="message_answered",
            properties_json={"model": "gpt-4.1-mini", "sources_used": 1},
        )
    )

    db.add(
        UnresolvedQuestion(
            workspace_id=workspace.id,
            chat_session_id=chat_session.id,
            chat_message_id=user_message.id,
            question="Do you offer annual billing discounts?",
            normalized_question="annual billing discounts",
            reason="not_found_in_knowledge_base",
            status="open",
        )
    )

    db.add(
        ChatbotSetting(
            workspace_id=workspace.id,
            display_name="Demo Assistant",
            welcome_message="Ask about documents, pricing, and onboarding.",
            system_prompt="Answer using the workspace knowledge base and cite sources.",
            model_name="gpt-4.1-mini",
            temperature=0.2,
            max_context_chunks=6,
            lead_capture_enabled=True,
            lead_capture_on_first_message=False,
            lead_capture_after_message_count=4,
            lead_capture_on_low_confidence=True,
            schedule_call_enabled=True,
            admin_notification_email="owner@example.com",
            allowed_domains_json=["localhost", "example.com"],
        )
    )

    db.add(
        AccessLog(
            workspace_id=workspace.id,
            user_id=analyst.id,
            path="/api/v1/chat/query",
            method="POST",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="demo-seed-client",
            request_id="seed-request-001",
            latency_ms=410,
        )
    )

    db.commit()
