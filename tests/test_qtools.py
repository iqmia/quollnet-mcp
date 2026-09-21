from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.qtools import (
    QToolMetadataInput,
    create_qtool,
    delete_qtool_file,
    get_qtool_generation_spec,
    list_qtools,
    publish_qtool,
    save_qtool,
    update_qtool_metadata,
    write_qtool_file,
)


class QToolsToolTests(unittest.IsolatedAsyncioTestCase):
    def _token(self, *scopes):
        return SimpleNamespace(
            token="mcp-bearer-token",
            subject="user-1",
            scopes=list(scopes),
        )

    async def test_generation_spec_calls_qapp(self) -> None:
        expected = {
            "spec_version": 1,
            "instructions": "# Quollnet Tools V2",
        }
        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=self._token("qtools:read"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.get_qtool_generation_spec",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            actual = await get_qtool_generation_spec()

        self.assertIs(actual, expected)
        call.assert_awaited_once_with(access_token="mcp-bearer-token")

    async def test_list_qtools_passes_filters(self) -> None:
        expected = {"data": [], "pagination": {"total": 0}}
        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=self._token("qtools:read"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.list_qtools",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            actual = await list_qtools(
                page=2,
                per_page=10,
                status="saved",
            )

        self.assertIs(actual, expected)
        call.assert_awaited_once_with(
            access_token="mcp-bearer-token",
            page=2,
            per_page=10,
            status="saved",
        )

    async def test_create_qtool_builds_metadata_payload(self) -> None:
        expected = {
            "data": {
                "slug": "concrete-checker",
                "working_version": 1,
            }
        }
        metadata = QToolMetadataInput(
            description="Concrete decision aid.",
            keywords="concrete, qa qc",
            login_required=False,
        )

        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=self._token("qtools:create"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.create_qtool",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            actual = await create_qtool(
                slug="concrete-checker",
                tool_name="Concrete Checker",
                metadata=metadata,
            )

        self.assertIs(actual, expected)
        call.assert_awaited_once()
        payload = call.await_args.kwargs["payload"]
        self.assertEqual(payload["slug"], "concrete-checker")
        self.assertEqual(payload["tool_name"], "Concrete Checker")
        self.assertEqual(
            payload["metadata"]["description"],
            "Concrete decision aid.",
        )
        self.assertIs(payload["metadata"]["login_required"], False)
        self.assertNotIn("hero_image", payload["metadata"])

    async def test_write_qtool_file_passes_complete_file(self) -> None:
        expected = {"data": {"working_version": 2}}
        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=self._token("qtools:edit"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.write_qtool_file",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            actual = await write_qtool_file(
                slug="concrete-checker",
                path="js/app.js",
                content="const x = 1;",
            )

        self.assertIs(actual, expected)
        call.assert_awaited_once_with(
            access_token="mcp-bearer-token",
            slug="concrete-checker",
            relative_path="js/app.js",
            payload={
                "encoding": "utf-8",
                "content": "const x = 1;",
            },
        )

    async def test_update_metadata_only_sends_requested_fields(self) -> None:
        expected = {"data": {"slug": "concrete-checker"}}
        metadata = QToolMetadataInput(
            seo_title="Concrete Checker | Quollnet",
        )

        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=self._token("qtools:edit"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.update_qtool_metadata",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            actual = await update_qtool_metadata(
                slug="concrete-checker",
                metadata=metadata,
            )

        self.assertIs(actual, expected)
        self.assertEqual(
            call.await_args.kwargs["payload"],
            {"seo_title": "Concrete Checker | Quollnet"},
        )

    async def test_delete_qtool_file_calls_qapp(self) -> None:
        expected = {"data": {"deleted": True}}
        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=self._token("qtools:edit"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.delete_qtool_file",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            actual = await delete_qtool_file(
                slug="concrete-checker",
                path="js/old.js",
            )

        self.assertIs(actual, expected)
        call.assert_awaited_once_with(
            access_token="mcp-bearer-token",
            slug="concrete-checker",
            relative_path="js/old.js",
        )

    async def test_save_validation_error_is_exposed_to_model(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=self._token("qtools:edit"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.save_qtool",
                new=AsyncMock(
                    side_effect=QAppClientError(
                        "qApp returned HTTP 422: Tool package validation failed: "
                        "core.html must contain a root"
                    )
                ),
            ),
        ):
            with self.assertRaisesRegex(
                ToolError,
                "core.html must contain a root",
            ):
                await save_qtool(slug="concrete-checker")

    async def test_publish_passes_selected_version(self) -> None:
        expected = {"data": {"published_version": 2}}
        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=self._token("qtools:publish"),
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.publish_qtool",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            actual = await publish_qtool(
                slug="concrete-checker",
                version=2,
            )

        self.assertIs(actual, expected)
        call.assert_awaited_once_with(
            access_token="mcp-bearer-token",
            slug="concrete-checker",
            version=2,
        )

    async def test_missing_qtools_scope_is_rejected(self) -> None:
        with patch(
            "quollnet_mcp.tools.qtools.get_access_token",
            return_value=self._token("quollnet:access"),
        ):
            with self.assertRaisesRegex(ToolError, "qtools:read"):
                await list_qtools()


if __name__ == "__main__":
    unittest.main()
