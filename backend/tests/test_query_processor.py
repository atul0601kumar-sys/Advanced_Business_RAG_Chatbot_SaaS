import unittest

from app.services.query_processor import QueryProcessor


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]


class QueryProcessorTests(unittest.TestCase):
    def test_normalizes_query_and_caches_embedding(self) -> None:
        embedder = FakeEmbedder()
        processor = QueryProcessor(embedder, cache_size=8)
        first = processor.process(" Show ME revenue growth for Q1?! ")
        second = processor.process("show me revenue growth for q1")

        self.assertEqual(first.normalized_query, "show me revenue growth for q1")
        self.assertEqual(second.normalized_query, "show me revenue growth for q1")
        self.assertEqual(len(embedder.calls), 1)
        self.assertIn("revenue", first.keywords)


if __name__ == "__main__":
    unittest.main()
