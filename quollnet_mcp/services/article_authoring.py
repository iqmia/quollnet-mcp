from __future__ import annotations

from typing import Any



def build_authoring_data(
    *,
    slug: str,
    answer_summary: str,
    primary_keyword: str,
    search_intent: str,
    target_audience: str,
    key_questions: list[str] | None = None,
    hero_image_prompt: str = "",
    hero_image_alt_text: str = "",
    og_image_prompt: str = "",
    og_image_alt_text: str = "",
    infographic_needed: bool = False,
    infographic_prompt: str = "",
    infographic_alt_text: str = "",
    references: list[dict[str, Any]] | None = None,
    internal_links: list[dict[str, Any]] | None = None,
    downloads: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    social_primary_angle: str | None = None,
    social_key_points: list[str] | None = None,
    social_hook: str | None = None,
    social_cta: str | None = None,
    social_avoid: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build qApp article_draft_create.v1 authoring_data.

    This keeps qApp's internal authoring contract out of the public MCP
    tool interface. qApp remains responsible for authoritative validation.
    """
    questions = list(key_questions or [])

    if social_key_points is None:
        social_points = list(questions)
    else:
        social_points = list(social_key_points)

    if not social_points:
        social_points = [answer_summary]

    avoid_items = list(social_avoid or [])

    infographic_filename = (
        f"{slug}-infographic.webp"
        if infographic_needed
        else ""
    )

    return {
        "schema_version": 1,
        "answer_summary": answer_summary,
        "search": {
            "primary_keyword": primary_keyword,
            "search_intent": search_intent,
            "target_audience": target_audience,
            "key_questions": questions,
        },
        "images": {
            "hero": {
                "prompt": hero_image_prompt,
                "alt_text": hero_image_alt_text,
                "suggested_filename": f"{slug}-hero.webp",
            },
            "og": {
                "prompt": og_image_prompt,
                "alt_text": og_image_alt_text,
                "suggested_filename": f"{slug}-open-graph.webp",
            },
            "infographic": {
                "needed": infographic_needed,
                "prompt": infographic_prompt,
                "alt_text": infographic_alt_text,
                "suggested_filename": infographic_filename,
            },
        },
        "references": list(references or []),
        "internal_links": list(internal_links or []),
        "downloads": list(downloads or []),
        "tools": list(tools or []),
        "social": {
            "brief": {
                "primary_angle": social_primary_angle or answer_summary,
                "target_audience": target_audience,
                "key_points": social_points,
                "strongest_hook": social_hook or answer_summary,
                "cta": (
                    social_cta
                    or "Read the full practical guidance on Quollnet."
                ),
                "avoid": avoid_items,
            },
        },
    }