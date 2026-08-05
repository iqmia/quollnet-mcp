
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")

from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.articles import (
    create_article_draft,
    search_articles,
)

class CreateArticleDraftTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_token_and_payload(self) -> None:
        token = SimpleNamespace(
            token="bearer-token",
            subject="user-1",
            scopes=["articles:read", "articles:create"],
        )

        authoring_data = {
            "schema_version": 1,
            "answer_summary": "A concise practical answer.",
            "search": {},
            "images": {},
            "references": [],
            "internal_links": [],
            "downloads": [],
            "tools": [],
            "social": {},
        }

        expected = {
            "message": "Article draft created",
            "data": {
                "id": "article-1",
                "slug": "test-article-draft",
                "subject": "Test Article Draft",
                "posted": False,
                "ready_to_publish": False,
            },
        }

        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=token,
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.create_article_draft",
                new=AsyncMock(return_value=expected),
            ) as create,
        ):
            actual = await create_article_draft(
                subject="Test Article Draft",
                path="test-article-draft",
                description="A test article draft description.",
                keywords="test article, draft",
                body=(
                    "<h1>Test Article Draft</h1>"
                    "<p>A concise practical answer.</p>"
                ),
                primary_article_topic="qa-qc",
                authoring_data=authoring_data,
                article_topics=[],
                faq="",
                lang="en",
                page_type="article",
            )

        self.assertIs(actual, expected)

        create.assert_awaited_once_with(
            access_token="bearer-token",
            payload={
                "subject": "Test Article Draft",
                "path": "test-article-draft",
                "description": "A test article draft description.",
                "keywords": "test article, draft",
                "body": (
                    "<h1>Test Article Draft</h1>"
                    "<p>A concise practical answer.</p>"
                ),
                "faq": "",
                "primary_article_topic": "qa-qc",
                "article_topics": [],
                "lang": "en",
                "page_type": "article",
                "authoring_data": authoring_data,
            },
        )

class SearchArticlesTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_token_and_parameters(self) -> None:
        result = {"articles": [], "pagination": {"page": 2}}
        token = SimpleNamespace(token="bearer-token", subject="user-1")
        with (
            patch("quollnet_mcp.tools.articles.get_access_token", return_value=token),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.search_articles",
                new=AsyncMock(return_value=result),
            ) as search,
        ):
            actual = await search_articles(
                q="climate",
                topic="science",
                lang="en",
                status="draft",
                sort_by="title",
                sort_dir="asc",
                page=2,
                per_page=10,
            )

        self.assertIs(actual, result)
        search.assert_awaited_once_with(
            access_token="bearer-token",
            q="climate",
            topic="science",
            lang="en",
            status="draft",
            sort_by="title",
            sort_dir="asc",
            page=2,
            per_page=10,
        )

    async def test_missing_authentication(self) -> None:
        with patch("quollnet_mcp.tools.articles.get_access_token", return_value=None):
            with self.assertRaises(ToolError):
                await search_articles()

    async def test_missing_authenticated_subject(self) -> None:
        token = SimpleNamespace(token="bearer-token", subject=None)
        with patch("quollnet_mcp.tools.articles.get_access_token", return_value=token):
            with self.assertRaises(ToolError):
                await search_articles()

    async def test_qapp_error_is_converted(self) -> None:
        token = SimpleNamespace(token="bearer-token", subject="user-1")
        with (
            patch("quollnet_mcp.tools.articles.get_access_token", return_value=token),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.search_articles",
                new=AsyncMock(side_effect=QAppClientError("qApp unavailable")),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "Article search failed"):
                await search_articles()


if __name__ == "__main__":
    unittest.main()
