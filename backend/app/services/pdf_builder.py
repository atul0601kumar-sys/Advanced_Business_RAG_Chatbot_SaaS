from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class PDFBuilder:
    def build_table_report(
        self,
        *,
        title: str,
        subtitle: str,
        generated_at: datetime | None,
        summary_items: list[tuple[str, str]],
        filter_items: list[tuple[str, str]],
        column_titles: list[str],
        rows: list[list[str]],
    ) -> bytes:
        self._require_reportlab()
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer, doc, styles = self._build_document("table-report.pdf")
        story = [
            Spacer(1, 24),
            Paragraph(title, styles["Title"]),
            Spacer(1, 10),
            Paragraph(subtitle, styles["BodyText"]),
            Spacer(1, 20),
            Paragraph("Summary", styles["Heading2"]),
            self._summary_table(summary_items),
            Spacer(1, 16),
            Paragraph("Filters", styles["Heading2"]),
            self._summary_table(filter_items or [("Filters", "No additional filters applied")]),
            PageBreak(),
            Paragraph("Exported Data", styles["Heading2"]),
            Spacer(1, 8),
        ]

        table_data = [column_titles, *rows] if rows else [column_titles, ["No rows matched the selected filters."] + [""] * (len(column_titles) - 1)]
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(table)
        doc.build(story, onFirstPage=self._footer(generated_at), onLaterPages=self._footer(generated_at))
        return buffer.getvalue()

    def build_analytics_report(self, report: dict[str, Any]) -> bytes:
        self._require_reportlab()
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.lib import colors
        from reportlab.platypus import PageBreak, Paragraph, Spacer

        buffer, doc, styles = self._build_document("analytics-report.pdf")
        workspace = report["workspace"]
        date_range = report["date_range"]
        overview = report["overview"]
        performance = report["performance"]
        queries = report["queries"]
        leads = report["leads"]
        chats = report["chats"]

        summary_items = [
            ("Workspace", workspace["name"]),
            ("Workspace slug", workspace["slug"]),
            ("Date range", f'{date_range["from"] or "Beginning"} to {date_range["to"] or "Now"}'),
            ("Generated", report["generated_at"]),
        ]
        kpi_items = [
            ("Total chats", str(overview["metrics"]["total_chats"])),
            ("Total leads", str(overview["metrics"]["total_leads"])),
            ("Conversion rate", f'{overview["metrics"]["conversion_rate"]:.2f}%'),
            ("Avg response time", f'{overview["metrics"]["average_response_time_ms"]:.2f} ms'),
            ("Avg confidence", f'{overview["metrics"]["average_confidence_score"]:.2f}'),
            ("Retrieval success", f'{performance["retrieval_success_rate"]:.2f}%'),
        ]

        story = [
            Spacer(1, 30),
            Paragraph("Advanced Business RAG Chatbot Analytics Report", styles["Title"]),
            Spacer(1, 12),
            Paragraph("Client-ready export covering KPI performance, usage trends, knowledge signals, and AI quality metrics.", styles["BodyText"]),
            Spacer(1, 24),
            Paragraph("Report Summary", styles["Heading2"]),
            self._summary_table(summary_items),
            Spacer(1, 16),
            Paragraph("Key KPIs", styles["Heading2"]),
            self._summary_table(kpi_items),
            PageBreak(),
            Paragraph("Trend Charts", styles["Heading2"]),
            Spacer(1, 10),
            self._line_chart("Daily Chat Volume", overview["daily_chat_volume"], stroke_color="#0284c7"),
            Spacer(1, 14),
            self._line_chart("Daily Lead Volume", overview["daily_lead_volume"], stroke_color="#ea580c"),
            Spacer(1, 14),
            self._bar_chart("Lead Funnel", leads["funnel"], fill_color="#2563eb"),
            PageBreak(),
            Paragraph("Distribution and Performance", styles["Heading2"]),
            Spacer(1, 10),
            self._pie_chart("Confidence Distribution", overview["confidence_distribution"]),
            Spacer(1, 14),
            self._bar_chart("Top Knowledge Sources", queries["top_knowledge_sources"], fill_color="#0f766e"),
            Spacer(1, 14),
            self._bar_chart("Peak Usage Times", chats["peak_usage_times"], fill_color="#7c3aed"),
            PageBreak(),
            Paragraph("Performance Summary", styles["Heading2"]),
            self._summary_table(
                [
                    ("Unanswered queries", str(performance["unanswered_queries"])),
                    ("Failed query count", str(len(performance["failed_queries"]))),
                    ("Messages per session", f'{chats["messages_per_session"]:.2f}'),
                    ("Average session duration", f'{chats["average_session_duration_minutes"]:.2f} minutes'),
                ]
            ),
            Spacer(1, 16),
            Paragraph("Top Queries and Trends", styles["Heading2"]),
            self._top_queries_table(queries["most_asked_questions"]),
            Spacer(1, 16),
            Paragraph("Insights", styles["Heading2"]),
        ]

        insight_items = [*overview["alerts"], *overview["insights"], *leads["insights"], *performance["alerts"], *queries["insights"]]
        if insight_items:
            for item in insight_items:
                story.append(Paragraph(f'<b>{item["title"]}</b>: {item["description"]}', styles["BodyText"]))
                story.append(Spacer(1, 8))
        else:
            story.append(Paragraph("No major insights were produced for the selected range.", styles["BodyText"]))
        doc.build(story, onFirstPage=self._footer(), onLaterPages=self._footer())
        return buffer.getvalue()

    def _build_document(self, filename: str):
        self._require_reportlab()
        from io import BytesIO

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )
        styles = getSampleStyleSheet()
        styles["Title"].fontName = "Helvetica-Bold"
        styles["Title"].fontSize = 24
        styles["Heading2"].fontName = "Helvetica-Bold"
        styles["Heading2"].fontSize = 14
        styles["Heading2"].textColor = "#0f172a"
        styles["BodyText"].fontName = "Helvetica"
        styles["BodyText"].fontSize = 10
        styles["BodyText"].leading = 14
        return buffer, doc, styles

    def _summary_table(self, items: list[tuple[str, str]]):
        self._require_reportlab()
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle

        data = [[label, value] for label, value in items]
        table = Table(data, colWidths=[150, 330])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def _line_chart(self, title: str, points: list[dict[str, Any]], *, stroke_color: str):
        self._require_reportlab()
        from reportlab.graphics.charts.linecharts import HorizontalLineChart
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.lib import colors

        drawing = Drawing(480, 180)
        drawing.add(String(0, 164, title, fontName="Helvetica-Bold", fontSize=11, fillColor=colors.HexColor("#0f172a")))
        chart = HorizontalLineChart()
        chart.x = 42
        chart.y = 24
        chart.height = 110
        chart.width = 390
        chart.data = [[float(item.get("value", 0.0)) for item in points[:10]] or [0.0]]
        chart.lines[0].strokeColor = colors.HexColor(stroke_color)
        chart.lines[0].strokeWidth = 2
        chart.categoryAxis.categoryNames = [item.get("label") or item.get("bucket", "") for item in points[:10]] or [""]
        chart.categoryAxis.labels.boxAnchor = "ne"
        chart.categoryAxis.labels.angle = 30
        chart.valueAxis.valueMin = 0
        chart.valueAxis.forceZero = 1
        drawing.add(chart)
        return drawing

    def _bar_chart(self, title: str, items: list[dict[str, Any]], *, fill_color: str):
        self._require_reportlab()
        from reportlab.graphics.charts.barcharts import VerticalBarChart
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.lib import colors

        drawing = Drawing(480, 190)
        drawing.add(String(0, 174, title, fontName="Helvetica-Bold", fontSize=11, fillColor=colors.HexColor("#0f172a")))
        chart = VerticalBarChart()
        chart.x = 42
        chart.y = 24
        chart.height = 120
        chart.width = 390
        chart.data = [[float(item.get("value", 0.0)) for item in items[:8]] or [0.0]]
        chart.categoryAxis.categoryNames = [item.get("label", "")[:18] for item in items[:8]] or [""]
        chart.categoryAxis.labels.angle = 25
        chart.categoryAxis.labels.boxAnchor = "ne"
        chart.valueAxis.valueMin = 0
        chart.valueAxis.forceZero = 1
        chart.bars[0].fillColor = colors.HexColor(fill_color)
        drawing.add(chart)
        return drawing

    def _pie_chart(self, title: str, items: list[dict[str, Any]]):
        self._require_reportlab()
        from reportlab.graphics.charts.piecharts import Pie
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.lib import colors

        drawing = Drawing(480, 220)
        drawing.add(String(0, 200, title, fontName="Helvetica-Bold", fontSize=11, fillColor=colors.HexColor("#0f172a")))
        pie = Pie()
        pie.x = 110
        pie.y = 24
        pie.width = 180
        pie.height = 140
        pie.data = [max(float(item.get("value", 0.0)), 0.01) for item in items[:5]] or [1.0]
        pie.labels = [item.get("label", "")[:22] for item in items[:5]] or ["No data"]
        palette = ["#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6"]
        for index, slice_color in enumerate(palette[: len(pie.data)]):
            pie.slices[index].fillColor = colors.HexColor(slice_color)
        drawing.add(pie)
        return drawing

    def _top_queries_table(self, items: list[dict[str, Any]]):
        self._require_reportlab()
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle

        rows = [["Query", "Count", "Last Seen"]]
        for item in items[:10]:
            rows.append(
                [
                    item.get("query", ""),
                    str(item.get("count", 0)),
                    item.get("last_seen_at") or "N/A",
                ]
            )
        table = Table(rows, repeatRows=1, colWidths=[290, 70, 120])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def _footer(self, generated_at: datetime | None = None):
        stamp = (generated_at or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")

        def draw(canvas, doc) -> None:
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColorRGB(0.35, 0.4, 0.47)
            canvas.drawString(doc.leftMargin, 18, f"Generated on {stamp}")
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 18, f"Page {canvas.getPageNumber()}")
            canvas.restoreState()

        return draw

    def _require_reportlab(self) -> None:
        try:
            import reportlab  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("PDF exports require the 'reportlab' package in the backend environment.") from exc
