import unittest

from app.core.config import Settings
from app.services.embedder import HashingEmbedder, get_default_embedder


class HashingEmbedderTests(unittest.TestCase):
    def test_hashing_embedder_is_deterministic_and_normalized(self) -> None:
        embedder = HashingEmbedder(dimensions=16)

        first = embedder.embed_texts(["Revenue grew sharply in Q1"])[0]
        second = embedder.embed_texts(["Revenue grew sharply in Q1"])[0]

        self.assertEqual(len(first), 16)
        self.assertEqual(first, second)
        self.assertAlmostEqual(sum(value * value for value in first), 1.0, places=5)

    def test_default_embedder_uses_hash_provider_without_openai_billing(self) -> None:
        settings = Settings(embedding_provider="hash")

        self.assertEqual(settings.embedding_provider, "hash")
        self.assertEqual(type(get_default_embedder()).__name__, "HashingEmbedder")


if __name__ == "__main__":
    unittest.main()
