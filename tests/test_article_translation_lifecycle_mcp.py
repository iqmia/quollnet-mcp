import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools import article_lifecycle as lifecycle


class ArticleTranslationLifecycleForwardingTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_articles_needing_translation_forwards_to_qapp(self) -> None:
        self.assertTrue(hasattr(lifecycle, "list_articles_needing_translation"))
        expected = {"message": "Pending translations retrieved", "data": []}
        with (
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_client.get_json",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await lifecycle.list_articles_needing_translation()

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            "/articles/api/v1/articles/translations/pending",
            access_token="qapp-user-token",
        )

    async def test_increment_article_version_forwards_encoded_id(self) -> None:
        self.assertTrue(hasattr(lifecycle, "increment_article_version"))
        await self._assert_post_tool(
            lifecycle.increment_article_version,
            "article/1",
            "/articles/api/v1/articles/article%2F1/increment-version",
        )

    async def test_lock_article_auto_translation_forwards_encoded_id(self) -> None:
        self.assertTrue(hasattr(lifecycle, "lock_article_auto_translation"))
        await self._assert_post_tool(
            lifecycle.lock_article_auto_translation,
            "article/1",
            "/articles/api/v1/articles/article%2F1/lock-auto-translation",
        )

    async def test_unlock_article_auto_translation_forwards_encoded_id(self) -> None:
        self.assertTrue(hasattr(lifecycle, "unlock_article_auto_translation"))
        await self._assert_post_tool(
            lifecycle.unlock_article_auto_translation,
            "article/1",
            "/articles/api/v1/articles/article%2F1/unlock-auto-translation",
        )

    async def test_mark_article_translation_current_forwards_encoded_id(self) -> None:
        self.assertTrue(hasattr(lifecycle, "mark_article_translation_current"))
        await self._assert_post_tool(
            lifecycle.mark_article_translation_current,
            "translation/1",
            "/articles/api/v1/articles/translation%2F1/mark-translation-current",
        )

    async def test_translation_lifecycle_qapp_error_becomes_tool_error(self) -> None:
        self.assertTrue(hasattr(lifecycle, "increment_article_version"))
        with (
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_client.post_json",
                new=AsyncMock(side_effect=QAppClientError("permission denied")),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "permission denied"):
                await lifecycle.increment_article_version(article_id="article-1")

    async def _assert_post_tool(self, tool, article_id: str, path: str) -> None:
        expected = {"message": "ok", "data": {"article_id": article_id}}
        with (
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_client.post_json",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await tool(article_id=article_id)

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            path,
            payload={},
            access_token="qapp-user-token",
        )


class GeneralMCPToolsetTests(unittest.TestCase):
    def test_general_mcp_replaces_legacy_cashflow_tools_with_translation_lifecycle_tools(self) -> None:
        import app as app_module

        tool_names = {
            tool.name for tool in app_module.mcp._tool_manager._tools.values()
        }

        for name in {
            "list_articles_needing_translation",
            "increment_article_version",
            "lock_article_auto_translation",
            "unlock_article_auto_translation",
            "mark_article_translation_current",
        }:
            self.assertIn(name, tool_names)

        self.assertNotIn("list_cashflow_projects", tool_names)
        self.assertNotIn("create_cashflow", tool_names)


if __name__ == "__main__":
    unittest.main()
