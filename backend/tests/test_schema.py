import unittest

from app.db.base import Base
from app.models import *  # noqa: F403


class SchemaMetadataTests(unittest.TestCase):
    def test_expected_tables_exist(self) -> None:
        expected_tables = {
            "users",
            "workspaces",
            "workspace_members",
            "documents",
            "document_chunks",
            "website_sources",
            "chat_sessions",
            "chat_messages",
            "leads",
            "feedback",
            "notification_jobs",
            "notification_logs",
            "analytics_events",
            "unresolved_questions",
            "chatbot_settings",
            "access_logs",
            "audit_logs",
            "integration_connections",
            "integration_deliveries",
        }
        self.assertTrue(expected_tables.issubset(Base.metadata.tables.keys()))


if __name__ == "__main__":
    unittest.main()
