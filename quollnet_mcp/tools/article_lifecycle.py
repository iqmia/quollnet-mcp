import urllib.parse
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.qapp_auth import qapp_user_token


_ARTICLE_ID = Field(
    min_length=1,
    max_length=250,
    description="Quollnet article ID.",
)


def _encoded_article_id(article_id: str) -> str:
    return urllib.parse.quote(article_id, safe="")


async def list_article_topics() -> dict[str, Any]:
    """Return the current qApp registry of valid QArticle topics."""
    access_token = await qapp_user_token()
    try:
        return await qapp_client.get_json(
            "/articles/api/v1/article-topics",
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def validate_article_for_publish(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Validate one article against qApp's publication-readiness rules.

    qApp is authoritative. Hard errors make the article invalid; warnings are
    returned for editorial review but do not by themselves change publication
    state.
    """
    access_token = await qapp_user_token()
    try:
        return await qapp_client.get_json(
            f"/articles/api/v1/articles/{_encoded_article_id(article_id)}/validate",
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def recheck_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Run qApp's deterministic article health checks after editing."""
    access_token = await qapp_user_token()
    try:
        return await qapp_client.get_json(
            f"/articles/api/v1/articles/{_encoded_article_id(article_id)}/recheck",
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def publish_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Publish or request publication of a QArticle through qApp.

    The article must first pass qApp's authoritative publication validation.
    qApp then applies the connected user's normal role: an author may publish
    their own article, an admin may publish permitted articles, and a normal
    owner creates a publication request instead of publishing directly.
    """
    access_token = await qapp_user_token()
    try:
        validation = await qapp_client.get_json(
            f"/articles/api/v1/articles/{_encoded_article_id(article_id)}/validate",
            access_token=access_token,
        )
        validation_data = (
            validation.get("data") if isinstance(validation, dict) else None
        )
        if not isinstance(validation_data, dict) or validation_data.get("valid") is not True:
            raise ToolError(
                "Article is not ready for publication; use "
                "validate_article_for_publish to review the errors"
            )

        return await qapp_client.post_json(
            "/articles/api/v1/articles/publish",
            payload={"id": article_id},
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def unpublish_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Unpublish a QArticle through qApp's normal ownership/role rules."""
    access_token = await qapp_user_token()
    try:
        return await qapp_client.post_json(
            "/articles/api/v1/articles/unpublish",
            payload={"id": article_id},
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def archive_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Soft-delete an unpublished QArticle through qApp.

    This never hard-deletes article data. qApp rejects publication-state or
    permission combinations that are not allowed.
    """
    access_token = await qapp_user_token()
    try:
        return await qapp_client.delete_json(
            "/articles/api/v1/articles/delete",
            payload={"id": article_id},
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def restore_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Restore a soft-deleted QArticle through qApp."""
    access_token = await qapp_user_token()
    try:
        return await qapp_client.post_json(
            "/articles/api/v1/articles/restore",
            payload={"id": article_id},
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def list_articles_needing_translation() -> dict[str, Any]:
    """List missing or stale translations visible to the connected user.

    The qApp response includes both work that is eligible for automatic
    translation and work whose source family is locked from the cron translator.
    """
    access_token = await qapp_user_token()
    try:
        return await qapp_client.get_json(
            "/articles/api/v1/articles/translations/pending",
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def increment_article_version(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Increment an origin article's translation-impact version by exactly one.

    Use only after a source change is significant enough that existing
    translations should be reviewed or retranslated. Do not call this after
    every ordinary edit.
    """
    return await _post_translation_lifecycle_action(article_id, "increment-version")


async def lock_article_auto_translation(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Lock an origin article family from automatic cron translation.

    Pending translations remain visible; this only prevents automatic selection.
    """
    return await _post_translation_lifecycle_action(article_id, "lock-auto-translation")


async def unlock_article_auto_translation(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Allow automatic cron translation for an origin article family again.

    Unlocking does not mark any existing translation current.
    """
    return await _post_translation_lifecycle_action(article_id, "unlock-auto-translation")


async def mark_article_translation_current(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Mark one translation current against its source's present version.

    Call only after that translation has actually been updated or reviewed
    against the current source article.
    """
    return await _post_translation_lifecycle_action(article_id, "mark-translation-current")


async def _post_translation_lifecycle_action(
    article_id: str,
    action: str,
) -> dict[str, Any]:
    access_token = await qapp_user_token()
    try:
        return await qapp_client.post_json(
            f"/articles/api/v1/articles/{_encoded_article_id(article_id)}/{action}",
            payload={},
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


def register_article_lifecycle_tools(mcp: MCPServer) -> None:
    """Register QArticles health, reference, and lifecycle tools."""
    security = [{"type": "oauth2", "scopes": ["mcp:connect"]}]

    mcp.tool(
        name="list_article_topics",
        title="List Quollnet article topics",
        description=(
            "Return the current qApp registry of valid primary/additional article "
            "topic slugs. Use this instead of inventing topic values."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Retrieving article topics",
            "openai/toolInvocation/invoked": "Article topics retrieved",
        },
    )(list_article_topics)

    mcp.tool(
        name="validate_article_for_publish",
        title="Validate Quollnet article for publication",
        description=(
            "Run qApp's authoritative publication-readiness validation for one "
            "article. Use this before publication to inspect hard errors and "
            "editorial warnings."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Validating article",
            "openai/toolInvocation/invoked": "Article validation complete",
        },
    )(validate_article_for_publish)

    mcp.tool(
        name="recheck_article",
        title="Recheck Quollnet article",
        description=(
            "Run qApp's deterministic article health checks after editing and "
            "return structured errors, warnings, and check results."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Rechecking article",
            "openai/toolInvocation/invoked": "Article recheck complete",
        },
    )(recheck_article)

    mcp.tool(
        name="publish_article",
        title="Publish or request publication of Quollnet article",
        description=(
            "Validate an article and then ask qApp to publish it. qApp applies "
            "the connected user's normal role: normal owners request publication, "
            "authors may directly publish their own articles, and admins may "
            "publish according to qApp permissions."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Publishing article",
            "openai/toolInvocation/invoked": "Article publication action complete",
        },
    )(publish_article)

    mcp.tool(
        name="unpublish_article",
        title="Unpublish Quollnet article",
        description=(
            "Remove an article from public publication through qApp. qApp permits "
            "the article owner or an authorized admin according to its normal rules."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Unpublishing article",
            "openai/toolInvocation/invoked": "Article unpublished",
        },
    )(unpublish_article)

    mcp.tool(
        name="archive_article",
        title="Archive Quollnet article",
        description=(
            "Soft-delete an unpublished article through qApp. This is reversible "
            "with restore_article and never performs a hard delete."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Archiving article",
            "openai/toolInvocation/invoked": "Article archived",
        },
    )(archive_article)

    mcp.tool(
        name="restore_article",
        title="Restore Quollnet article",
        description="Restore a previously soft-deleted article through qApp.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Restoring article",
            "openai/toolInvocation/invoked": "Article restored",
        },
    )(restore_article)

    mcp.tool(
        name="list_articles_needing_translation",
        title="List articles needing translation",
        description=(
            "List missing or stale QArticle translations visible to the connected "
            "user. Includes both auto-eligible work and pending work whose source "
            "family is locked from automatic translation."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Checking pending translations",
            "openai/toolInvocation/invoked": "Pending translations retrieved",
        },
    )(list_articles_needing_translation)

    mcp.tool(
        name="increment_article_version",
        title="Increment article translation version",
        description=(
            "Increment an origin article's translation-impact version by exactly one. "
            "Use only after a significant source change that requires existing "
            "translations to be reviewed or retranslated; never call after every edit."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Incrementing article version",
            "openai/toolInvocation/invoked": "Article version incremented",
        },
    )(increment_article_version)

    mcp.tool(
        name="lock_article_auto_translation",
        title="Lock article automatic translation",
        description=(
            "Reserve the whole origin article family from automatic cron translation. "
            "Pending translation work remains visible and may still be handled manually."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Locking automatic translation",
            "openai/toolInvocation/invoked": "Automatic translation locked",
        },
    )(lock_article_auto_translation)

    mcp.tool(
        name="unlock_article_auto_translation",
        title="Unlock article automatic translation",
        description=(
            "Allow the cron translator to process pending work for the source family "
            "again. Unlocking does not mark any translation current."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Unlocking automatic translation",
            "openai/toolInvocation/invoked": "Automatic translation unlocked",
        },
    )(unlock_article_auto_translation)

    mcp.tool(
        name="mark_article_translation_current",
        title="Mark article translation current",
        description=(
            "Mark one translation current against the source's present version. "
            "Use only after that translation has actually been reviewed or updated "
            "against the current source article."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Marking translation current",
            "openai/toolInvocation/invoked": "Translation marked current",
        },
    )(mark_article_translation_current)
