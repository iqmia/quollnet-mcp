from __future__ import annotations

import copy
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


_UNSET = object()


def merge_authoring_data_for_edit(
    existing: dict[str, Any],
    *,
    answer_summary: Any = _UNSET,
    primary_keyword: Any = _UNSET,
    search_intent: Any = _UNSET,
    target_audience: Any = _UNSET,
    key_questions: Any = _UNSET,
    hero_image_prompt: Any = _UNSET,
    hero_image_alt_text: Any = _UNSET,
    og_image_prompt: Any = _UNSET,
    og_image_alt_text: Any = _UNSET,
    infographic_needed: Any = _UNSET,
    infographic_prompt: Any = _UNSET,
    infographic_alt_text: Any = _UNSET,
    references: Any = _UNSET,
    internal_links: Any = _UNSET,
    tools: Any = _UNSET,
) -> dict[str, Any]:
    """
    Deep-copy existing authoring_data and apply only the explicitly supplied
    public authoring changes. Returns the merged complete authoring_data.

    Fields that are left as _UNSET are not touched.
    """
    merged: dict[str, Any] = copy.deepcopy(existing)

    if answer_summary is not _UNSET:
        merged["answer_summary"] = answer_summary

    search = merged.setdefault("search", {})
    if primary_keyword is not _UNSET:
        search["primary_keyword"] = primary_keyword
    if search_intent is not _UNSET:
        search["search_intent"] = search_intent
    if target_audience is not _UNSET:
        search["target_audience"] = target_audience
        # Keep social.brief.target_audience aligned (mirrors create_article_draft)
        merged.setdefault("social", {}).setdefault("brief", {})["target_audience"] = target_audience
    if key_questions is not _UNSET:
        search["key_questions"] = key_questions

    images = merged.setdefault("images", {})
    hero = images.setdefault("hero", {})
    if hero_image_prompt is not _UNSET:
        hero["prompt"] = hero_image_prompt
    if hero_image_alt_text is not _UNSET:
        hero["alt_text"] = hero_image_alt_text

    og = images.setdefault("og", {})
    if og_image_prompt is not _UNSET:
        og["prompt"] = og_image_prompt
    if og_image_alt_text is not _UNSET:
        og["alt_text"] = og_image_alt_text

    infographic = images.setdefault("infographic", {})
    if infographic_needed is not _UNSET:
        infographic["needed"] = infographic_needed
    if infographic_prompt is not _UNSET:
        infographic["prompt"] = infographic_prompt
    if infographic_alt_text is not _UNSET:
        infographic["alt_text"] = infographic_alt_text

    if references is not _UNSET:
        merged["references"] = references
    if internal_links is not _UNSET:
        merged["internal_links"] = internal_links
    if tools is not _UNSET:
        merged["tools"] = tools

    return merged