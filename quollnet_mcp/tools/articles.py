from typing import Annotated, Any, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.services.article_authoring import build_authoring_data


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

# the following classes 
class ArticleReferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=500)]
    url: Annotated[str, Field(min_length=1, pattern=r"^https?://")]
    publisher: Annotated[str, Field(min_length=1, max_length=500)]
    reference_type: Annotated[str, Field(min_length=1, max_length=100)]
    notes: Annotated[str, Field(max_length=1000)] = ""


class ArticleInternalLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    article_id: Annotated[str, Field(min_length=1, max_length=250)]
    slug: Annotated[str, Field(min_length=1, max_length=250)]
    title: Annotated[str, Field(min_length=1, max_length=500)]
    url: Annotated[str, Field(min_length=1, pattern=r"^https?://")]
    anchor_text: Annotated[str, Field(min_length=1, max_length=500)]
    reason: Annotated[str, Field(min_length=1, max_length=1000)]


class ArticleToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=500)]
    url_slug: Annotated[str, Field(min_length=1, max_length=250)]
    shortcode: Annotated[str, Field(min_length=1, max_length=500)]
    placement_note: Annotated[str, Field(max_length=1000)] = ""
    

async def create_article_draft(
    subject: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description=(
                "Human-readable article title."
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
            description="Article SEO meta description"
        ),
    ],
    keywords: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description="Comma-separated article keywords."
        ),
    ],
    body: Annotated[
        str,
        Field(
            min_length=1,
            max_length=1_000_000,
            description=(
                "Complete article HTML."
            ),
        ),
    ],
    primary_article_topic: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="Primary Quollnet article-topic slug."
        ),
    ],
    answer_summary: Annotated[
        str,
        Field(
            min_length=1,
            max_length=2000,
            description=(
                "Plain-text article answer summary."
            ),
        ),
    ],
    primary_keyword: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Main search keyword targeted by the article."
        ),
    ],
    search_intent: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description=(
                "Search intent addressed by the article."
            ),
        ),
    ],
    target_audience: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description=(
                "Primary professional audience."
            ),
        ),
    ],
    key_questions: Annotated[
        list[str] | None,
        Field(
            max_length=20,
            description=(
                "Important questions addressed by the article."
            ),
        ),
    ] = None,
    hero_image_prompt: Annotated[
        str,
        Field(
            max_length=2000,
            description="Prompt for generating the article hero image."
        ),
    ] = "",
    hero_image_alt_text: Annotated[
        str,
        Field(
            max_length=500,
            description="Accessible alt text for the hero image.",
        ),
    ] = "",
    og_image_prompt: Annotated[
        str,
        Field(
            max_length=2000,
            description=(
                "Open Graph image prompt."
            ),
        ),
    ] = "",
    og_image_alt_text: Annotated[
        str,
        Field(
            max_length=500,
            description="Accessible alt text for the Open Graph image.",
        ),
    ] = "",
    infographic_needed: Annotated[
        bool,
        Field(
            description=(
                "Whether the article should have a supporting infographic."
            ),
        ),
    ] = False,
    infographic_prompt: Annotated[
        str,
        Field(
            max_length=2000,
            description=(
                "Prompt for the supporting infographic when one is needed."
            ),
        ),
    ] = "",
    infographic_alt_text: Annotated[
        str,
        Field(
            max_length=500,
            description="Accessible alt text for the infographic.",
        ),
    ] = "",
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
                "FAQ - formatted as q: question text, a: answer text"
            ),
        ),
    ] = "",
    lang: Annotated[
        str,
        Field(
            min_length=2,
            max_length=20,
            description="Article language code.",
        ),
    ] = "en",
    page_type: Literal["article"] = "article",
    references: Annotated[
        list[ArticleReferenceInput] | None,
        Field(
            description=(
                "External references used by the article. These should also "
                "appear as visible reference links at the bottom of the body."
            )
        ),
    ] = None,

    internal_links: Annotated[
        list[ArticleInternalLinkInput] | None,
        Field(
            description=(
                "Selected Quollnet internal links returned by the internal-link "
                "candidate workflow and actually used in the article body."
            )
        ),
    ] = None,

    tools: Annotated[
        list[ArticleToolInput] | None,
        Field(
            description=(
                "Quollnet tools intentionally embedded in the article body "
                "using the trusted [[qtool:tool-url-slug]] shortcode."
            )
        ),
] = None,
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
    authoring_data = build_authoring_data(
        slug=path,
        answer_summary=answer_summary,
        primary_keyword=primary_keyword,
        search_intent=search_intent,
        target_audience=target_audience,
        key_questions=key_questions,
        hero_image_prompt=hero_image_prompt,
        hero_image_alt_text=hero_image_alt_text,
        og_image_prompt=og_image_prompt,
        og_image_alt_text=og_image_alt_text,
        infographic_needed=infographic_needed,
        infographic_prompt=infographic_prompt,
        infographic_alt_text=infographic_alt_text,
        references=[item.model_dump() for item in references or []],
        internal_links=[item.model_dump() for item in internal_links or []],
        tools=[item.model_dump() for item in tools or []],
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

async def get_internal_link_candidates(
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100_000,
            description=(
                "The completed article text or a detailed final summary used "
                "to find relevant Quollnet internal links."
            ),
        ),
    ],
    top_n: Annotated[int, Field(ge=1, le=20)] = 10,
    exclude_slugs: list[str] | None = None,
) -> dict[str, Any]:
    """Find ranked Quollnet internal-link candidates for a substantially completed
    article. Returns related articles, checklists associated with those articles,
    and related Method Statement/ITP candidates. Review the candidates and use
    only links that genuinely help the reader; do not insert all returned links
    automatically."""
    access_token = get_access_token()

    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    scopes = set(access_token.scopes or [])
    if "articles:read" not in scopes:
        raise ToolError(
            "The connected account does not have articles:read permission"
        )

    try:
        return await qapp_client.get_internal_link_candidates(
            access_token=access_token.token,
            text=text,
            top_n=top_n,
            exclude_slugs=exclude_slugs,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def get_article_authoring_policy() -> dict[str, Any]:
    """Retrieve the current authoritative Quollnet article-authoring policy."""
    access_token = get_access_token()

    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    scopes = set(access_token.scopes or [])
    if "articles:read" not in scopes:
        raise ToolError(
            "The connected account does not have articles:read permission"
        )

    try:
        return await qapp_client.get_article_authoring_policy(
            access_token=access_token.token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error