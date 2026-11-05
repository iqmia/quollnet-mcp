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
            if request.method == "GET" and request.url.path.endswith("/attachments/att-1"):
                data = {"id": "att-1", "owner_type": "checklist", "owner_id": "cl-1",
                        "file_name": "guide.webp", "file_type": "image/webp",
                        "file_url": "https://example.test/file/guide.webp", "alt_text": "Guide"}
            elif request.method == "GET" and request.url.path.endswith("/attachments"):
                data = [{"id": "att-1", "owner_type": "checklist", "owner_id": "cl-1"}]
            elif request.method == "GET" and request.url.path.endswith("/cl-1"):
                data = {"revision": REVISION, "is_posted": False, "hero_image": None,
                        "call_to_action_urls": [{"text": "Download PDF", "url": "https://example.test/auto.pdf"}], "items": [
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

    async def test_hero_prompt_is_part_of_create_and_update_contract(self):
        await tools.create_checklist(
            tools.ChecklistCreate(name="Before printing", categories=["construction"],
                                  main_image_prompt="A close-up of a 3D printer inspecting the bed"),
            [tools.ChecklistItemCreate(text="Check print bed")],
        )
        self.assertEqual(json.loads(self.requests[-1].content)["main_image_prompt"],
                         "A close-up of a 3D printer inspecting the bed")
        self.requests.clear()
        await tools.update_checklist("cl-1", REVISION, tools.ChecklistMetadata(
            main_image_prompt="Technician calibrating a 3D printer"))
        self.assertEqual(json.loads(self.requests[-1].content)["main_image_prompt"],
                         "Technician calibrating a 3D printer")
        self.assertEqual(self.requests[-1].headers["If-Match"], f'"{REVISION}"')

    async def test_list_uploaded_files(self):
        result = await tools.list_checklist_files("cl-1")
        self.assertEqual(result["data"][0]["id"], "att-1")
        self.assertEqual(self.requests[-1].url.params["owner_type"], "checklist")
        self.assertEqual(self.requests[-1].url.params["owner_id"], "cl-1")

    async def test_add_file_uses_authorized_file_transfer_and_multipart(self):
        file = tools.FileInput(download_url="https://files.oaiusercontent.com/signed",
                               file_id="file-1", file_name="guide.pdf", mime_type="application/pdf")
        with patch.object(tools, "download_file", new_callable=AsyncMock,
                          return_value=("guide.pdf", b"PDF CONTENT", "application/pdf")) as fetch:
            await tools.add_checklist_file("cl-1", REVISION, file, description="Installation guide")
        fetch.assert_awaited_once_with(file, max_bytes=tools.MAX_CHECKLIST_FILE_BYTES)
        request = self.requests[-1]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url.path, "/chk/v1/attachments")
        self.assertIn(b"PDF CONTENT", request.content)
        self.assertIn(b' name="owner_type"', request.content)
        self.assertIn(b"Installation guide", request.content)

    async def test_generated_image_file_uses_authorized_transfer_as_multipart(self):
        # A ChatGPT-generated image is transferable only when the host supplies
        # the authorized URL, not merely the image's file ID.
        generated = tools.FileInput(
            file_id="file_generated_hero",
            download_url="https://files.oaiusercontent.com/authorized-generated-image",
            filename="generated-hero.png",
            mime_type="image/png",
        )
        original_png = b"\x89PNG\r\n\x1a\n" + b"generated-image-test-bytes"
        with patch.object(
            tools, "download_file", new_callable=AsyncMock,
            return_value=("generated-hero.png", original_png, "image/png"),
        ) as fetch:
            await tools.add_checklist_file(
                "cl-1", REVISION, generated, alt_text="Generated checklist hero",
            )
        fetch.assert_awaited_once_with(
            generated, max_bytes=tools.MAX_CHECKLIST_FILE_BYTES,
        )
        request = self.requests[-1]
        self.assertEqual(request.url.path, "/chk/v1/attachments")
        self.assertIn(b"generated-hero.png", request.content)
        self.assertIn(b"image/png", request.content)
        self.assertIn(original_png, request.content)
        self.assertIn(b"Generated checklist hero", request.content)

    async def test_generated_image_file_requires_authorized_url(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            tools.FileInput(file_id="file_generated_hero")

    async def test_set_hero_requires_image_owned_by_checklist(self):
        await tools.set_checklist_hero("cl-1", REVISION, "att-1")
        patch_request = self.requests[-1]
        self.assertEqual(patch_request.method, "PATCH")
        self.assertEqual(json.loads(patch_request.content),
                         {"hero_image": "guide.webp", "hero_image_alt": "Guide"})
        self.assertEqual(patch_request.headers["If-Match"], f'"{REVISION}"')

    async def test_set_cta_preserves_generated_links_and_can_remove_only_custom(self):
        await tools.set_checklist_cta("cl-1", REVISION, "att-1", "Download guide")
        links = json.loads(self.requests[-1].content)["call_to_action_urls"]
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["text"], "Download PDF")
        self.assertEqual(links[1]["attachment_id"], "att-1")
        self.requests.clear()
        await tools.set_checklist_cta("cl-1", REVISION, "att-1", enabled=False)
        self.assertEqual(json.loads(self.requests[-1].content)["call_to_action_urls"],
                         [{"text": "Download PDF", "url": "https://example.test/auto.pdf"}])

    async def test_remove_clears_hero_and_custom_link_before_delete(self):
        current = {"revision": REVISION, "is_posted": False, "hero_image": "guide.webp",
                   "call_to_action_urls": [
                       {"text": "Download PDF", "url": "https://example.test/auto.pdf"},
                       {"text": "Guide", "url": "https://example.test/file/guide.webp",
                        "attachment_id": "att-1"}]}
        original = tools._request

        async def wrapped(client, method, path, **kwargs):
            if method == "GET" and path == "v1/checklists/cl-1":
                return {"data": current}
            return await original(client, method, path, **kwargs)

        with patch.object(tools, "_request", side_effect=wrapped):
            await tools.remove_checklist_file("cl-1", REVISION, "att-1")
        patch_request = next(req for req in self.requests if req.method == "PATCH")
        self.assertEqual(json.loads(patch_request.content),
                         {"hero_image": None, "hero_image_alt": None,
                          "call_to_action_urls": [{"text": "Download PDF",
                                                   "url": "https://example.test/auto.pdf"}]})
        self.assertEqual(self.requests[-1].method, "DELETE")
        self.assertEqual(self.requests[-1].url.path, "/chk/v1/attachments/att-1")

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

    async def test_all_thirteen_tools_have_oauth_and_correct_read_only_hints(self):
        server = MCPServer("checklists-test")
        tools.register_checklist_tools(server)
        registered = {tool.name: tool for tool in await server.list_tools()}
        self.assertEqual(set(registered), {
            "search_checklists", "get_checklist", "create_checklist", "update_checklist",
            "edit_checklist_items", "validate_checklist", "publish_checklist", "unpublish_checklist",
            "list_checklist_files", "add_checklist_file", "remove_checklist_file",
            "set_checklist_hero", "set_checklist_cta",
        })
        for name, tool in registered.items():
            self.assertEqual(tool.annotations.read_only_hint,
                             name in {"search_checklists", "get_checklist", "validate_checklist", "list_checklist_files"})
            if name == "add_checklist_file":
                self.assertEqual(tool.meta["openai/fileParams"], ["file"])
                schema = tool.input_schema["$defs"]["FileInput"]
                self.assertEqual(set(schema["required"]), {"download_url", "file_id"})
                self.assertTrue(
                    {"download_url", "file_id", "mime_type", "file_name", "filename"}
                    <= set(schema["properties"])
                )
            else:
                self.assertNotIn("openai/fileParams", tool.meta)
