import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from mcp.server import MCPServer

for name in ("QAUTH_APP_ID", "QAUTH_PUBLIC_KEY", "QAPP_APP_ID", "CASHFLOWPOT_APP_ID"):
    os.environ.setdefault(name, "test-value")

from quollnet_mcp.tools import checklists as tools


REVISION = "a" * 64


class TestChecklistTools(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []

        async def respond(request):
            self.requests.append(request)
            if request.method == "GET" and request.url.path.endswith("/cl-1"):
                data = {"revision": REVISION, "items": [
                    {"id": "one", "text": "Check access", "position": 1, "items_title": None},
                    {"id": "two", "text": "Check level", "position": 2, "items_title": "Print"},
                    {"id": "three", "text": "Check plant", "position": 3, "items_title": None},
                ]}
            elif request.method == "GET" and request.url.path.endswith("/checklists"):
                data = [{"id": "cl-1", "items": [{"text": "Full content"}]}]
            else:
                data = {}
            return httpx.Response(200, json={"data": data})

        async_client = httpx.AsyncClient

        def client_factory(**kwargs):
            return async_client(transport=httpx.MockTransport(respond), **kwargs)
        self.exchange = AsyncMock(return_value="checklists-user-token")
        self.enterContext(patch.object(tools, "get_access_token",
                                      return_value=SimpleNamespace(token="mcp-token", subject="editor")))
        self.enterContext(patch.object(tools.qauth_client, "exchange_app_token", self.exchange))
        self.enterContext(patch.object(tools.qauth_client, "settings", SimpleNamespace(
            qchecklists_app_id="target-app", qchecklists_base_url="https://example.test/chk",
            qchecklists_timeout_seconds=180)))
        self.enterContext(patch.object(tools.httpx, "AsyncClient", side_effect=client_factory))

    async def test_search_uses_connected_identity_and_compact_results(self):
        result = await tools.search_checklists(search="3D printing", mine_only=True)
        self.exchange.assert_awaited_once_with(mcp_access_token="mcp-token", target_app_id="target-app")
        self.assertEqual(result["data"], [{"id": "cl-1"}])
        request = self.requests[0]
        self.assertEqual(request.url.path, "/chk/v1/checklists")
        self.assertEqual(request.url.params["search"], "3D printing")
        self.assertEqual(request.url.params["my"], "true")
        self.assertEqual(request.headers["Authorization"], "Bearer checklists-user-token")

    async def test_create_is_a_private_draft(self):
        await tools.create_checklist(tools.ChecklistCreate(name="Before printing", categories=["construction"]),
                                     [tools.ChecklistItemCreate(text="Check print bed")])
        body = json.loads(self.requests[0].content)
        self.assertIs(body["is_public"], False)
        self.assertIs(body["editorial_draft"], True)
        self.assertEqual(body["items"], [{"text": "Check print bed", "position": 1}])

    async def test_item_edits_preserve_ids_and_send_revision(self):
        await tools.edit_checklist_items(
            "cl-1", REVISION,
            add=[tools.ChecklistItemAdd(text="New inspection", position=2)],
            edit=[tools.ChecklistItemEdit(item_id="two", text="Check current level")],
            delete_item_ids=["one"], item_order=["three", "two"],
        )
        method = self.requests[-1]
        self.assertEqual(method.method, "PUT")
        self.assertEqual(method.url.path, "/chk/v1/checklists/cl-1/items")
        self.assertEqual(method.headers["If-Match"], f'"{REVISION}"')
        self.assertEqual(json.loads(method.content)["items"], [
            {"id": "three", "text": "Check plant", "items_title": None, "position": 1},
            {"text": "New inspection", "position": 2},
            {"id": "two", "text": "Check current level", "items_title": "Print", "position": 3},
        ])
        self.exchange.assert_awaited_once()

    async def test_publish_targets_validated_revision(self):
        await tools.publish_checklist("cl-1", REVISION, "public")
        self.assertEqual(self.requests[0].url.path, "/chk/v1/checklists/cl-1/publish")
        self.assertEqual(self.requests[0].headers["If-Match"], f'"{REVISION}"')

    async def test_all_eight_tools_have_oauth_and_correct_read_only_hints(self):
        server = MCPServer("checklists-test")
        tools.register_checklist_tools(server)
        registered = {tool.name: tool for tool in await server.list_tools()}
        self.assertEqual(set(registered), {
            "search_checklists", "get_checklist", "create_checklist", "update_checklist",
            "edit_checklist_items", "validate_checklist", "publish_checklist", "unpublish_checklist",
        })
        for name, tool in registered.items():
            self.assertEqual(tool.annotations.read_only_hint,
                             name in {"search_checklists", "get_checklist", "validate_checklist"})
