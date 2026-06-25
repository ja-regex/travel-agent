import unittest

from backend.agent import normalize_research_plan


class GuardrailNormalizationTests(unittest.TestCase):
    def test_comparison_place_does_not_add_its_languages(self) -> None:
        plan = normalize_research_plan(
            {
                "accepted": True,
                "destinationsMentioned": ["Vietnam", "Hanoi"],
                "comparisonPlaces": ["Valle Sagrada", "Peru"],
                "localLanguages": ["Vietnamese", "Spanish", "Quechua"],
                "localLanguageWouldHelp": True,
                "searchQueries": ["quiet small towns near Hanoi"],
            },
            "Vietnam trip inspired by Valle Sagrada in Peru",
        )

        self.assertEqual(plan.local_languages, ["Vietnamese"])
        self.assertEqual(plan.comparison_places, ["Valle Sagrada", "Peru"])

    def test_explicit_source_language_is_kept(self) -> None:
        plan = normalize_research_plan(
            {
                "accepted": True,
                "destinationsMentioned": ["Vietnam"],
                "preferredSourceLanguages": ["Japanese"],
                "localLanguages": ["Vietnamese", "Japanese"],
                "localLanguageWouldHelp": True,
            },
            "Vietnam recommendations from Japanese tourbooks",
        )

        self.assertEqual(plan.local_languages, ["Vietnamese", "Japanese"])


if __name__ == "__main__":
    unittest.main()
