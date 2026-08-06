import unittest

from quollnet_mcp.services.article_authoring import build_authoring_data


class ArticleAuthoringBuilderTests(unittest.TestCase):
    def test_builds_complete_qapp_authoring_contract(self) -> None:
        result = build_authoring_data(
            slug="concrete-quality-control",
            answer_summary=(
                "Concrete quality control combines material verification, "
                "production monitoring, testing, inspection, and traceable records."
            ),
            primary_keyword="concrete quality control",
            search_intent=(
                "Explain how site engineers control and document concrete quality."
            ),
            target_audience="Site engineers and QA/QC engineers",
            key_questions=[
                "What should be checked before concrete placement?",
                "Which tests and records are required?",
            ],
        )

        self.assertEqual(result["schema_version"], 1)

        self.assertEqual(
            result["search"],
            {
                "primary_keyword": "concrete quality control",
                "search_intent": (
                    "Explain how site engineers control and document "
                    "concrete quality."
                ),
                "target_audience": "Site engineers and QA/QC engineers",
                "key_questions": [
                    "What should be checked before concrete placement?",
                    "Which tests and records are required?",
                ],
            },
        )

        self.assertEqual(
            result["images"]["hero"]["suggested_filename"],
            "concrete-quality-control-hero.webp",
        )
        self.assertEqual(
            result["images"]["og"]["suggested_filename"],
            "concrete-quality-control-open-graph.webp",
        )
        self.assertEqual(
            result["images"]["infographic"],
            {
                "needed": False,
                "prompt": "",
                "alt_text": "",
                "suggested_filename": "",
            },
        )

        self.assertEqual(result["references"], [])
        self.assertEqual(result["internal_links"], [])
        self.assertEqual(result["downloads"], [])
        self.assertEqual(result["tools"], [])

        social = result["social"]["brief"]

        self.assertEqual(
            social["target_audience"],
            "Site engineers and QA/QC engineers",
        )
        self.assertEqual(
            social["key_points"],
            [
                "What should be checked before concrete placement?",
                "Which tests and records are required?",
            ],
        )
        self.assertTrue(social["primary_angle"])
        self.assertTrue(social["strongest_hook"])
        self.assertTrue(social["cta"])
        self.assertEqual(social["avoid"], [])

def test_preserves_explicit_social_avoid(self) -> None:
    result = build_authoring_data(
        slug="test-article",
        answer_summary="Answer",
        primary_keyword="test",
        search_intent="informational",
        target_audience="Engineers",
        social_avoid=["Avoid unsupported claims"],
    )

    self.assertEqual(
        result["social"]["brief"]["avoid"],
        ["Avoid unsupported claims"],
    )

if __name__ == "__main__":
    unittest.main()