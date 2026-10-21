import json
from unittest.mock import patch

import httpx
import unittest
from pydantic import ValidationError

from tests.qledger_support import E, U, client, settings
from tests.test_qledger_journals import journal


class QledgerClassificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_readable_classifications_roundtrip_and_filters(self):
        from quollnet_mcp.qledger import models
        from quollnet_mcp.qledger.models_accounting import JournalCreate, JournalPatch
        from quollnet_mcp.qledger.tools import journals, reports

        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"chart": "partner Elie", "project": "Gym"})

        payload = journal()
        payload["chart"] = "partner Elie"
        payload["lines"][0].update(
            project="Gym", cost_center="concrete.material.ready-mix"
        )
        async with client(handler) as c:
            with (
                patch.object(journals, "qledger_client", c),
                patch.object(reports, "qledger_client", c),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.unit_token",
                    return_value="unit",
                ),
            ):
                result = await journals.create_qledger_transaction(
                    U, JournalCreate(**payload), "key"
                )
                assert result["project"] == "Gym"
                sent = json.loads(seen[-1].content)
                assert sent["chart"] == "partner Elie"
                assert sent["lines"][0]["cost_center"] == "concrete.material.ready-mix"
                await journals.update_qledger_transaction(
                    U, E, JournalPatch(version=1, chart="main")
                )
                assert json.loads(seen[-1].content) == {"version": 1, "chart": "main"}
                query = models.JournalQuery(
                    chart="partner Elie",
                    project="Gym",
                    cost_center_prefix="concrete.material",
                    account_type="expense",
                )
                await journals.list_qledger_transactions(U, query)
                assert seen[-1].url.params["project"] == "Gym"
                await reports.get_qledger_ledger(
                    U, models.LedgerQuery(**query.model_dump())
                )
                assert seen[-1].url.params["account_type"] == "expense"
                assert seen[-1].url.params["chart"] == "partner Elie"
                await journals.list_qledger_classification_values(
                    U,
                    models.ClassificationQuery(
                        field="cost_center", chart="main", prefix="concrete."
                    ),
                )
                assert (
                    seen[-1].url.path == "/api/units/" + U + "/journal-classifications"
                )
                assert seen[-1].url.params["field"] == "cost_center"

    def test_labels_trim_and_reject_blank_chart(self):
        from quollnet_mcp.qledger.models_accounting import JournalCreate, JournalPatch

        payload = journal()
        payload["lines"][0].update(project=" Gym ", cost_center=" concrete.material ")
        parsed = JournalCreate(**payload)
        assert parsed.chart == "main"
        assert parsed.lines[0].project == "Gym"
        assert parsed.lines[0].cost_center == "concrete.material"
        for value in (None, " ", "x" * 201):
            with self.assertRaises(ValidationError):
                JournalCreate(**{**payload, "chart": value})
        with self.assertRaises(ValidationError):
            JournalPatch(version=1, chart=None)

    async def test_discovery_is_exposed_with_read_only_annotation(self):
        from quollnet_mcp.qledger.server import build_qledger_server

        tools = await build_qledger_server(settings()).list_tools()
        discovery = next(
            t for t in tools if t.name == "list_qledger_classification_values"
        )
        assert discovery.annotations.read_only_hint
        assert "existing" in discovery.description.lower()
