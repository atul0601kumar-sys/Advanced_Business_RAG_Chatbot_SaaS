from __future__ import annotations

import base64
from io import BytesIO

from reportlab.pdfgen import canvas

SAMPLE_TEXT = """Q1 revenue reached 18 percent year over year growth.

Customer onboarding time dropped from 14 days to 9 days after workflow automation.

The enterprise pipeline improved because demo follow-ups and sales handoff were standardized.
"""

SAMPLE_CHAT_QUERY = "What changed in onboarding and revenue this quarter?"

SAMPLE_LEAD = {
    "name": "Taylor Morgan",
    "email": "taylor@example.com",
    "company": "Northwind Finance",
    "phone": "+1-555-100-2000",
    "use_case": "Need rollout support for a revenue assistant",
    "message": "Please contact me about pricing and onboarding.",
}


def sample_text_bytes() -> bytes:
    return SAMPLE_TEXT.encode("utf-8")


def sample_text_base64() -> str:
    return base64.b64encode(sample_text_bytes()).decode("utf-8")


def sample_pdf_bytes() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 760, "Q1 Revenue Report")
    pdf.drawString(72, 730, "Revenue grew 18 percent year over year.")
    pdf.drawString(72, 700, "Customer onboarding time dropped to 9 days.")
    pdf.showPage()
    pdf.drawString(72, 760, "Pipeline Notes")
    pdf.drawString(72, 730, "Enterprise pipeline improved with standardized follow-ups.")
    pdf.save()
    return buffer.getvalue()


def sample_pdf_base64() -> str:
    return base64.b64encode(sample_pdf_bytes()).decode("utf-8")
