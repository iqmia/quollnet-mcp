import json
import unittest
from unittest.mock import patch
from tests.qledger_support import U, E, client


class QledgerUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_unit_token_redaction_and_mapping(self):
        from quollnet_mcp.qledger.tools import units
        from quollnet_mcp.qledger.models import UnitCreate, MemberInvite, MemberRoles

        seen = []

        def handler(req):
            seen.append(req)
            if req.url.path.endswith("/records"):
                return __import__("httpx").Response(
                    200, json={"items": [], "total": 0, "page": 1, "per_page": 20}
                )
            return __import__("httpx").Response(
                200,
                json={
                    "unit": {"id": U, "name": "Company", "token": "nested-secret"},
                    "token": "top-secret",
                    "parent": None,
                    "children_page": [],
                },
            )

        async with client(handler) as c:
            with (
                patch.object(units, "qledger_client", c),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.application_token",
                    return_value="app",
                ),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.unit_token",
                    return_value="unit",
                ),
            ):
                result = await units.create_qledger_unit(UnitCreate(name="Company"))
                self.assertEqual(result, {"unit": {"id": U, "name": "Company"}})
                result = await units.load_qledger_unit(U)
                self.assertNotIn("secret", json.dumps(result))
                self.assertEqual(result["ai_instructions"], [])
                self.assertEqual(result["ai_instructions_total"], 0)
                self.assertEqual(seen[-1].url.params["types"], "ai_instruction")
                self.assertEqual(seen[-1].url.params["linked_to_object"], "unit")
                self.assertEqual(seen[-1].url.params["linked_to_object_id"], U)
                calls = [
                    (lambda: units.list_qledger_units(), "GET", "/api/units"),
                    (
                        lambda: units.list_qledger_members(U),
                        "GET",
                        f"/api/units/{U}/members",
                    ),
                    (
                        lambda: units.invite_qledger_member(
                            U, MemberInvite(email="a@example.com", send_email=False)
                        ),
                        "POST",
                        f"/api/units/{U}/members/invite",
                    ),
                    (
                        lambda: units.remove_qledger_member(U, E),
                        "DELETE",
                        f"/api/units/{U}/members/{E}",
                    ),
                    (
                        lambda: units.list_qledger_roles(U),
                        "GET",
                        f"/api/units/{U}/roles",
                    ),
                    (
                        lambda: units.add_qledger_member_roles(
                            U, E, MemberRoles(roles=["controller"])
                        ),
                        "POST",
                        f"/api/units/{U}/members/{E}/roles",
                    ),
                    (
                        lambda: units.remove_qledger_member_role(
                            U, E, "role/with space"
                        ),
                        "DELETE",
                        f"/api/units/{U}/members/{E}/roles/role/with space",
                    ),
                ]
                for fn, method, path in calls:
                    await fn()
                    self.assertEqual(
                        (seen[-1].method, seen[-1].url.path), (method, path)
                    )
                self.assertIn("role%2Fwith%20space", str(seen[-1].url))
                self.assertIs(json.loads(seen[5].content)["send_email"], False)

    async def test_load_exposes_only_authorized_unit_instruction_records(self):
        import httpx

        from quollnet_mcp.qledger.tools import units

        def handler(req):
            if req.url.path.endswith("/records"):
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {"id": E, "version": 2, "type": "ai_instruction",
                             "is_postable": False,
                             "data": {"purpose": "Building accounts",
                                      "rules": ["Record annual contributions"]}},
                            {"id": U, "version": 1, "type": "invoice",
                             "is_postable": True, "data": {"secret": "not instructions"}},
                        ],
                        "total": 1,
                    },
                )
            return httpx.Response(
                200,
                json={"unit": {"id": U, "name": "Building"},
                      "token": "top-secret", "parent": None, "children_page": []},
            )

        async with client(handler) as c:
            with (
                patch.object(units, "qledger_client", c),
                patch("quollnet_mcp.qledger.tools.common.auth.application_token",
                      return_value="app"),
                patch("quollnet_mcp.qledger.tools.common.auth.unit_token",
                      return_value="unit"),
            ):
                result = await units.load_qledger_unit(U)
                self.assertEqual(result["ai_instructions_total"], 1)
                self.assertEqual(
                    result["ai_instructions"],
                    [{"id": E, "version": 2, "data": {
                        "purpose": "Building accounts",
                        "rules": ["Record annual contributions"],
                    }}],
                )
                self.assertNotIn("secret", json.dumps(result))

    async def test_load_denied_record_view_keeps_unit_access(self):
        import httpx

        from quollnet_mcp.qledger.tools import units

        def handler(req):
            if req.url.path.endswith("/records"):
                return httpx.Response(403, json={"message": "Permission required"})
            return httpx.Response(
                200,
                json={"unit": {"id": U, "name": "Building"},
                      "token": "top-secret", "parent": None, "children_page": []},
            )

        async with client(handler) as c:
            with (
                patch.object(units, "qledger_client", c),
                patch("quollnet_mcp.qledger.tools.common.auth.application_token",
                      return_value="app"),
                patch("quollnet_mcp.qledger.tools.common.auth.unit_token",
                      return_value="unit"),
            ):
                result = await units.load_qledger_unit(U)
                self.assertEqual(result["ai_instructions_access"], "not_authorized")
                self.assertNotIn("ai_instructions", result)
                self.assertNotIn("secret", json.dumps(result))
