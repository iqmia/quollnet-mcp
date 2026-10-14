import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.articles import (
    list_article_topics,
    recheck_article,
    validate_article_for_publish,
)


class ArticleHealthToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_article_topics_forwards_qapp_token(self) -> None:
        expected = {"message": "ok", "data": [{"slug": "qa-qc"}]}
        with (
            patch(
                "quollnet_mcp.tools.articles.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.list_article_topics",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await list_article_topics()

        self.assertIs(result, expected)
        call.assert_awaited_once_with(access_token="qapp-user-token")

    async def test_validate_article_for_publish_forwards_article_id(self) -> None:
        expected = {"data": {"article_id": "article-1", "valid": True}}
        with (
            patch(
                "quollnet_mcp.tools.articles.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.validate_article_for_publish",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await validate_article_for_publish(article_id="article-1")

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            access_token="qapp-user-token",
            article_id="article-1",
        )

    async def test_recheck_article_forwards_article_id(self) -> None:
        expected = {"data": {"article_id": "article-1", "checks": {}}}
        with (
            patch(
                "quollnet_mcp.tools.articles.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.recheck_article",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await recheck_article(article_id="article-1")

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            access_token="qapp-user-token",
            article_id="article-1",
        )

    async def test_health_qapp_error_becomes_tool_error(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.recheck_article",
                new=AsyncMock(side_effect=QAppClientError("permission denied")),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "permission denied"):
                await recheck_article(article_id="article-1")


class ArticleHealthRegistrationTests(unittest.TestCase):
    def test_health_tools_are_registered(self) -> None:
        import app as app_module

        tool_names = {
            tool.name for tool in app_module.mcp._tool_manager._tools.values()
        }
        self.assertIn("list_article_topics", tool_names)
        self.assertIn("validate_article_for_publish", tool_names)
        self.assertIn("recheck_article", tool_names)


if __name__ == "__main__":
    unittest.main()
