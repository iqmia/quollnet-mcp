from typing import Annotated, Any, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.services.qapp_client import QAppClientError


async def search_articles(
    q: Annotated[str | None, Field(max_length=250)] = None,
    topic: Annotated[str | None, Field(max_length=100)] = None,
    lang: str | None = None,
    status: Literal["all", "published", "draft"] = "all",
    sort_by: Literal["modified", "published", "title"] = "modified",
    sort_dir: Literal["asc", "desc"] = "desc",
    page: Annotated[int, Field(ge=1)] = 1,
    per_page: Annotated[int, Field(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    """Search published articles and the authenticated user's drafts."""
    access_token = get_access_token()
    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    try:
        return await qapp_client.search_articles(
            access_token=access_token.token,
            q=q,
            topic=topic,
            lang=lang,
            status=status,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            per_page=per_page,
        )
    except QAppClientError as error:
        raise ToolError("Article search failed") from error

async def create_article_draft(
    subject: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description=(
                "Article title. It must exactly match the text inside "
                "the single H1 at the beginning of body."
            ),
        ),
    ],
    path: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
            description=(
                "Unique lowercase kebab-case article slug, without a "
                "leading or trailing slash."
            ),
        ),
    ],
    description: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description="Concise SEO description for the article.",
        ),
    ],
    keywords: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description="Comma-separated article keywords.",
        ),
    ],
    body: Annotated[
        str,
        Field(
            min_length=1,
            max_length=1_000_000,
            description=(
                "Complete article HTML. The first top-level element must "
                "be one H1 matching subject. The second must be a Quick "
                "Answer paragraph matching authoring_data.answer_summary. "
                "Scripts, event handlers, classes, IDs, embedded media, "
                "and unsafe HTML are not allowed."
            ),
        ),
    ],
    primary_article_topic: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="Primary Quollnet article-topic slug.",
        ),
    ],
    authoring_data: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Structured article-authoring metadata following the "
                "qApp article_draft_create.v1 contract. It must contain "
                "schema_version, answer_summary, search, images, "
                "references, internal_links, downloads, tools, and "
                "social. schema_version must be 1."
            ),
        ),
    ],
    article_topics: Annotated[
        list[str] | None,
        Field(
            max_length=5,
            description=(
                "Zero to five additional Quollnet topic slugs. Do not "
                "repeat primary_article_topic."
            ),
        ),
    ] = None,
    faq: Annotated[
        str,
        Field(
            max_length=50_000,
            description=(
                "Optional FAQ text. Each block must contain exactly a "
                "'q:' line followed by an 'a:' line. Separate pairs with "
                "a blank line."
            ),
        ),
    ] = "",
    lang: Annotated[
        str,
        Field(
            min_length=2,
            max_length=20,
            description="Supported article language code. Default: en.",
        ),
    ] = "en",
    page_type: Literal["article"] = "article",
) -> dict[str, Any]:
    """
    Create a new unpublished Quollnet article draft owned by the
    authenticated user.

    This tool cannot publish an article, select another owner, mark a draft
    ready for publication, or set protected publication fields. qApp
    performs the authoritative validation and ownership assignment.
    """
    access_token = get_access_token()

    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    scopes = set(access_token.scopes or [])
    if "articles:create" not in scopes:
        raise ToolError(
            "The connected account does not have articles:create permission"
        )

    payload: dict[str, Any] = {
        "subject": subject,
        "path": path,
        "description": description,
        "keywords": keywords,
        "body": body,
        "faq": faq,
        "primary_article_topic": primary_article_topic,
        "article_topics": article_topics or [],
        "lang": lang,
        "page_type": page_type,
        "authoring_data": authoring_data,
    }

    try:
        return await qapp_client.create_article_draft(
            access_token=access_token.token,
            payload=payload,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error