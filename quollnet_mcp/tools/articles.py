import base64
from typing import Annotated, Any, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.services.article_authoring import build_authoring_data, merge_authoring_data_for_edit
from quollnet_mcp.tools.qapp_auth import qapp_user_token


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
    access_token = await qapp_user_token()
    try:
        return await qapp_client.search_articles(
            access_token=access_token,
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
    access_token = await qapp_user_token()
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
            access_token=access_token,
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
    access_token = await qapp_user_token()

    try:
        return await qapp_client.get_internal_link_candidates(
            access_token=access_token,
            text=text,
            top_n=top_n,
            exclude_slugs=exclude_slugs,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def get_article_authoring_policy() -> dict[str, Any]:
    """Retrieve the current authoritative Quollnet article-authoring policy."""
    access_token = await qapp_user_token()

    try:
        return await qapp_client.get_article_authoring_policy(
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def get_article(
    article_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description=(
                "Article ID returned by search_articles or create_article_draft."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Retrieve one Quollnet article by ID. Use this after search_articles when the
    full article content is needed for review or editing. Published articles may
    be readable, while private drafts are subject to qApp ownership rules."""
    access_token = await qapp_user_token()

    try:
        return await qapp_client.get_article(
            access_token=access_token,
            article_id=article_id,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


# Sentinel used to detect "not supplied" vs explicit None/empty-list.
_UNSET = object()


async def edit_article_draft(
    article_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description="ID of the existing unpublished draft to edit.",
        ),
    ],
    subject: Annotated[str | None, Field(max_length=250)] = None,
    path: Annotated[
        str | None,
        Field(max_length=250, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
    ] = None,
    description: Annotated[str | None, Field(max_length=250)] = None,
    keywords: Annotated[str | None, Field(max_length=250)] = None,
    body: Annotated[str | None, Field(max_length=1_000_000)] = None,
    faq: Annotated[str | None, Field(max_length=50_000)] = None,
    primary_article_topic: Annotated[str | None, Field(max_length=100)] = None,
    article_topics: Annotated[
        list[str] | None,
        Field(
            max_length=5,
            description=(
                "Additional topic slugs. An empty list intentionally clears "
                "additional topics."
            ),
        ),
    ] = _UNSET,  # type: ignore[assignment]
    lang: str | None = None,
    page_type: Literal["article"] | None = None,
    # Authoring fields — all optional
    answer_summary: Annotated[str | None, Field(max_length=2000)] = None,
    primary_keyword: Annotated[str | None, Field(max_length=500)] = None,
    search_intent: Annotated[str | None, Field(max_length=500)] = None,
    target_audience: Annotated[str | None, Field(max_length=500)] = None,
    key_questions: list[str] | None = None,
    hero_image_prompt: Annotated[str | None, Field(max_length=2000)] = None,
    hero_image_alt_text: Annotated[str | None, Field(max_length=500)] = None,
    og_image_prompt: Annotated[str | None, Field(max_length=2000)] = None,
    og_image_alt_text: Annotated[str | None, Field(max_length=500)] = None,
    infographic_needed: bool | None = None,
    infographic_prompt: Annotated[str | None, Field(max_length=2000)] = None,
    infographic_alt_text: Annotated[str | None, Field(max_length=500)] = None,
    references: list[ArticleReferenceInput] | None = None,
    internal_links: list[ArticleInternalLinkInput] | None = None,
    tools: list[ArticleToolInput] | None = None,
) -> dict[str, Any]:
    """Edit selected fields of an existing unpublished Quollnet article draft.
    Retrieve the draft first when reviewing or substantially revising existing
    content. qApp performs authoritative validation and will reject edits to
    published articles."""
    access_token = await qapp_user_token()

    # Build the PATCH payload from only the explicitly supplied direct fields.
    payload: dict[str, Any] = {}
    if subject is not None:
        payload["subject"] = subject
    if path is not None:
        payload["path"] = path
    if description is not None:
        payload["description"] = description
    if keywords is not None:
        payload["keywords"] = keywords
    if body is not None:
        payload["body"] = body
    if faq is not None:
        payload["faq"] = faq
    if primary_article_topic is not None:
        payload["primary_article_topic"] = primary_article_topic
    # article_topics uses _UNSET sentinel so an empty list is distinguishable.
    if article_topics is not _UNSET:
        payload["article_topics"] = article_topics
    if lang is not None:
        payload["lang"] = lang
    if page_type is not None:
        payload["page_type"] = page_type

    # Detect whether any authoring field was explicitly supplied.
    _authoring_kwargs: dict[str, Any] = {}
    if answer_summary is not None:
        _authoring_kwargs["answer_summary"] = answer_summary
    if primary_keyword is not None:
        _authoring_kwargs["primary_keyword"] = primary_keyword
    if search_intent is not None:
        _authoring_kwargs["search_intent"] = search_intent
    if target_audience is not None:
        _authoring_kwargs["target_audience"] = target_audience
    if key_questions is not None:
        _authoring_kwargs["key_questions"] = key_questions
    if hero_image_prompt is not None:
        _authoring_kwargs["hero_image_prompt"] = hero_image_prompt
    if hero_image_alt_text is not None:
        _authoring_kwargs["hero_image_alt_text"] = hero_image_alt_text
    if og_image_prompt is not None:
        _authoring_kwargs["og_image_prompt"] = og_image_prompt
    if og_image_alt_text is not None:
        _authoring_kwargs["og_image_alt_text"] = og_image_alt_text
    if infographic_needed is not None:
        _authoring_kwargs["infographic_needed"] = infographic_needed
    if infographic_prompt is not None:
        _authoring_kwargs["infographic_prompt"] = infographic_prompt
    if infographic_alt_text is not None:
        _authoring_kwargs["infographic_alt_text"] = infographic_alt_text
    if references is not None:
        _authoring_kwargs["references"] = [r.model_dump() for r in references]
    if internal_links is not None:
        _authoring_kwargs["internal_links"] = [l.model_dump() for l in internal_links]
    if tools is not None:
        _authoring_kwargs["tools"] = [t.model_dump() for t in tools]

    if not payload and not _authoring_kwargs:
        raise ToolError("No article changes were provided")

    if _authoring_kwargs:
        # Retrieve the current article to obtain existing authoring_data.
        try:
            current = await qapp_client.get_article(
                access_token=access_token,
                article_id=article_id,
            )
        except QAppClientError as error:
            raise ToolError(str(error)) from error

        existing_authoring = current.get("data", {}).get("authoring_data")
        if not isinstance(existing_authoring, dict):
            raise ToolError(
                "Cannot update authoring metadata: the current article does not "
                "have accessible authoring_data. Ensure the draft is owned by "
                "the authenticated user."
            )

        payload["authoring_data"] = merge_authoring_data_for_edit(
            existing_authoring,
            **_authoring_kwargs,
        )

    try:
        return await qapp_client.edit_article_draft(
            access_token=access_token,
            article_id=article_id,
            payload=payload,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def replace_article_body_text(
    article_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description="ID of the existing unpublished draft to edit.",
        ),
    ],
    old_text: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "The exact literal text currently present in the article body. "
                "Must occur exactly once."
            ),
        ),
    ],
    new_text: Annotated[
        str,
        Field(
            description=(
                "Replacement text. An empty string is allowed to remove the "
                "matched text."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Replace one exact piece of text in an unpublished Quollnet article draft
    without resending the full article body. Use this for small wording changes,
    URL substitutions, or replacing download placeholders. The old text must
    occur exactly once. Use edit_article_draft for substantial edits or changes
    that must also update authoring metadata."""
    access_token = await qapp_user_token()

    try:
        return await qapp_client.replace_article_body_text(
            access_token=access_token,
            article_id=article_id,
            old_text=old_text,
            new_text=new_text,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def upload_article_file(
    article_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description="ID of the article to upload the file to.",
        ),
    ],
    file_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description=(
                "Desired filename for the upload, before any qApp WebP conversion. "
                "The returned filename may differ if conversion changes the extension."
            ),
        ),
    ],
    file_base64: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "Base64-encoded raw file bytes. Do not include a data-URI prefix "
                "such as 'data:image/png;base64,' — provide the base64 content only."
            ),
        ),
    ],
    convert_to_webp: Annotated[
        bool,
        Field(
            description=(
                "When True (default) qApp converts images to WebP at quality 70. "
                "Set to False to preserve the original image format."
            ),
        ),
    ] = True,
) -> dict[str, Any]:
    """Upload a file to a Quollnet article's file folder. Images are converted to
    WebP by qApp by default; set convert_to_webp=false when the original image
    format must be preserved. The returned filename and URL are authoritative
    because image conversion may change the filename extension. Use
    list_article_files afterwards when file discovery is needed."""
    access_token = await qapp_user_token()

    try:
        file_bytes = base64.b64decode(file_base64, validate=True)
    except Exception as error:
        raise ToolError("Invalid base64 file content") from error

    if not file_bytes:
        raise ToolError("Uploaded file is empty")

    try:
        return await qapp_client.upload_article_file(
            access_token=access_token,
            article_id=article_id,
            file_name=file_name,
            file_bytes=file_bytes,
            convert_to_webp=convert_to_webp,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def list_article_files(
    article_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description="ID of the article whose files to list.",
        ),
    ],
) -> dict[str, Any]:
    """List files stored for a Quollnet article, including each file's exact stored
    filename, permanent URL, and whether it is an image. Use this before referring
    to, renaming, embedding, or linking an existing article file. For requests
    such as 'insert file X after section B', first use this tool to resolve the
    actual stored filename and URL, then use replace_article_body_text to insert
    the appropriate HTML at a unique article-body anchor."""
    access_token = await qapp_user_token()

    try:
        return await qapp_client.list_article_files(
            access_token=access_token,
            article_id=article_id,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def rename_article_file(
    article_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description="ID of the article that owns the file.",
        ),
    ],
    file_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description=(
                "Current stored filename, as returned by list_article_files."
            ),
        ),
    ],
    new_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="New filename for the file.",
        ),
    ],
) -> dict[str, Any]:
    """Rename an existing file in a Quollnet article folder, typically to improve
    clarity or SEO. Use list_article_files first to obtain the exact current
    filename. qApp automatically updates exact permanent-file URL references in
    the article body, including download links and embedded images, and updates
    the hero URL when applicable. Do not manually patch those file URLs after a
    successful rename unless the user also requested surrounding content changes."""
    access_token = await qapp_user_token()

    try:
        return await qapp_client.rename_article_file(
            access_token=access_token,
            article_id=article_id,
            file_name=file_name,
            new_name=new_name,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def set_article_hero_image(
    article_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=250,
            description="ID of the article to set the hero image for.",
        ),
    ],
    file_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description=(
                "Exact stored filename of the image to use as the hero, "
                "as returned by list_article_files."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Set the hero image for a Quollnet article. The file must already exist in
    that article's file folder — use list_article_files first when the exact stored
    filename is not already known. This only assigns the hero image; it does not
    insert the image into the article body. Do not use replace_article_body_text
    for hero image assignment."""
    access_token = await qapp_user_token()

    try:
        return await qapp_client.set_article_hero_image(
            access_token=access_token,
            article_id=article_id,
            file_name=file_name,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error