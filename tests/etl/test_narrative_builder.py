"""Tests for narrative building (R6)."""

from bilingual_etl.transform.narrative_builder import (
    build_category_narrative,
    build_company_narrative,
)


class TestBuildCompanyNarrative:
    def test_basic_fields_rendered_as_sentences(self):
        company = {
            "company_name": "Zultzer Pumpen Kft.",
            "year_founded": 1996,
            "nr_employees": 13,
            "legal_form": "Korlátolt felelősségű társaság",
            "company_status": "Működő",
        }
        result = build_company_narrative(company, "hu")

        assert "Zultzer Pumpen Kft." in result
        assert "1996" in result
        assert "13" in result
        # Rendered as prose, not a "key: value" dump
        assert "founded" not in result.lower()
        assert ":" not in result.split(".")[0]

    def test_hu_article_before_consonant(self):
        company = {"company_name": "Zultzer Pumpen Kft."}
        result = build_company_narrative(company, "hu")
        assert result.startswith("A Zultzer")

    def test_hu_article_before_vowel(self):
        company = {"company_name": "ABS Kft."}
        result = build_company_narrative(company, "hu")
        assert result.startswith("Az ABS")

    def test_category_list_ordered_near_end(self):
        company = {
            "company_name": "Test Kft.",
            "description": "A description sentence.",
            "brands": ["BrandA"],
        }
        result = build_company_narrative(company, "en", category_names=["Cat1", "Cat2"])

        category_pos = result.index("Cat1")
        description_pos = result.index("A description sentence")
        assert category_pos > description_pos

    def test_brands_and_certificates_are_language_invariant(self):
        company = {
            "company_name": "Test Kft.",
            "brands": ["Piranha", "ABS"],
            "certificates": ["ISO 9001"],
        }
        result_hu = build_company_narrative(company, "hu")
        result_en = build_company_narrative(company, "en")

        for term in ("Piranha", "ABS", "ISO 9001"):
            assert term in result_hu
            assert term in result_en

    def test_legal_form_translated_for_english(self):
        company = {
            "company_name": "Test Kft.",
            "legal_form": "Korlátolt felelősségű társaság",
        }
        result = build_company_narrative(company, "en")
        assert "Limited Liability Company" in result
        assert "Korlátolt felelősségű társaság" not in result

    def test_services_translated_per_language(self):
        company = {"company_name": "Test Kft.", "services": ["manufacturing", "wholesale"]}
        result_hu = build_company_narrative(company, "hu")
        result_en = build_company_narrative(company, "en")

        assert "gyártás" in result_hu
        assert "manufacturing" in result_en

    def test_unmapped_enum_value_falls_back_to_original(self):
        company = {"company_name": "Test Kft.", "legal_form": "Some Unknown Form"}
        result = build_company_narrative(company, "en")
        assert "Some Unknown Form" in result

    def test_missing_optional_fields_do_not_crash(self):
        company = {"company_name": "Minimal Kft."}
        result = build_company_narrative(company, "hu")
        assert "Minimal Kft." in result

    def test_empty_company_dict(self):
        result = build_company_narrative({}, "en")
        assert isinstance(result, str)


class TestBuildCategoryNarrative:
    def test_hierarchy_and_description(self):
        category = {
            "category_name": "Vakolható tokos alumínium redőny",
            "hierarchy": ["Alumínium redőny", "Redőny"],
            "description": "Praktikus megoldás.",
        }
        result = build_category_narrative(category, "hu")

        assert "Vakolható tokos alumínium redőny" in result
        assert "Alumínium redőny > Redőny" in result
        assert "Praktikus megoldás." in result

    def test_hu_article_before_vowel_category_name(self):
        category = {"category_name": "Alumínium redőny szerelés", "hierarchy": ["X"]}
        result = build_category_narrative(category, "hu")
        assert result.startswith("Az Alumínium")

    def test_falls_back_to_short_description(self):
        category = {
            "category_name": "Test Category",
            "short_description": "Short desc text.",
        }
        result = build_category_narrative(category, "hu")
        assert "Short desc text." in result

    def test_synonyms_as_string_are_split(self):
        category = {
            "category_name": "Test",
            "synonyms": "term1, term2, term3",
        }
        result = build_category_narrative(category, "en")
        assert "term1" in result
        assert "term2" in result
        assert "term3" in result

    def test_empty_category(self):
        result = build_category_narrative({}, "hu")
        assert isinstance(result, str)
