from __future__ import annotations

import base64
import csv
import hashlib
import io
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile

from fastapi import HTTPException, status

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - exercised in environments without the optional dependency
    PdfReader = None

from app.core.config import get_settings
from app.core.input_validator import sanitize_text, validate_file_signature
from app.services.file_storage import get_storage_service

settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "application/csv",
    "application/octet-stream",
}


@dataclass
class ExtractedSection:
    text: str
    order: int
    section_type: str
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDocument:
    full_text: str
    cleaned_text: str
    sections: list[ExtractedSection]
    metadata: dict[str, Any]


def sanitize_filename(filename: str) -> str:
    normalized = sanitize_text(filename, max_length=255) or ""
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", normalized).strip("._")
    return safe_name or "document"


def validate_upload(filename: str, mime_type: str, file_size: int) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Supported formats: PDF, DOCX, TXT, CSV.",
        )
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported MIME type for uploaded file.",
        )
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is too large. Maximum size is {settings.max_upload_size_mb} MB.",
        )
    return extension


def decode_content(content_base64: str) -> bytes:
    try:
        return base64.b64decode(content_base64.encode("utf-8"), validate=True)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file content is not valid base64.",
        ) from exc


def calculate_checksum(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def store_original_file(workspace_id: str, document_id: str, filename: str, file_bytes: bytes) -> str:
    return get_storage_service(settings).store_bytes(
        object_group="uploads",
        workspace_id=workspace_id,
        object_id=document_id,
        filename=sanitize_filename(filename),
        content=file_bytes,
    )


def remove_original_file(storage_path: str | None) -> None:
    get_storage_service(settings).delete(storage_path)


def read_stored_file(storage_path: str) -> bytes:
    return get_storage_service(settings).load_bytes(storage_path)


def stored_file_exists(storage_path: str | None) -> bool:
    return get_storage_service(settings).exists(storage_path)


def generate_stored_file_url(storage_path: str | None, *, download_name: str | None = None) -> str | None:
    return get_storage_service(settings).generate_signed_url(storage_path, download_name=download_name)


def extract_text(filename: str, mime_type: str, file_bytes: bytes) -> ExtractedDocument:
    extension = validate_upload(filename, mime_type, len(file_bytes))
    validate_file_signature(filename, mime_type, file_bytes)
    if extension == ".txt":
        return _extract_txt(file_bytes, filename)
    if extension == ".csv":
        return _extract_csv(file_bytes, filename)
    if extension == ".docx":
        return _extract_docx(file_bytes, filename)
    if extension == ".pdf":
        return _extract_pdf(file_bytes, filename)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type.")


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _remove_repeated_pdf_noise(lines_per_page: list[list[str]]) -> list[list[str]]:
    if len(lines_per_page) < 2:
        return lines_per_page

    header_counts: dict[str, int] = {}
    footer_counts: dict[str, int] = {}
    for lines in lines_per_page:
        if lines:
            header_counts[lines[0]] = header_counts.get(lines[0], 0) + 1
            footer_counts[lines[-1]] = footer_counts.get(lines[-1], 0) + 1

    min_repetition = max(2, len(lines_per_page) // 2)
    repeated_headers = {line for line, count in header_counts.items() if count >= min_repetition}
    repeated_footers = {line for line, count in footer_counts.items() if count >= min_repetition}

    cleaned_pages: list[list[str]] = []
    for lines in lines_per_page:
        cleaned = list(lines)
        if cleaned and cleaned[0] in repeated_headers:
            cleaned = cleaned[1:]
        if cleaned and cleaned[-1] in repeated_footers:
            cleaned = cleaned[:-1]
        cleaned_pages.append(cleaned)
    return cleaned_pages


def _collapse_lines(lines: list[str]) -> str:
    cleaned_lines = [_clean_pdf_line(line) for line in lines if line.strip()]
    cleaned_lines = [line for line in cleaned_lines if line]
    return _normalize_whitespace("\n".join(cleaned_lines))


def _clean_pdf_line(line: str) -> str:
    cleaned = " ".join(line.strip().split())
    if not cleaned:
        return ""
    cleaned = re.sub(r"(\w)-\s+(\w)", r"\1\2", cleaned)
    if _looks_like_outline_line(cleaned):
        return ""
    return cleaned


def _looks_like_outline_line(line: str) -> bool:
    lowered = line.lower()
    section_markers = len(re.findall(r"\b\d+(?:\.\d+)+\b", line))
    toc_keywords = {"contents", "chapter", "lesson", "unit", "summary", "objective"}
    uppercase_letters = sum(1 for char in line if char.isalpha() and char.isupper())
    lowercase_letters = sum(1 for char in line if char.isalpha() and char.islower())
    alpha_letters = uppercase_letters + lowercase_letters
    uppercase_ratio = (uppercase_letters / alpha_letters) if alpha_letters else 0.0
    is_short_heading = len(line.split()) <= 14 and uppercase_ratio >= 0.45
    return (
        section_markers >= 3
        or ("table of contents" in lowered)
        or (any(keyword in lowered for keyword in toc_keywords) and section_markers >= 1)
        or (is_short_heading and section_markers >= 1)
    )


def _extract_txt(file_bytes: bytes, filename: str) -> ExtractedDocument:
    raw_text = file_bytes.decode("utf-8", errors="ignore")
    cleaned_text = _normalize_whitespace(raw_text)
    paragraphs = [paragraph.strip() for paragraph in cleaned_text.split("\n\n") if paragraph.strip()]
    sections = [
        ExtractedSection(text=paragraph, order=index, section_type="paragraph")
        for index, paragraph in enumerate(paragraphs)
    ]
    metadata = {
        "original_filename": filename,
        "file_type": "txt",
        "line_count": len(cleaned_text.splitlines()),
        "character_count": len(cleaned_text),
    }
    return ExtractedDocument(raw_text, cleaned_text, sections, metadata)


def _extract_csv(file_bytes: bytes, filename: str) -> ExtractedDocument:
    raw_text = file_bytes.decode("utf-8-sig", errors="ignore")
    reader = csv.reader(io.StringIO(raw_text))
    rows = list(reader)
    header = rows[0] if rows else []
    content_rows = rows[1:] if len(rows) > 1 else []

    sections: list[ExtractedSection] = []
    if header:
        sections.append(
            ExtractedSection(
                text=" | ".join(header),
                order=0,
                section_type="header",
                metadata={"columns": header},
            )
        )

    batch_size = 50
    for batch_index in range(0, len(content_rows), batch_size):
        batch_rows = content_rows[batch_index : batch_index + batch_size]
        section_text = "\n".join(" | ".join(row) for row in batch_rows)
        sections.append(
            ExtractedSection(
                text=section_text,
                order=len(sections),
                section_type="table_rows",
                metadata={"row_start": batch_index + 1, "row_end": batch_index + len(batch_rows)},
            )
        )

    cleaned_text = _normalize_whitespace("\n\n".join(section.text for section in sections))
    metadata = {
        "original_filename": filename,
        "file_type": "csv",
        "row_count": len(content_rows),
        "column_count": len(header),
        "headers": header,
    }
    return ExtractedDocument(raw_text, cleaned_text, sections, metadata)


def _extract_docx(file_bytes: bytes, filename: str) -> ExtractedDocument:
    with ZipFile(io.BytesIO(file_bytes)) as archive:
        document_xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(document_xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        body = root.find("w:body", namespace)
        sections: list[ExtractedSection] = []
        order = 0

        if body is not None:
            for child in list(body):
                tag = child.tag.split("}")[-1]
                if tag == "p":
                    paragraph_text = _normalize_whitespace("".join(child.itertext()))
                    if paragraph_text:
                        sections.append(
                            ExtractedSection(
                                text=paragraph_text,
                                order=order,
                                section_type="paragraph",
                            )
                        )
                        order += 1
                elif tag == "tbl":
                    rows: list[str] = []
                    for row in child.findall(".//w:tr", namespace):
                        cells = [
                            _normalize_whitespace("".join(cell.itertext()))
                            for cell in row.findall(".//w:tc", namespace)
                        ]
                        cells = [cell for cell in cells if cell]
                        if cells:
                            rows.append(" | ".join(cells))
                    if rows:
                        sections.append(
                            ExtractedSection(
                                text="\n".join(rows),
                                order=order,
                                section_type="table",
                                metadata={"row_count": len(rows)},
                            )
                        )
                        order += 1

        core_metadata: dict[str, str] = {}
        if "docProps/core.xml" in archive.namelist():
            core_root = ElementTree.fromstring(archive.read("docProps/core.xml"))
            for child in core_root:
                tag = child.tag.split("}")[-1]
                if child.text:
                    core_metadata[tag] = child.text

    raw_text = "\n\n".join(section.text for section in sections)
    cleaned_text = _normalize_whitespace(raw_text)
    metadata = {
        "original_filename": filename,
        "file_type": "docx",
        "paragraph_count": len([section for section in sections if section.section_type == "paragraph"]),
        "table_count": len([section for section in sections if section.section_type == "table"]),
        "core_metadata": core_metadata,
    }
    return ExtractedDocument(raw_text, cleaned_text, sections, metadata)


def _extract_pdf_info(text_blob: str) -> dict[str, str]:
    info: dict[str, str] = {}
    for key in ("Title", "Author", "Subject", "Creator", "Producer"):
        match = re.search(rf"/{key}\s*\((.*?)\)", text_blob, re.S)
        if match:
            info[key.lower()] = _decode_pdf_escaped_text(match.group(1).encode("latin-1"))
    return info


def _decode_pdf_escaped_text(data: bytes) -> str:
    text = data.decode("latin-1", errors="ignore")
    text = text.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), text)


def _extract_pdf_stream_text(stream_bytes: bytes) -> str:
    if b"/FlateDecode" in stream_bytes:
        try:
            stream_bytes = zlib.decompress(stream_bytes)
        except zlib.error:
            pass

    text_segments: list[str] = []
    for match in re.finditer(rb"\((.*?)(?<!\\)\)\s*Tj", stream_bytes, re.S):
        text_segments.append(_decode_pdf_escaped_text(match.group(1)))
    for match in re.finditer(rb"\[(.*?)\]\s*TJ", stream_bytes, re.S):
        parts = re.findall(rb"\((.*?)(?<!\\)\)", match.group(1), re.S)
        if parts:
            text_segments.append("".join(_decode_pdf_escaped_text(part) for part in parts))
    return "\n".join(segment.strip() for segment in text_segments if segment.strip())


def _extract_pdf(file_bytes: bytes, filename: str) -> ExtractedDocument:
    extracted_with_library = _extract_pdf_with_pypdf(file_bytes, filename)
    if extracted_with_library and extracted_with_library.sections:
        return extracted_with_library

    text_blob = file_bytes.decode("latin-1", errors="ignore")
    page_matches = list(re.finditer(rb"/Type\s*/Page\b", file_bytes))
    object_map = {
        match.group(1).decode("ascii"): match.group(2)
        for match in re.finditer(rb"(\d+)\s+\d+\s+obj(.*?)endobj", file_bytes, re.S)
    }

    pages: list[list[str]] = []
    for page_number, page_match in enumerate(page_matches, start=1):
        next_start = page_matches[page_number].start() if page_number < len(page_matches) else len(file_bytes)
        page_block = file_bytes[page_match.start() : next_start]
        content_refs = re.findall(rb"/Contents\s+(?:\[(.*?)\]|(\d+\s+\d+\s+R))", page_block, re.S)
        refs: list[str] = []
        for grouped_refs, single_ref in content_refs:
            ref_block = grouped_refs or single_ref
            refs.extend(match.decode("ascii") for match in re.findall(rb"(\d+)\s+\d+\s+R", ref_block))

        page_lines: list[str] = []
        for ref in refs:
            obj_body = object_map.get(ref)
            if not obj_body:
                continue
            stream_match = re.search(rb"stream\r?\n(.*?)\r?\nendstream", obj_body, re.S)
            if not stream_match:
                continue
            page_text = _extract_pdf_stream_text(stream_match.group(1))
            page_lines.extend(line for line in page_text.splitlines() if line.strip())
        pages.append(page_lines)

    cleaned_pages = _remove_repeated_pdf_noise(pages)
    sections: list[ExtractedSection] = []
    for index, lines in enumerate(cleaned_pages, start=1):
        page_text = _collapse_lines(lines)
        if page_text:
            sections.append(
                ExtractedSection(
                    text=page_text,
                    order=len(sections),
                    section_type="page",
                    page_number=index,
                )
            )

    raw_text = "\n\n".join(section.text for section in sections)
    cleaned_text = _normalize_whitespace(raw_text)
    metadata = {
        "original_filename": filename,
        "file_type": "pdf",
        "page_count": len(page_matches),
        "pdf_info": _extract_pdf_info(text_blob),
        "ocr_recommended": not bool(sections),
    }
    return ExtractedDocument(raw_text, cleaned_text, sections, metadata)


def _extract_pdf_with_pypdf(file_bytes: bytes, filename: str) -> ExtractedDocument | None:
    if PdfReader is None:
        return None

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception:  # noqa: BLE001
        return None

    pages: list[list[str]] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            page_text = ""
        pages.append([line for line in page_text.splitlines() if line.strip()])

    cleaned_pages = _remove_repeated_pdf_noise(pages)
    sections: list[ExtractedSection] = []
    for index, lines in enumerate(cleaned_pages, start=1):
        page_text = _collapse_lines(lines)
        if page_text:
            sections.append(
                ExtractedSection(
                    text=page_text,
                    order=len(sections),
                    section_type="page",
                    page_number=index,
                )
            )

    raw_text = "\n\n".join(section.text for section in sections)
    cleaned_text = _normalize_whitespace(raw_text)
    metadata = {
        "original_filename": filename,
        "file_type": "pdf",
        "page_count": len(reader.pages),
        "pdf_info": {
            str(key).lstrip("/").lower(): str(value)
            for key, value in (reader.metadata or {}).items()
            if value is not None
        },
        "extraction_strategy": "pypdf",
        "ocr_recommended": not bool(sections),
    }
    return ExtractedDocument(raw_text, cleaned_text, sections, metadata)
