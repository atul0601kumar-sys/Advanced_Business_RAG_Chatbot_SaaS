from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
import urllib.parse

from app.services.text_extractor import ExtractedDocument, ExtractedSection
from app.services.website.content_cleaner import clean_sections, normalize_whitespace, stable_text_key

IGNORED_TAGS = {"script", "style", "nav", "footer", "aside", "noscript", "form", "svg"}
BLOCK_TAGS = {"p", "div", "section", "article", "main", "li", "ul", "ol", "header", "br"}
HEADING_TAGS = {"h1", "h2", "h3"}
NOISE_HINTS = {"nav", "menu", "footer", "sidebar", "advert", "ads", "promo", "cookie", "banner"}


@dataclass
class ExtractedWebPage:
    url: str
    title: str
    text: str
    cleaned_text: str
    sections: list[ExtractedSection]
    metadata: dict[str, Any]
    links: list[str]


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href.strip())


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[ExtractedSection] = []
        self._text_buffer: list[str] = []
        self._current_tag: str | None = None
        self._ignore_depth = 0
        self._order = 0
        self._list_depth = 0
        self.title = ""
        self.metadata: dict[str, Any] = {}
        self._current_heading: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): (value or "") for key, value in attrs}
        if tag in IGNORED_TAGS or self._looks_like_noise(attrs_map):
            self._ignore_depth += 1
            return

        if tag == "title":
            self._current_tag = "title"
            self._text_buffer = []
            return

        if tag == "meta":
            self._consume_meta(attrs_map)
            return

        if tag in {"ul", "ol"}:
            self._list_depth += 1

        if tag in HEADING_TAGS | {"p", "li"}:
            self._flush_buffer()
            self._current_tag = tag
            self._text_buffer = []
            if tag == "li":
                self._text_buffer.append("- ")
            return

        if tag in BLOCK_TAGS:
            self._flush_buffer()

    def handle_endtag(self, tag: str) -> None:
        if self._ignore_depth and (tag in IGNORED_TAGS or tag in {"div", "section", "aside", "footer", "nav", "header"}):
            self._ignore_depth = max(0, self._ignore_depth - 1)
            return

        if tag == "title":
            self.title = normalize_whitespace("".join(self._text_buffer))
            self._current_tag = None
            self._text_buffer = []
            return

        if tag in {"ul", "ol"} and self._list_depth:
            self._list_depth -= 1

        if tag == self._current_tag:
            self._flush_buffer()
            self._current_tag = None
            return

        if tag in BLOCK_TAGS:
            self._flush_buffer()

    def handle_data(self, data: str) -> None:
        if self._ignore_depth or not data.strip():
            return
        self._text_buffer.append(data)

    def _flush_buffer(self) -> None:
        text = normalize_whitespace("".join(self._text_buffer))
        if not text:
            self._text_buffer = []
            return
        if self._current_tag == "title":
            self.title = text
        else:
            section_type = self._current_tag or "paragraph"
            metadata = {"section_heading": self._current_heading} if self._current_heading else {}
            if section_type in HEADING_TAGS:
                self._current_heading = text
                metadata["section_heading"] = text
            self.sections.append(
                ExtractedSection(
                    text=text,
                    order=self._order,
                    section_type=section_type,
                    metadata=metadata,
                )
            )
            self._order += 1
        self._text_buffer = []

    def _looks_like_noise(self, attrs_map: dict[str, str]) -> bool:
        marker = " ".join(
            [
                attrs_map.get("class", ""),
                attrs_map.get("id", ""),
                attrs_map.get("role", ""),
                attrs_map.get("aria-label", ""),
            ]
        ).lower()
        return any(hint in marker for hint in NOISE_HINTS)

    def _consume_meta(self, attrs_map: dict[str, str]) -> None:
        key = (attrs_map.get("name") or attrs_map.get("property") or "").lower()
        content = normalize_whitespace(attrs_map.get("content", ""))
        if not key or not content:
            return
        if key in {"author", "article:author"}:
            self.metadata["author"] = content
        if key in {"article:published_time", "date", "pubdate", "article:modified_time"}:
            self.metadata["date"] = content
        if key in {"description", "og:description"}:
            self.metadata["description"] = content


def extract_clean_web_content(url: str, html_text: str) -> ExtractedWebPage:
    parser = _ReadableHtmlParser()
    parser.feed(html_text)
    parser.close()

    link_parser = _LinkCollector()
    link_parser.feed(html_text)
    link_parser.close()

    sections = clean_sections([section for section in parser.sections if section.text])
    cleaned_text = normalize_whitespace("\n\n".join(section.text for section in sections))
    title = parser.title or parser.metadata.get("description") or url
    parsed = urllib.parse.urlsplit(url)
    metadata = {
        "title": title,
        "author": parser.metadata.get("author"),
        "date": parser.metadata.get("date"),
        "description": parser.metadata.get("description"),
        "section_count": len(sections),
        "domain": parsed.hostname,
        "content_hash": stable_text_key(cleaned_text),
    }
    return ExtractedWebPage(
        url=url,
        title=title,
        text="\n\n".join(section.text for section in sections),
        cleaned_text=cleaned_text,
        sections=sections,
        metadata=metadata,
        links=link_parser.links,
    )


def build_document_from_pages(title: str, pages: list[ExtractedWebPage]) -> ExtractedDocument:
    sections: list[ExtractedSection] = []
    for page in pages:
        sections.append(
            ExtractedSection(
                text=page.title,
                order=len(sections),
                section_type="h1",
                metadata={"url": page.url, "page_title": page.title},
            )
        )
        for page_section in page.sections:
            sections.append(
                ExtractedSection(
                    text=page_section.text,
                    order=len(sections),
                    section_type=page_section.section_type,
                    metadata={
                        **(page_section.metadata or {}),
                        "url": page.url,
                        "page_title": page.title,
                        "domain": page.metadata.get("domain"),
                    },
                )
            )
    cleaned_text = normalize_whitespace("\n\n".join(section.text for section in sections))
    return ExtractedDocument(
        full_text=cleaned_text,
        cleaned_text=cleaned_text,
        sections=sections,
        metadata={
            "title": title,
            "page_count": len(pages),
            "source_type": "url",
            "domains": sorted({page.metadata.get("domain") for page in pages if page.metadata.get("domain")}),
        },
    )
