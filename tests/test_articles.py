
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")

from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.services.article_authoring import build_authoring_data
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.articles import (
    create_article_draft,
    edit_article_draft,
    get_article,
    get_internal_link_candidates,
    search_articles,
)

class CreateArticleDraftTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_token_and_payload(self) -> None:
        token = SimpleNamespace(
            token="bearer-token",
            subject="user-1",
            scopes=["articles:read", "articles:create"],
        )

        answer_summary = "A concise practical answer."

        expected_authoring_data = build_authoring_data(
            slug="test-article-draft",
            answer_summary=answer_summary,
            primary_keyword="test article",
            search_intent="Provide a practical test article.",
            target_audience="Construction professionals",
            key_questions=[
                "What does this test article explain?",
            ],
        )

        expected = {
            "message": "Article draft created",
            "data": {
                "id": "article-1",
                "slug": "test-article-draft",
                "subject": "Test Article Draft",
                "posted": False,
                "ready_to_publish": False,
            },
        }

        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=token,
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.create_article_draft",
                new=AsyncMock(return_value=expected),
            ) as create,
        ):
            actual = await create_article_draft(
                subject="Test Article Draft",
                path="test-article-draft",
                description="A test article draft description.",
                keywords="test article, draft",
                body=(
                    "<h1>Test Article Draft</h1>"
                    "<p>A concise practical answer.</p>"
                ),
                primary_article_topic="qa-qc",
                answer_summary=answer_summary,
                primary_keyword="test article",
                search_intent="Provide a practical test article.",
                target_audience="Construction professionals",
                key_questions=[
                    "What does this test article explain?",
                ],
                article_topics=[],
                faq="",
                lang="en",
                page_type="article",
            )

        self.assertIs(actual, expected)

        create.assert_awaited_once_with(
            access_token="bearer-token",
            payload={
                "subject": "Test Article Draft",
                "path": "test-article-draft",
                "description": "A test article draft description.",
                "keywords": "test article, draft",
                "body": (
                    "<h1>Test Article Draft</h1>"
                    "<p>A concise practical answer.</p>"
                ),
                "faq": "",
                "primary_article_topic": "qa-qc",
                "article_topics": [],
                "lang": "en",
                "page_type": "article",
                "authoring_data": expected_authoring_data,
            },
        )

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


class GetInternalLinkCandidatesTests(unittest.IsolatedAsyncioTestCase):
    _QAPP_RESPONSE = {
        "message": "ok",
        "data": {
            "articles": [{"slug": "article-a", "title": "Article A"}],
            "checklists": [{"slug": "checklist-b", "title": "Checklist B"}],
            "methods": [{"slug": "method-c", "title": "Method C"}],
        },
    }

    def _token(self, scopes=("articles:read",), subject="user-1"):
        return SimpleNamespace(
            token="bearer-token",
            subject=subject,
            scopes=list(scopes),
        )

    async def test_forwards_access_token(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_internal_link_candidates",
                new=AsyncMock(return_value=self._QAPP_RESPONSE),
            ) as mock_call,
        ):
            await get_internal_link_candidates(text="some text")

        mock_call.assert_awaited_once()
        _, kwargs = mock_call.call_args
        self.assertEqual(kwargs["access_token"], "bearer-token")

    async def test_forwards_text_unchanged(self) -> None:
        article_text = "Detailed article text about construction quality."
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_internal_link_candidates",
                new=AsyncMock(return_value=self._QAPP_RESPONSE),
            ) as mock_call,
        ):
            await get_internal_link_candidates(text=article_text)

        _, kwargs = mock_call.call_args
        self.assertEqual(kwargs["text"], article_text)

    async def test_top_n_defaults_to_10(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_internal_link_candidates",
                new=AsyncMock(return_value=self._QAPP_RESPONSE),
            ) as mock_call,
        ):
            await get_internal_link_candidates(text="text")

        _, kwargs = mock_call.call_args
        self.assertEqual(kwargs["top_n"], 10)

    async def test_exclude_slugs_defaults_to_none(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_internal_link_candidates",
                new=AsyncMock(return_value=self._QAPP_RESPONSE),
            ) as mock_call,
        ):
            await get_internal_link_candidates(text="text")

        _, kwargs = mock_call.call_args
        self.assertIsNone(kwargs["exclude_slugs"])

    async def test_explicit_top_n_and_exclude_slugs_are_forwarded(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_internal_link_candidates",
                new=AsyncMock(return_value=self._QAPP_RESPONSE),
            ) as mock_call,
        ):
            await get_internal_link_candidates(
                text="text",
                top_n=5,
                exclude_slugs=["draft-slug"],
            )

        _, kwargs = mock_call.call_args
        self.assertEqual(kwargs["top_n"], 5)
        self.assertEqual(kwargs["exclude_slugs"], ["draft-slug"])

    async def test_returns_qapp_response_unchanged(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_internal_link_candidates",
                new=AsyncMock(return_value=self._QAPP_RESPONSE),
            ),
        ):
            result = await get_internal_link_candidates(text="text")

        self.assertIs(result, self._QAPP_RESPONSE)

    async def test_result_groups_are_not_reranked_or_mutated(self) -> None:
        """The three result groups must be returned as-is from qApp."""
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_internal_link_candidates",
                new=AsyncMock(return_value=self._QAPP_RESPONSE),
            ),
        ):
            result = await get_internal_link_candidates(text="text")

        data = result["data"]
        self.assertIn("articles", data)
        self.assertIn("checklists", data)
        self.assertIn("methods", data)
        # Verify all three groups are preserved as distinct lists (not flattened)
        self.assertIsInstance(data["articles"], list)
        self.assertIsInstance(data["checklists"], list)
        self.assertIsInstance(data["methods"], list)

    async def test_missing_authentication_raises_tool_error(self) -> None:
        with patch(
            "quollnet_mcp.tools.articles.get_access_token", return_value=None
        ):
            with self.assertRaises(ToolError):
                await get_internal_link_candidates(text="text")

    async def test_missing_subject_raises_tool_error(self) -> None:
        token = SimpleNamespace(token="bearer-token", subject=None, scopes=["articles:read"])
        with patch(
            "quollnet_mcp.tools.articles.get_access_token", return_value=token
        ):
            with self.assertRaises(ToolError):
                await get_internal_link_candidates(text="text")

    async def test_missing_articles_read_scope_raises_tool_error(self) -> None:
        token = SimpleNamespace(token="bearer-token", subject="user-1", scopes=[])
        with patch(
            "quollnet_mcp.tools.articles.get_access_token", return_value=token
        ):
            with self.assertRaisesRegex(ToolError, "articles:read"):
                await get_internal_link_candidates(text="text")

    async def test_qapp_error_is_converted_to_tool_error(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_internal_link_candidates",
                new=AsyncMock(side_effect=QAppClientError("upstream error")),
            ),
        ):
            with self.assertRaises(ToolError):
                await get_internal_link_candidates(text="text")


class AppRegistrationTests(unittest.TestCase):
    def test_get_internal_link_candidates_is_registered(self) -> None:
        import app as app_module

        tool_names = {tool.name for tool in app_module.mcp._tool_manager._tools.values()}
        self.assertIn("get_internal_link_candidates", tool_names)


# ---------------------------------------------------------------------------
# get_article
# ---------------------------------------------------------------------------

class GetArticleTests(unittest.IsolatedAsyncioTestCase):
    def _token(self, scopes=("articles:read",), subject="user-1"):
        return SimpleNamespace(
            token="bearer-token",
            subject=subject,
            scopes=list(scopes),
        )

    _ARTICLE_RESPONSE = {
        "message": "ok",
        "data": {
            "id": "art-42",
            "subject": "Test Article",
            "body": "<p>Hello</p>",
            "authoring_data": {"answer_summary": "A summary"},
        },
    }

    async def test_forwards_article_id_and_access_token(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_article",
                new=AsyncMock(return_value=self._ARTICLE_RESPONSE),
            ) as mock_get,
        ):
            result = await get_article(article_id="art-42")

        self.assertIs(result, self._ARTICLE_RESPONSE)
        mock_get.assert_awaited_once_with(
            access_token="bearer-token",
            article_id="art-42",
        )

    async def test_missing_authentication_raises_tool_error(self) -> None:
        with patch("quollnet_mcp.tools.articles.get_access_token", return_value=None):
            with self.assertRaises(ToolError):
                await get_article(article_id="art-1")

    async def test_missing_scope_raises_tool_error(self) -> None:
        token = SimpleNamespace(token="t", subject="user-1", scopes=[])
        with patch("quollnet_mcp.tools.articles.get_access_token", return_value=token):
            with self.assertRaisesRegex(ToolError, "articles:read"):
                await get_article(article_id="art-1")

    async def test_qapp_error_becomes_tool_error(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_article",
                new=AsyncMock(side_effect=QAppClientError("not found")),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "not found"):
                await get_article(article_id="art-1")


# ---------------------------------------------------------------------------
# edit_article_draft
# ---------------------------------------------------------------------------

class EditArticleDraftTests(unittest.IsolatedAsyncioTestCase):
    def _token(self, scopes=("articles:read", "articles:edit"), subject="user-1"):
        return SimpleNamespace(
            token="bearer-token",
            subject=subject,
            scopes=list(scopes),
        )

    _EDIT_RESPONSE = {"message": "Article draft updated", "data": {"id": "art-42"}}

    _CURRENT_ARTICLE = {
        "message": "ok",
        "data": {
            "id": "art-42",
            "authoring_data": {
                "schema_version": 1,
                "answer_summary": "Old summary",
                "search": {
                    "primary_keyword": "old keyword",
                    "search_intent": "old intent",
                    "target_audience": "old audience",
                    "key_questions": [],
                },
                "images": {
                    "hero": {"prompt": "", "alt_text": "", "suggested_filename": ""},
                    "og": {"prompt": "", "alt_text": "", "suggested_filename": ""},
                    "infographic": {
                        "needed": False,
                        "prompt": "",
                        "alt_text": "",
                        "suggested_filename": "",
                    },
                },
                "references": [],
                "internal_links": [{"article_id": "x", "slug": "x", "title": "X",
                                     "url": "https://example.com", "anchor_text": "X",
                                     "reason": "r"}],
                "downloads": [],
                "tools": [],
                "social": {
                    "brief": {
                        "primary_angle": "Old summary",
                        "target_audience": "old audience",
                        "key_points": [],
                        "strongest_hook": "Old summary",
                        "cta": "Read more.",
                        "avoid": [],
                    }
                },
            },
        },
    }

    async def test_body_only_edit_sends_only_body(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.edit_article_draft",
                new=AsyncMock(return_value=self._EDIT_RESPONSE),
            ) as mock_edit,
        ):
            await edit_article_draft(article_id="art-42", body="<p>New body</p>")

        mock_edit.assert_awaited_once_with(
            access_token="bearer-token",
            article_id="art-42",
            payload={"body": "<p>New body</p>"},
        )

    async def test_empty_edit_raises_tool_error_without_calling_qapp(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.edit_article_draft",
                new=AsyncMock(),
            ) as mock_edit,
        ):
            with self.assertRaisesRegex(ToolError, "No article changes"):
                await edit_article_draft(article_id="art-42")

        mock_edit.assert_not_awaited()

    async def test_missing_articles_edit_scope_raises_tool_error(self) -> None:
        token = SimpleNamespace(token="t", subject="user-1", scopes=["articles:read"])
        with patch("quollnet_mcp.tools.articles.get_access_token", return_value=token):
            with self.assertRaisesRegex(ToolError, "articles:edit"):
                await edit_article_draft(article_id="art-42", body="<p>x</p>")

    async def test_authoring_edit_retrieves_current_and_merges(self) -> None:
        """Changing answer_summary must fetch current article and preserve
        unrelated authoring_data fields (e.g. existing internal_links)."""
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_article",
                new=AsyncMock(return_value=self._CURRENT_ARTICLE),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.edit_article_draft",
                new=AsyncMock(return_value=self._EDIT_RESPONSE),
            ) as mock_edit,
        ):
            await edit_article_draft(
                article_id="art-42",
                answer_summary="New summary",
            )

        _, kwargs = mock_edit.call_args
        authoring = kwargs["payload"]["authoring_data"]
        # Changed field is updated
        self.assertEqual(authoring["answer_summary"], "New summary")
        # Unrelated field is preserved
        self.assertEqual(len(authoring["internal_links"]), 1)
        self.assertEqual(authoring["internal_links"][0]["article_id"], "x")
        # primary_keyword was NOT changed
        self.assertEqual(authoring["search"]["primary_keyword"], "old keyword")

    async def test_replacing_references_with_empty_list(self) -> None:
        """Explicitly passing references=[] must clear references in the payload."""
        with (
            patch(
                "quollnet_mcp.tools.articles.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.get_article",
                new=AsyncMock(return_value=self._CURRENT_ARTICLE),
            ),
            patch(
                "quollnet_mcp.tools.articles.qapp_client.edit_article_draft",
                new=AsyncMock(return_value=self._EDIT_RESPONSE),
            ) as mock_edit,
        ):
            await edit_article_draft(article_id="art-42", references=[])

        _, kwargs = mock_edit.call_args
        authoring = kwargs["payload"]["authoring_data"]
        self.assertEqual(authoring["references"], [])


if __name__ == "__main__":
    unittest.main()
