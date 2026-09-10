import json
import tempfile
from pathlib import Path

import pytest

from bilingual_etl.extract.source import (
    _safe_parse_list,
    _safe_parse_number,
    extract_categories,
    extract_companies,
)


class TestSafeParseList:
    def test_native_list(self):
        assert _safe_parse_list(["a", "b"]) == ["a", "b"]

    def test_stringified_json_list(self):
        assert _safe_parse_list('["ABS", "ABS MF"]') == ["ABS", "ABS MF"]

    def test_none(self):
        assert _safe_parse_list(None) == []

    def test_empty_string(self):
        assert _safe_parse_list("") == []

    def test_empty_brackets(self):
        assert _safe_parse_list("[]") == []

    def test_plain_string(self):
        assert _safe_parse_list("single value") == ["single value"]


class TestSafeParseNumber:
    def test_string_integer(self):
        assert _safe_parse_number("42") == 42

    def test_string_float(self):
        assert _safe_parse_number("3.14") == 3.14

    def test_none(self):
        assert _safe_parse_number(None) is None

    def test_empty_string(self):
        assert _safe_parse_number("") is None

    def test_dash(self):
        assert _safe_parse_number("-") is None

    def test_already_int(self):
        assert _safe_parse_number(42) == 42

    def test_comma_separated(self):
        assert _safe_parse_number("1,000,000") == 1000000


class TestExtractCategories:
    def test_real_data(self):
        categories = extract_categories()
        assert len(categories) == 3000
        first = categories[0]
        assert "category_id" in first
        assert "category_name" in first
        assert "description" in first
        assert isinstance(first["hierarchy"], list)

    def test_invalid_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"not": "a list"}, f)
            f.flush()
            with pytest.raises(ValueError, match="Expected a JSON array"):
                extract_categories(Path(f.name))


class TestExtractCompanies:
    def test_real_data(self):
        companies = extract_companies()
        assert len(companies) == 471

        for company in companies[:10]:
            assert isinstance(company.get("brands", []), list)
            assert isinstance(company.get("certificates", []), list)
            assert isinstance(company.get("services", []), list)
            nr = company.get("nr_employees")
            assert nr is None or isinstance(nr, (int, float))

    def test_empty_descriptions_counted(self):
        companies = extract_companies()
        empty = sum(1 for c in companies if not c["description"])
        assert empty > 0
