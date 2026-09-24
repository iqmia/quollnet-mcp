from unittest.mock import AsyncMock, patch

import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.qtools import (
    QToolCreateMetadata,
    QToolMetadataUpdate,
    create_qtool,
    get_qtool,
    get_qtool_development_guide,
    get_qtool_file,
    list_qtools,
    publish_qtool,
    save_qtool,
    update_qtool_file,
    update_qtool_metadata,
)




class GetQToolDevelopmentGuideTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_token_to_qapp(self) -> None:
        expected = {
            "spec_version": 1,
            "spec_format": "text/markdown",
            "instructions": "# Quollnet qTools V2 Development Guide",
        }

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.get_qtool_development_guide",
                new=AsyncMock(return_value=expected),
            ) as get_guide,
        ):
            actual = await get_qtool_development_guide()

        self.assertIs(actual, expected)
        get_guide.assert_awaited_once_with(
            access_token="qapp-user-token",
        )


    async def test_qapp_error_is_converted(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.get_qtool_development_guide",
                new=AsyncMock(
                    side_effect=QAppClientError("qApp unavailable")
                ),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "qApp unavailable"):
                await get_qtool_development_guide()


class ListQToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_filters_and_pagination(self) -> None:
        expected = {
            "data": [{"slug": "concrete-strength-calculator"}],
            "pagination": {"page": 2},
        }

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.list_qtools",
                new=AsyncMock(return_value=expected),
            ) as list_call,
        ):
            actual = await list_qtools(
                status="published",
                page=2,
                per_page=10,
            )

        self.assertIs(actual, expected)
        list_call.assert_awaited_once_with(
            access_token="qapp-user-token",
            status="published",
            page=2,
            per_page=10,
        )


class CreateQToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchanges_qapp_token_and_builds_create_payload(self) -> None:
        expected = {
            "data": {
                "slug": "concrete-checker",
                "working_version": 1,
            }
        }
        metadata = QToolCreateMetadata(
            description="Concrete decision aid.",
            keywords="concrete, qa qc",
            login_required=False,
            article_embed_allowed=True,
        )

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.create_qtool",
                new=AsyncMock(return_value=expected),
            ) as create_call,
        ):
            actual = await create_qtool(
                slug="concrete-checker",
                tool_name="Concrete Checker",
                metadata=metadata,
            )

        self.assertIs(actual, expected)
        create_call.assert_awaited_once_with(
            access_token="qapp-user-token",
            payload={
                "slug": "concrete-checker",
                "tool_name": "Concrete Checker",
                "metadata": {
                    "description": "Concrete decision aid.",
                    "keywords": "concrete, qa qc",
                    "login_required": False,
                    "article_embed_allowed": True,
                },
            },
        )

    async def test_metadata_is_optional(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.create_qtool",
                new=AsyncMock(return_value={"data": {}}),
            ) as create_call,
        ):
            await create_qtool(
                slug="concrete-checker",
                tool_name="Concrete Checker",
            )

        create_call.assert_awaited_once_with(
            access_token="qapp-user-token",
            payload={
                "slug": "concrete-checker",
                "tool_name": "Concrete Checker",
            },
        )

    async def test_qapp_error_is_converted(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.create_qtool",
                new=AsyncMock(
                    side_effect=QAppClientError(
                        "qApp returned HTTP 400: Tool slug already exists"
                    )
                ),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "slug already exists"):
                await create_qtool(
                    slug="concrete-checker",
                    tool_name="Concrete Checker",
                )


class GetQToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_combines_tool_and_package_file_list(self) -> None:
        tool_response = {
            "data": {
                "slug": "sample-tool",
                "tool_name": "Sample Tool",
                "versions": [{"version": 1, "state": "saved"}],
            }
        }
        files_response = {
            "data": {
                "version": 1,
                "state": "saved",
                "files": [
                    "core.html",
                    "css/01-base.css",
                    "js/01-ui.js",
                ],
            }
        }

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.get_qtool",
                new=AsyncMock(return_value=tool_response),
            ) as get_call,
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.list_qtool_files",
                new=AsyncMock(return_value=files_response),
            ) as files_call,
        ):
            actual = await get_qtool("sample-tool")

        self.assertEqual(actual["data"]["slug"], "sample-tool")
        self.assertEqual(
            actual["data"]["package"]["files"],
            ["core.html", "css/01-base.css", "js/01-ui.js"],
        )
        get_call.assert_awaited_once_with(
            access_token="qapp-user-token",
            slug="sample-tool",
        )
        files_call.assert_awaited_once_with(
            access_token="qapp-user-token",
            slug="sample-tool",
        )


class GetQToolFileTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_exact_package_path(self) -> None:
        expected = {
            "data": {
                "path": "js/01-ui.js",
                "encoding": "utf-8",
                "content": "window.ready = true;",
            }
        }

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.get_qtool_file",
                new=AsyncMock(return_value=expected),
            ) as get_file,
        ):
            actual = await get_qtool_file(
                "sample-tool",
                "js/01-ui.js",
            )

        self.assertIs(actual, expected)
        get_file.assert_awaited_once_with(
            access_token="qapp-user-token",
            slug="sample-tool",
            relative_path="js/01-ui.js",
        )


class UpdateQToolFileTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchanges_qapp_token_and_forwards_content(self) -> None:
        expected = {
            "data": {
                "path": "core.html",
                "working_version": 2,
            }
        }

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.update_qtool_file",
                new=AsyncMock(return_value=expected),
            ) as update_file,
        ):
            actual = await update_qtool_file(
                "sample-tool",
                "core.html",
                '<section data-qtool="sample-tool"></section>',
            )

        self.assertIs(actual, expected)
        update_file.assert_awaited_once_with(
            access_token="qapp-user-token",
            slug="sample-tool",
            relative_path="core.html",
            content='<section data-qtool="sample-tool"></section>',
            encoding="utf-8",
        )


class UpdateQToolMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_only_supplied_fields(self) -> None:
        expected = {
            "data": {
                "slug": "sample-tool",
                "description": "Updated description",
                "article_embed_allowed": True,
            }
        }
        metadata = QToolMetadataUpdate(
            description="Updated description",
            article_embed_allowed=True,
        )

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.update_qtool_metadata",
                new=AsyncMock(return_value=expected),
            ) as update_meta,
        ):
            actual = await update_qtool_metadata(
                "sample-tool",
                metadata,
            )

        self.assertIs(actual, expected)
        update_meta.assert_awaited_once_with(
            access_token="qapp-user-token",
            slug="sample-tool",
            payload={
                "description": "Updated description",
                "article_embed_allowed": True,
            },
        )

    async def test_explicit_null_can_clear_optional_metadata(self) -> None:
        metadata = QToolMetadataUpdate(description=None)

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.update_qtool_metadata",
                new=AsyncMock(return_value={"data": {}}),
            ) as update_meta,
        ):
            await update_qtool_metadata("sample-tool", metadata)

        update_meta.assert_awaited_once_with(
            access_token="qapp-user-token",
            slug="sample-tool",
            payload={"description": None},
        )

    async def test_empty_metadata_update_is_rejected(self) -> None:
        with patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ):
            with self.assertRaisesRegex(ToolError, "At least one"):
                await update_qtool_metadata(
                    "sample-tool",
                    QToolMetadataUpdate(),
                )


class SaveQToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchanges_qapp_token_and_forwards_slug(self) -> None:
        expected = {
            "data": {
                "slug": "sample-tool",
                "saved_version": 2,
            }
        }

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.save_qtool",
                new=AsyncMock(return_value=expected),
            ) as save_call,
        ):
            actual = await save_qtool("sample-tool")

        self.assertIs(actual, expected)
        save_call.assert_awaited_once_with(
            access_token="qapp-user-token",
            slug="sample-tool",
        )


class PublishQToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchanges_qapp_token_and_forwards_version(self) -> None:
        expected = {
            "data": {
                "slug": "sample-tool",
                "published_version": 2,
            }
        }

        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.publish_qtool",
                new=AsyncMock(return_value=expected),
            ) as publish_call,
        ):
            actual = await publish_qtool(
                "sample-tool",
                version=2,
            )

        self.assertIs(actual, expected)
        publish_call.assert_awaited_once_with(
            access_token="qapp-user-token",
            slug="sample-tool",
            version=2,
        )

    async def test_version_may_be_omitted(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.qtools.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.publish_qtool",
                new=AsyncMock(return_value={"data": {}}),
            ) as publish_call,
        ):
            await publish_qtool("sample-tool")

        publish_call.assert_awaited_once_with(
            access_token="qapp-user-token",
            slug="sample-tool",
            version=None,
        )


if __name__ == "__main__":
    unittest.main()
