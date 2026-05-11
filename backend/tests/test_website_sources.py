import shutil
import socket
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Document, DocumentChunk, User, WebsiteSource, Workspace, WorkspaceMember
from app.services.text_extractor import settings as extractor_settings
from app.services.website_content_extractor import extract_clean_web_content
from app.services.website_crawler import (
    CrawlRequest,
    HttpResponse,
    UrlValidationService,
    WebsiteCrawler,
)
from app.services.website_sources import _crawl_and_index_source, create_website_source


class FakeFetcher:
    def __init__(self, pages: dict[str, HttpResponse]) -> None:
        self.pages = pages

    def fetch(self, url: str) -> HttpResponse:
        if url not in self.pages:
            return HttpResponse(url=url, status_code=404, headers={"content-type": "text/plain"}, body=b"missing")
        return self.pages[url]


class FakeEmbedder:
    model = "test-embedding-model"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1), 0.1, 0.2] for index, _ in enumerate(texts)]


class FakeVectorStore:
    def __init__(self) -> None:
        self.collections: list[int] = []
        self.upserted: list[dict] = []
        self.deleted: list[list[str]] = []

    def ensure_collection(self, vector_size: int) -> None:
        self.collections.append(vector_size)

    def upsert_points(self, points) -> None:
        self.upserted = [{"id": point.id, "payload": point.payload} for point in points]

    def delete_points(self, point_ids: list[str]) -> None:
        self.deleted.append(point_ids)


class WebsiteSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path.cwd() / ".tmp-website-storage"
        self.temp_root.mkdir(exist_ok=True)
        self.temp_dir = self.temp_root / f"case-{uuid.uuid4().hex[:8]}"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.previous_storage_dir = extractor_settings.storage_dir
        extractor_settings.storage_dir = str(self.temp_dir)

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def tearDown(self) -> None:
        extractor_settings.storage_dir = self.previous_storage_dir
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.engine.dispose()

    def _seed_workspace(self):
        with self.SessionLocal() as db:
            user = User(
                email="website@example.com",
                full_name="Website Owner",
                password_hash="hashed",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.flush()
            workspace = Workspace(
                name="Website Workspace",
                slug=f"website-{uuid.uuid4().hex[:8]}",
                description="Workspace for website ingestion tests",
                status="active",
                owner_user_id=user.id,
            )
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin"))
            db.commit()
            return user.id, workspace.id

    def test_url_validation_normalizes_and_blocks_malicious_hosts(self) -> None:
        validator = UrlValidationService()
        normalized = validator.validate_and_normalize("HTTPS://Example.com/pricing///?b=2&a=1#section")
        self.assertEqual(normalized, "https://example.com/pricing?a=1&b=2")

        with self.assertRaises(HTTPException):
            validator.validate_and_normalize("file:///etc/passwd")
        with self.assertRaises(HTTPException):
            validator.validate_and_normalize("http://127.0.0.1/admin")
        with self.assertRaises(HTTPException):
            validator.validate_and_normalize("https://user:pass@example.com/private")

    def test_url_validation_blocks_hostnames_resolving_to_private_ips(self) -> None:
        validator = UrlValidationService()
        with patch.object(socket, "getaddrinfo", return_value=[(0, 0, 0, "", ("10.0.0.5", 0))]):
            with self.assertRaises(HTTPException):
                validator.validate_and_normalize("https://internal.example.com/docs")

    def test_crawler_respects_robots_depth_and_deduplicates_urls(self) -> None:
        fetcher = FakeFetcher(
            {
                "https://example.com/robots.txt": HttpResponse(
                    url="https://example.com/robots.txt",
                    status_code=200,
                    headers={"content-type": "text/plain"},
                    body=b"User-agent: *\nDisallow: /blocked\n",
                ),
                "https://example.com": HttpResponse(
                    url="https://example.com",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=(
                        b"<html><head><title>Home</title></head>"
                        b"<body><nav>Nav</nav><h1>Home</h1><p>Welcome</p>"
                        b"<a href='/about/'>About</a><a href='/about'>About dup</a>"
                        b"<a href='/blocked'>Blocked</a></body></html>"
                    ),
                ),
                "https://example.com/about": HttpResponse(
                    url="https://example.com/about",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=(
                        b"<html><head><title>About</title><meta name='author' content='Team'></head>"
                        b"<body><h2>About us</h2><p>Clean text.</p></body></html>"
                    ),
                ),
            }
        )
        crawler = WebsiteCrawler(fetcher=fetcher)
        crawled = crawler.crawl(CrawlRequest(url="https://example.com/", max_depth=1, max_pages=5))

        self.assertEqual([page.url for page in crawled.pages], ["https://example.com", "https://example.com/about"])
        self.assertIn("https://example.com/blocked", crawled.blocked_urls)
        self.assertEqual(len(crawled.visited_urls), 3)

    def test_crawler_applies_request_delay_between_fetches(self) -> None:
        fetcher = FakeFetcher(
            {
                "https://example.com/robots.txt": HttpResponse(
                    url="https://example.com/robots.txt",
                    status_code=200,
                    headers={"content-type": "text/plain"},
                    body=b"User-agent: *\nAllow: /\n",
                ),
                "https://example.com": HttpResponse(
                    url="https://example.com",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=b"<html><head><title>Home</title></head><body><h1>Home</h1><p>Welcome</p></body></html>",
                ),
            }
        )
        crawler = WebsiteCrawler(fetcher=fetcher)

        with patch("app.services.website_crawler.settings.website_crawler_request_delay_seconds", 0.25):
            with patch("app.services.website_crawler.time.sleep") as sleep_mock:
                crawler.crawl(CrawlRequest(url="https://example.com", max_depth=0, max_pages=1))

        sleep_mock.assert_called()

    def test_html_extraction_removes_noise_and_preserves_structure(self) -> None:
        html = """
        <html>
          <head>
            <title>Pricing</title>
            <meta name="author" content="Finance Team" />
            <meta property="article:published_time" content="2026-01-02" />
          </head>
          <body>
            <nav>Main menu</nav>
            <article>
              <h1>Pricing Overview</h1>
              <p>Base subscription starts at $299.</p>
              <p>Base subscription starts at $299.</p>
              <ul><li>Analytics add-on</li><li>Priority support</li></ul>
              <p>Privacy policy</p>
            </article>
            <footer>Footer links</footer>
            <script>console.log('ignore');</script>
          </body>
        </html>
        """
        extracted = extract_clean_web_content("https://example.com/pricing", html)

        self.assertEqual(extracted.title, "Pricing")
        self.assertEqual(extracted.metadata["author"], "Finance Team")
        self.assertEqual(extracted.metadata["date"], "2026-01-02")
        self.assertIn("Pricing Overview", extracted.cleaned_text)
        self.assertIn("Base subscription starts at $299.", extracted.cleaned_text)
        self.assertIn("- Analytics add-on", extracted.cleaned_text)
        self.assertEqual(extracted.cleaned_text.count("Base subscription starts at $299."), 1)
        self.assertNotIn("Main menu", extracted.cleaned_text)
        self.assertNotIn("Footer links", extracted.cleaned_text)
        self.assertNotIn("console.log", extracted.cleaned_text)
        self.assertNotIn("Privacy policy", extracted.cleaned_text)

    def test_create_and_index_website_source(self) -> None:
        user_id, workspace_id = self._seed_workspace()
        fetcher = FakeFetcher(
            {
                "https://example.com/robots.txt": HttpResponse(
                    url="https://example.com/robots.txt",
                    status_code=200,
                    headers={"content-type": "text/plain"},
                    body=b"User-agent: *\nAllow: /\n",
                ),
                "https://example.com/pricing": HttpResponse(
                    url="https://example.com/pricing",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=(
                        b"<html><head><title>Pricing</title><meta name='author' content='Marketing'></head>"
                        b"<body><h1>Pricing</h1><p>Base plan starts at $299 monthly.</p>"
                        b"<a href='/pricing/faq'>FAQ</a></body></html>"
                    ),
                ),
                "https://example.com/pricing/faq": HttpResponse(
                    url="https://example.com/pricing/faq",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=(
                        b"<html><head><title>FAQ</title></head>"
                        b"<body><h2>FAQ</h2><p>Annual contracts include onboarding support.</p></body></html>"
                    ),
                ),
                "https://example.com/pricing-copy": HttpResponse(
                    url="https://example.com/pricing-copy",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=(
                        b"<html><head><title>Pricing Copy</title></head>"
                        b"<body><h1>Pricing</h1><p>Base plan starts at $299 monthly.</p></body></html>"
                    ),
                ),
            }
        )

        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            source_summary = create_website_source(
                db,
                workspace_id,
                user,
                url="https://example.com/pricing/",
                domain_root="https://example.com",
                max_depth=1,
                max_pages=5,
            )

            source = db.scalar(select(WebsiteSource).where(WebsiteSource.id == source_summary.id))
            self.assertIsNotNone(source)

            _crawl_and_index_source(
                db,
                source,
                crawler=WebsiteCrawler(fetcher=fetcher),
                embedder=FakeEmbedder(),
                vector_store=FakeVectorStore(),
            )

            refreshed_source = db.scalar(select(WebsiteSource).where(WebsiteSource.id == source_summary.id))
            linked_document = db.scalar(select(Document).where(Document.id == refreshed_source.document_id))
            chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == linked_document.id)).all()

            self.assertEqual(refreshed_source.crawl_status, "indexed")
            self.assertEqual(linked_document.ingestion_status, "indexed")
            self.assertEqual(linked_document.source_type, "url")
            self.assertEqual(refreshed_source.url, "https://example.com/pricing")
            self.assertEqual(refreshed_source.domain, "example.com")
            self.assertEqual(refreshed_source.page_title, "Pricing")
            self.assertIsNotNone(refreshed_source.crawl_date)
            self.assertEqual(refreshed_source.metadata_json["page_count"], 2)
            self.assertTrue(Path(linked_document.storage_path).exists())
            self.assertGreaterEqual(len(chunks), 1)
            self.assertTrue(all(chunk.metadata_json.get("url", "").startswith("https://example.com") for chunk in chunks))
            self.assertTrue(all(chunk.metadata_json.get("content_type") == "url" for chunk in chunks))
            self.assertTrue(all(chunk.metadata_json.get("domain") == "example.com" for chunk in chunks))
            self.assertTrue(all(chunk.metadata_json.get("crawl_date") for chunk in chunks))
            self.assertTrue(all(chunk.metadata_json.get("chunk_id") for chunk in chunks))
            self.assertTrue(all(chunk.metadata_json.get("section_heading") for chunk in chunks))
            self.assertTrue(all(chunk.website_source_id == refreshed_source.id for chunk in chunks))
            self.assertTrue(any(chunk.metadata_json.get("section_heading") == "FAQ" for chunk in chunks))

    def test_failed_crawl_marks_source_failed_with_reason(self) -> None:
        user_id, workspace_id = self._seed_workspace()
        fetcher = FakeFetcher(
            {
                "https://example.com/robots.txt": HttpResponse(
                    url="https://example.com/robots.txt",
                    status_code=200,
                    headers={"content-type": "text/plain"},
                    body=b"User-agent: *\nAllow: /\n",
                ),
                "https://example.com/failure": HttpResponse(
                    url="https://example.com/failure",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=b"<html><body><nav>Menu</nav><footer>Footer</footer></body></html>",
                ),
            }
        )

        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            source_summary = create_website_source(
                db,
                workspace_id,
                user,
                url="https://example.com/failure",
                domain_root="https://example.com",
                max_depth=0,
                max_pages=1,
            )
            source = db.scalar(select(WebsiteSource).where(WebsiteSource.id == source_summary.id))

            with self.assertRaises(RuntimeError):
                _crawl_and_index_source(
                    db,
                    source,
                    crawler=WebsiteCrawler(fetcher=fetcher),
                    embedder=FakeEmbedder(),
                    vector_store=FakeVectorStore(),
                )

            source.crawl_status = "failed"
            source.metadata_json = {
                **(source.metadata_json or {}),
                "failure_reason": "indexing_failed",
                "processing_error": "No readable pages were extracted from the provided URL.",
            }
            db.commit()
            db.refresh(source)

            self.assertEqual(source.crawl_status, "failed")
            self.assertEqual(source.metadata_json["failure_reason"], "indexing_failed")
            self.assertIn("No readable pages", source.metadata_json["processing_error"])

    def test_duplicate_website_source_is_rejected_after_normalization(self) -> None:
        user_id, workspace_id = self._seed_workspace()
        with self.SessionLocal() as db:
            user = db.get(User, user_id)
            create_website_source(
                db,
                workspace_id,
                user,
                url="https://example.com/pricing/",
                domain_root="https://example.com",
                max_depth=0,
                max_pages=1,
            )
            with self.assertRaises(HTTPException):
                create_website_source(
                    db,
                    workspace_id,
                    user,
                    url="https://example.com/pricing",
                    domain_root="https://example.com/",
                    max_depth=0,
                    max_pages=1,
                )


if __name__ == "__main__":
    unittest.main()
