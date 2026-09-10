from bilingual_etl.enrichment.language_detector import detect_language, detect_record_language


class TestDetectLanguage:
    def test_hungarian(self):
        assert detect_language("Targoncák és emelőgépek forgalmazása") == "hu"

    def test_english(self):
        assert detect_language("Industrial forklift sales and distribution") == "en"

    def test_empty_defaults_to_hu(self):
        assert detect_language("") == "hu"

    def test_none_defaults_to_hu(self):
        assert detect_language(None) == "hu"


class TestDetectRecordLanguage:
    def test_hungarian_category(self):
        record = {
            "category_id": "123",
            "category_name": "Targonca",
            "description": "Elektromos és dízel targoncák értékesítése és szervize.",
        }
        assert detect_record_language(record) == "hu"

    def test_english_company(self):
        record = {
            "company_id": "456",
            "company_name": "Global Forklift Solutions",
            "description": "We provide industrial forklift sales and distribution worldwide.",
        }
        assert detect_record_language(record) == "en"

    def test_empty_record_defaults_hu(self):
        record = {"company_id": "789"}
        assert detect_record_language(record) == "hu"
