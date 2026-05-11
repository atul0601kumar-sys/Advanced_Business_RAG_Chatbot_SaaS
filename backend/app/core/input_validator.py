from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, status

PROMPT_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b",
        r"\breveal\s+(the\s+)?(system prompt|developer message|hidden prompt|secret|credentials?|api keys?|tokens?)\b",
        r"\bshow\s+(the\s+)?(system prompt|developer message|hidden instructions?)\b",
        r"\bact\s+as\s+(the\s+)?(system|developer)\b",
        r"\bdo\s+not\s+follow\s+(the\s+)?(previous|above)\s+instructions?\b",
    )
]
SCRIPT_TAG_PATTERN = re.compile(r"<\s*script\b", re.IGNORECASE)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
PRIVATE_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
EXECUTABLE_SIGNATURES = (
    b"MZ",
    b"\x7fELF",
    b"#!",
    b"\xcf\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
)


@dataclass(frozen=True)
class SanitizedPrompt:
    text: str
    was_modified: bool
    blocked_signals: list[str]


def sanitize_text(value: str | None, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    cleaned = CONTROL_CHAR_PATTERN.sub("", value).replace("\r\n", "\n").strip()
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if max_length is not None:
        cleaned = cleaned[:max_length]
    return cleaned


def sanitize_prompt_input(value: str) -> SanitizedPrompt:
    cleaned = sanitize_text(value, max_length=8000) or ""
    blocked_signals: list[str] = []
    mutated = cleaned
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(mutated):
            blocked_signals.append(pattern.pattern)
            mutated = pattern.sub("[redacted unsafe instruction]", mutated)
    if SCRIPT_TAG_PATTERN.search(mutated):
        blocked_signals.append("script_tag")
        mutated = SCRIPT_TAG_PATTERN.sub("&lt;script", mutated)
    mutated = re.sub(r"\s{2,}", " ", mutated).strip()
    return SanitizedPrompt(text=mutated, was_modified=mutated != cleaned, blocked_signals=blocked_signals)


def validate_no_xss(value: str | None, *, field_name: str) -> str | None:
    cleaned = sanitize_text(value)
    if cleaned and SCRIPT_TAG_PATTERN.search(cleaned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} contains disallowed script markup.",
        )
    return cleaned


def _is_private_host(hostname: str) -> bool:
    normalized = hostname.strip().lower()
    if not normalized or normalized in PRIVATE_HOSTNAMES or normalized.endswith(".local") or normalized.endswith(".internal"):
        return True
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast


def validate_webhook_url(url: str) -> str:
    parsed = urlparse((sanitize_text(url, max_length=500) or ""))
    if parsed.scheme not in {"https"}:
        raise ValueError("Webhook URLs must use HTTPS.")
    if not parsed.hostname:
        raise ValueError("Webhook URLs must include a valid host.")
    if parsed.username or parsed.password:
        raise ValueError("Webhook URLs must not embed credentials.")
    if _is_private_host(parsed.hostname):
        raise ValueError("Webhook URLs cannot target localhost or private network hosts.")
    return parsed.geturl()


def validate_origin_value(origin: str) -> str:
    parsed = urlparse((sanitize_text(origin, max_length=500) or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Origin must use http or https and include a host.")
    if parsed.username or parsed.password:
        raise ValueError("Origins cannot include credentials.")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def validate_file_signature(filename: str, mime_type: str, file_bytes: bytes) -> None:
    extension = Path(filename).suffix.lower()
    for signature in EXECUTABLE_SIGNATURES:
        if file_bytes.startswith(signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Executable uploads are not allowed.",
            )
    if extension == ".pdf" and not file_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded PDF content is invalid.")
    if extension == ".docx" and not file_bytes.startswith(b"PK"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded DOCX content is invalid.")
    if extension in {".txt", ".csv"}:
        sample = file_bytes[:1024]
        if b"\x00" in sample:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Binary file uploads are not allowed.")
    if mime_type == "application/octet-stream" and extension not in {".pdf", ".docx"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generic binary MIME types are only accepted for verified PDF or DOCX uploads.",
        )


def sanitize_json_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_json_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_payload(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value, max_length=5000) or ""
    return value
