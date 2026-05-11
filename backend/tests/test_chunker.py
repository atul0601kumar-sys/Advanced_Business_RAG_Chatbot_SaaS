import unittest

from app.services.chunker import SmartChunker
from app.services.text_extractor import ExtractedDocument, ExtractedSection


class SmartChunkerTests(unittest.TestCase):
    def test_chunker_respects_sentence_boundaries_and_deduplicates(self) -> None:
        extracted = ExtractedDocument(
            full_text="",
            cleaned_text="",
            sections=[
                ExtractedSection(
                    text=(
                        "This is sentence one. This is sentence two. "
                        "This is sentence three. This is sentence one. This is sentence two."
                    ),
                    order=0,
                    section_type="paragraph",
                ),
                ExtractedSection(
                    text="Another semantic sentence closes the section.",
                    order=1,
                    section_type="paragraph",
                ),
            ],
            metadata={},
        )
        chunker = SmartChunker(target_chunk_tokens=20, overlap_tokens=6, min_chunk_tokens=5)
        chunks = chunker.chunk_document(extracted)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(list(range(len(chunks))), [chunk.chunk_index for chunk in chunks])
        self.assertEqual(len(chunks), len({chunk.metadata["content_hash"] for chunk in chunks}))
        for chunk in chunks:
            self.assertFalse(chunk.text.endswith("This is"))


if __name__ == "__main__":
    unittest.main()

