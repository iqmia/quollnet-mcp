import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.articles import search_articles


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
