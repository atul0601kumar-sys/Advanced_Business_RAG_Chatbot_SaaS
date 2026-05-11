from __future__ import annotations

from typing import Any

from app.services.csv_builder import CSVBuilder
from app.services.pdf_builder import PDFBuilder


class ReportGenerator:
    def __init__(
        self,
        csv_builder: CSVBuilder | None = None,
        pdf_builder: PDFBuilder | None = None,
    ) -> None:
        self.csv_builder = csv_builder or CSVBuilder()
        self.pdf_builder = pdf_builder or PDFBuilder()

    def to_csv(self, payload: dict[str, Any]) -> str:
        return self.csv_builder.flatten_payload(payload)

    def build_table_csv(self, rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
        return self.csv_builder.build_bytes(rows, fieldnames)

    def build_table_pdf(
        self,
        *,
        title: str,
        subtitle: str,
        generated_at,
        summary_items: list[tuple[str, str]],
        filter_items: list[tuple[str, str]],
        column_titles: list[str],
        rows: list[list[str]],
    ) -> bytes:
        return self.pdf_builder.build_table_report(
            title=title,
            subtitle=subtitle,
            generated_at=generated_at,
            summary_items=summary_items,
            filter_items=filter_items,
            column_titles=column_titles,
            rows=rows,
        )

    def build_analytics_pdf(self, report: dict[str, Any]) -> bytes:
        return self.pdf_builder.build_analytics_report(report)

    def build_analytics_csv_rows(self, report: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        overview = report["overview"]
        performance = report["performance"]
        leads = report["leads"]
        chats = report["chats"]
        queries = report["queries"]

        for card in overview["metric_cards"]:
            rows.append(
                {
                    "section": "overview_metrics",
                    "label": card["label"],
                    "value": card["display_value"],
                    "description": card.get("hint"),
                    "bucket": "",
                    "secondary_value": "",
                    "meta": "",
                }
            )
        for point in overview["daily_chat_volume"]:
            rows.append(
                {
                    "section": "daily_chat_volume",
                    "label": point.get("label") or point.get("bucket"),
                    "value": point.get("value"),
                    "description": "Daily chat sessions",
                    "bucket": point.get("bucket"),
                    "secondary_value": point.get("secondary_value"),
                    "meta": "",
                }
            )
        for point in overview["daily_lead_volume"]:
            rows.append(
                {
                    "section": "daily_lead_volume",
                    "label": point.get("label") or point.get("bucket"),
                    "value": point.get("value"),
                    "description": "Daily lead volume",
                    "bucket": point.get("bucket"),
                    "secondary_value": point.get("secondary_value"),
                    "meta": "",
                }
            )
        for item in leads["funnel"]:
            rows.append(
                {
                    "section": "lead_funnel",
                    "label": item["label"],
                    "value": item["value"],
                    "description": item.get("hint"),
                    "bucket": "",
                    "secondary_value": "",
                    "meta": "",
                }
            )
        for item in performance["alerts"]:
            rows.append(
                {
                    "section": "performance_alerts",
                    "label": item["title"],
                    "value": item["severity"],
                    "description": item["description"],
                    "bucket": "",
                    "secondary_value": "",
                    "meta": "",
                }
            )
        for item in queries["most_asked_questions"]:
            rows.append(
                {
                    "section": "top_queries",
                    "label": item["query"],
                    "value": item["count"],
                    "description": "Most asked query",
                    "bucket": "",
                    "secondary_value": item.get("share"),
                    "meta": item.get("last_seen_at"),
                }
            )
        rows.append(
            {
                "section": "summary",
                "label": "retrieval_success_rate",
                "value": performance["retrieval_success_rate"],
                "description": "Percent of responses with successful retrieval",
                "bucket": "",
                "secondary_value": "",
                "meta": "",
            }
        )
        rows.append(
            {
                "section": "summary",
                "label": "messages_per_session",
                "value": chats["messages_per_session"],
                "description": "Average messages per session",
                "bucket": "",
                "secondary_value": "",
                "meta": "",
            }
        )
        return rows
