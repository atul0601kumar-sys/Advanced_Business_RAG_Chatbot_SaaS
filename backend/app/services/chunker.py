from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.text_extractor import ExtractedDocument, ExtractedSection


@dataclass
class SentenceUnit:
    text: str
    token_count: int
    page_number: int | None
    section_order: int
    section_type: str
    metadata: dict[str, Any]


@dataclass
class ChunkDraft:
    text: str
    chunk_index: int
    token_count: int
    page_number: int | None
    page_numbers: list[int]
    section_orders: list[int]
    metadata: dict[str, Any] = field(default_factory=dict)


class SmartChunker:
    def __init__(self, target_chunk_tokens: int = 650, overlap_tokens: int = 120, min_chunk_tokens: int = 120):
        self.target_chunk_tokens = target_chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens

    def chunk_document(self, extracted: ExtractedDocument) -> list[ChunkDraft]:
        sentence_units: list[SentenceUnit] = []
        for section in extracted.sections:
            sentence_units.extend(self._section_to_sentence_units(section))

        if not sentence_units:
            return []

        raw_chunks = self._build_sentence_windows(sentence_units)
        return self._deduplicate_chunks(raw_chunks)

    def estimate_tokens(self, text: str) -> int:
        word_tokens = len(re.findall(r"\w+|[^\w\s]", text))
        char_tokens = math.ceil(len(text) / 4) if text else 0
        return max(word_tokens, char_tokens, 1)

    def _section_to_sentence_units(self, section: ExtractedSection) -> list[SentenceUnit]:
        blocks = [block.strip() for block in re.split(r"\n{2,}", section.text) if block.strip()]
        units: list[SentenceUnit] = []
        for block in blocks:
            sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", block) if sentence.strip()]
            if not sentences:
                sentences = [block]
            for sentence in sentences:
                if self.estimate_tokens(sentence) > self.target_chunk_tokens:
                    units.extend(self._split_large_sentence(sentence, section))
                    continue
                units.append(
                    SentenceUnit(
                        text=sentence,
                        token_count=self.estimate_tokens(sentence),
                        page_number=section.page_number,
                        section_order=section.order,
                        section_type=section.section_type,
                        metadata=dict(section.metadata),
                    )
                )
        return units

    def _split_large_sentence(self, sentence: str, section: ExtractedSection) -> list[SentenceUnit]:
        clauses = [clause.strip() for clause in re.split(r"(?<=[;:])\s+|,\s+|\n+", sentence) if clause.strip()]
        if len(clauses) <= 1:
            clauses = [sentence]
        units: list[SentenceUnit] = []
        buffer = ""
        for clause in clauses:
            candidate = f"{buffer} {clause}".strip() if buffer else clause
            if self.estimate_tokens(candidate) <= self.target_chunk_tokens:
                buffer = candidate
                continue
            if buffer:
                units.append(
                    SentenceUnit(
                        text=buffer,
                        token_count=self.estimate_tokens(buffer),
                        page_number=section.page_number,
                        section_order=section.order,
                        section_type=section.section_type,
                        metadata=dict(section.metadata),
                    )
                )
            buffer = clause
        if buffer:
            units.append(
                SentenceUnit(
                    text=buffer,
                    token_count=self.estimate_tokens(buffer),
                    page_number=section.page_number,
                    section_order=section.order,
                    section_type=section.section_type,
                    metadata=dict(section.metadata),
                )
            )
        return units

    def _build_sentence_windows(self, units: list[SentenceUnit]) -> list[ChunkDraft]:
        chunks: list[ChunkDraft] = []
        start = 0
        chunk_index = 0

        while start < len(units):
            current_tokens = 0
            end = start
            chunk_units: list[SentenceUnit] = []
            while end < len(units):
                next_unit = units[end]
                if chunk_units and current_tokens + next_unit.token_count > self.target_chunk_tokens:
                    break
                chunk_units.append(next_unit)
                current_tokens += next_unit.token_count
                end += 1

            if not chunk_units:
                chunk_units.append(units[end])
                current_tokens = units[end].token_count
                end += 1

            chunk_text = " ".join(unit.text for unit in chunk_units).strip()
            page_numbers = sorted({unit.page_number for unit in chunk_units if unit.page_number is not None})
            section_orders = sorted({unit.section_order for unit in chunk_units})
            metadata: dict[str, Any] = {
                "page_numbers": page_numbers,
                "section_orders": section_orders,
                "section_types": sorted({unit.section_type for unit in chunk_units}),
            }
            chunks.append(
                ChunkDraft(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    token_count=current_tokens,
                    page_number=page_numbers[0] if page_numbers else None,
                    page_numbers=page_numbers,
                    section_orders=section_orders,
                    metadata=metadata,
                )
            )
            chunk_index += 1

            if end >= len(units):
                break

            overlap_start = end
            overlap_tokens = 0
            while overlap_start > start and overlap_tokens < self.overlap_tokens:
                overlap_start -= 1
                overlap_tokens += units[overlap_start].token_count
            if overlap_start == start:
                start = end
            else:
                start = overlap_start

        return chunks

    def _deduplicate_chunks(self, chunks: list[ChunkDraft]) -> list[ChunkDraft]:
        seen_hashes: set[str] = set()
        unique_chunks: list[ChunkDraft] = []

        for chunk in chunks:
            normalized = re.sub(r"\s+", " ", chunk.text).strip().lower()
            content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            chunk.metadata["content_hash"] = content_hash
            chunk.chunk_index = len(unique_chunks)
            unique_chunks.append(chunk)
        return unique_chunks

