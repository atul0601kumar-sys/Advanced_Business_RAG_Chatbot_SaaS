import io
import unittest
from zipfile import ZipFile

from app.services.text_extractor import extract_text


def build_docx_bytes(paragraphs: list[str], table_rows: list[list[str]] | None = None) -> bytes:
    buffer = io.BytesIO()
    table_xml = ""
    if table_rows:
        rendered_rows = "".join(
            "<w:tr>"
            + "".join(f"<w:tc><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>" for cell in row)
            + "</w:tr>"
            for row in table_rows
        )
        table_xml = f"<w:tbl>{rendered_rows}</w:tbl>"

    body_xml = "".join(f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>" for paragraph in paragraphs) + table_xml

    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Default Extension="xml" ContentType="application/xml"/>
              <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
              <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
              <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
            </Types>""",
        )
        archive.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>{body_xml}</w:body>
            </w:document>""",
        )
        archive.writestr(
            "docProps/core.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties">
              <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Demo DOCX</dc:title>
            </cp:coreProperties>""",
        )
    return buffer.getvalue()


def build_pdf_bytes() -> bytes:
    return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Count 3 /Kids [3 0 R 4 0 R 5 0 R] >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /Contents 6 0 R >> endobj
4 0 obj << /Type /Page /Parent 2 0 R /Contents 7 0 R >> endobj
5 0 obj << /Type /Page /Parent 2 0 R /Contents 8 0 R >> endobj
6 0 obj << /Length 88 >> stream
BT /F1 12 Tf 72 720 Td (Company Header) Tj ET
BT /F1 12 Tf 72 700 Td (Page One Text) Tj ET
BT /F1 12 Tf 72 680 Td (Company Footer) Tj ET
endstream endobj
7 0 obj << /Length 88 >> stream
BT /F1 12 Tf 72 720 Td (Company Header) Tj ET
BT /F1 12 Tf 72 700 Td (Page Two Text) Tj ET
BT /F1 12 Tf 72 680 Td (Company Footer) Tj ET
endstream endobj
8 0 obj << /Length 90 >> stream
BT /F1 12 Tf 72 720 Td (Company Header) Tj ET
BT /F1 12 Tf 72 700 Td (Page Three Text) Tj ET
BT /F1 12 Tf 72 680 Td (Company Footer) Tj ET
endstream endobj
9 0 obj << /Title (Demo PDF) /Author (Codex) >> endobj
trailer << /Root 1 0 R /Info 9 0 R >>
%%EOF"""


class TextExtractionTests(unittest.TestCase):
    def test_txt_extraction_preserves_paragraphs(self) -> None:
        extracted = extract_text("notes.txt", "text/plain", b"hello world\n\nsecond paragraph")
        self.assertEqual(len(extracted.sections), 2)
        self.assertEqual(extracted.metadata["file_type"], "txt")
        self.assertIn("second paragraph", extracted.cleaned_text)

    def test_csv_extraction_preserves_headers_and_rows(self) -> None:
        extracted = extract_text("rows.csv", "text/csv", b"name,role\nAarav,admin\nNina,viewer")
        self.assertEqual(extracted.metadata["column_count"], 2)
        self.assertEqual(extracted.sections[0].section_type, "header")
        self.assertIn("Aarav | admin", extracted.cleaned_text)

    def test_docx_extraction_preserves_structure(self) -> None:
        extracted = extract_text(
            "demo.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            build_docx_bytes(["Overview paragraph", "Another section"], [["Metric", "Value"], ["ARR", "$1M"]]),
        )
        section_types = [section.section_type for section in extracted.sections]
        self.assertIn("paragraph", section_types)
        self.assertIn("table", section_types)
        self.assertEqual(extracted.metadata["file_type"], "docx")

    def test_pdf_extraction_preserves_page_numbers_and_removes_repeated_noise(self) -> None:
        extracted = extract_text("demo.pdf", "application/pdf", build_pdf_bytes())
        page_numbers = [section.page_number for section in extracted.sections]
        self.assertEqual(page_numbers, [1, 2, 3])
        self.assertNotIn("Company Header", extracted.cleaned_text)
        self.assertIn("Page Two Text", extracted.cleaned_text)


if __name__ == "__main__":
    unittest.main()
