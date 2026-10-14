import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.article_lifecycle import (
    archive_article,
    list_article_topics,
    publish_article,
    recheck_article,
    restore_article,
    unpublish_article,
    validate_article_for_publish,
)


class ArticleHealthToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_article_topics_uses_qapp_registry_route(self) -> None:
        expected = {"message": "ok", "data": [{"slug": "qa-qc"}]}
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
            result = await list_article_topics()

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            "/articles/api/v1/article-topics",
            access_token="qapp-user-token",
        )

    async def test_validate_article_for_publish_uses_encoded_article_route(self) -> None:
        expected = {"data": {"article_id": "article/1", "valid": True}}
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
            result = await validate_article_for_publish(article_id="article/1")

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            "/articles/api/v1/articles/article%2F1/validate",
            access_token="qapp-user-token",
        )

    async def test_recheck_article_remains_available_internally(self) -> None:
        expected = {"data": {"article_id": "article/1", "checks": {}}}
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
            result = await recheck_article(article_id="article/1")

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            "/articles/api/v1/articles/article%2F1/recheck",
            access_token="qapp-user-token",
        )

    async def test_health_qapp_error_becomes_tool_error(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_client.get_json",
                new=AsyncMock(side_effect=QAppClientError("permission denied")),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "permission denied"):
                await recheck_article(article_id="article-1")


class ArticleLifecycleMutationTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_validates_then_forwards_to_qapp(self) -> None:
        publication = {
            "message": "Article is ready to publish",
            "data": {"published": False},
        }
        with (
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_client.get_json",
                new=AsyncMock(return_value={"data": {"valid": True, "warnings": []}}),
            ) as validate,
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_client.post_json",
                new=AsyncMock(return_value=publication),
            ) as publish,
        ):
            result = await publish_article(article_id="article-1")

        self.assertIs(result, publication)
        validate.assert_awaited_once_with(
            "/articles/api/v1/articles/article-1/validate",
            access_token="qapp-user-token",
        )
        publish.assert_awaited_once_with(
            "/articles/api/v1/articles/publish",
            payload={"id": "article-1"},
            access_token="qapp-user-token",
        )

    async def test_publish_stops_when_qapp_validation_fails(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_client.get_json",
                new=AsyncMock(
                    return_value={
                        "data": {
                            "valid": False,
                            "errors": [{"code": "content_contract"}],
                        }
                    }
                ),
            ),
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_client.post_json",
                new=AsyncMock(),
            ) as publish,
        ):
            with self.assertRaisesRegex(ToolError, "not ready for publication"):
                await publish_article(article_id="article-1")

        publish.assert_not_awaited()

    async def test_unpublish_forwards_to_qapp(self) -> None:
        expected = {"message": "Article unpublished"}
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
            result = await unpublish_article(article_id="article-1")

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            "/articles/api/v1/articles/unpublish",
            payload={"id": "article-1"},
            access_token="qapp-user-token",
        )

    async def test_archive_uses_soft_delete_route(self) -> None:
        expected = {"message": "Article deleted"}
        with (
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_user_token",
                return_value="qapp-user-token",
            ),
            patch(
                "quollnet_mcp.tools.article_lifecycle.qapp_client.delete_json",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await archive_article(article_id="article-1")

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            "/articles/api/v1/articles/delete",
            payload={"id": "article-1"},
            access_token="qapp-user-token",
        )

    async def test_restore_forwards_to_qapp(self) -> None:
        expected = {"message": "Article restored"}
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
            result = await restore_article(article_id="article-1")

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            "/articles/api/v1/articles/restore",
            payload={"id": "article-1"},
            access_token="qapp-user-token",
        )

    async def test_lifecycle_qapp_error_becomes_tool_error(self) -> None:
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
                await unpublish_article(article_id="article-1")


class ArticleLifecycleRegistrationTests(unittest.TestCase):
    def test_article_lifecycle_tools_are_registered_without_separate_recheck(self) -> None:
        import app as app_module

        tool_names = {
            tool.name for tool in app_module.mcp._tool_manager._tools.values()
        }
        self.assertIn("list_article_topics", tool_names)
        self.assertIn("validate_article_for_publish", tool_names)
        self.assertNotIn("recheck_article", tool_names)
        self.assertIn("publish_article", tool_names)
        self.assertIn("unpublish_article", tool_names)
        self.assertIn("archive_article", tool_names)
        self.assertIn("restore_article", tool_names)
        self.assertEqual(len(tool_names), 32)


if __name__ == "__main__":
    unittest.main()
