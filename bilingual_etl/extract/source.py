"""
Source extraction — the single entry point for all raw data into the ETL pipeline.

Currently reads from data/*.json files. To swap to a live PostgreSQL source later,
only this module needs to change — nothing downstream cares where the data came from.

Handles the known data-quality issues from REQUIREMENTS.md §4:
  - List fields arrive as either native JSON arrays OR stringified-JSON strings
  - Numeric fields arrive as strings
  - description is null/empty in ~34% of company records
  - address is empty in 100% of company records
"""

import json
from pathlib import Path
from typing import Any

from loguru import logger

DATA_DIR = Path(__file__).parent.parent.parent / "data"

CATEGORIES_FILE = "categories_export_2026_04_14T11_17_15Z.json"
COMPANIES_FILE = "companies_data_for_vectors_sample_2026_03_11.json"

STRINGIFIED_LIST_FIELDS = {"brands", "certificates", "services", "counties"}

NUMERIC_FIELDS = {
    "nr_employees",
    "year_founded",
    "registered_capital",
    "profit_after_tax",
    "price_in",
}


def _safe_parse_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped == "[]":
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return [stripped]
    return [value]


def _safe_parse_number(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        stripped = value.strip().replace(",", "").replace(" ", "")
        if not stripped or stripped == "-":
            return None
        try:
            return int(stripped)
        except ValueError:
            try:
                return float(stripped)
            except ValueError:
                return None
    return None


def _normalize_company(raw: dict) -> dict:
    company = dict(raw)

    for field in STRINGIFIED_LIST_FIELDS:
        if field in company:
            company[field] = _safe_parse_list(company[field])

    for field in NUMERIC_FIELDS:
        if field in company:
            company[field] = _safe_parse_number(company[field])

    if not company.get("description"):
        company["description"] = ""

    if not company.get("address"):
        company["address"] = ""

    return company


def _normalize_category(raw: dict) -> dict:
    category = dict(raw)

    if not category.get("description"):
        category["description"] = ""

    if not category.get("short_description"):
        category["short_description"] = ""

    if category.get("hierarchy") is None:
        category["hierarchy"] = []

    for field in ("keywords", "synonyms", "supplements", "offer_request_keywords"):
        if not category.get(field):
            category[field] = ""

    return category


def extract_categories(file_path: Path | None = None) -> list[dict]:
    path = file_path or (DATA_DIR / CATEGORIES_FILE)
    logger.info(f"Extracting categories from {path.name}")

    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    if not isinstance(raw_data, list):
        raise ValueError(
            f"Expected a JSON array in {path.name}, got {type(raw_data).__name__}"
        )

    categories = [_normalize_category(item) for item in raw_data]
    logger.info(f"Extracted {len(categories)} categories")
    return categories


def extract_companies(file_path: Path | None = None) -> list[dict]:
    path = file_path or (DATA_DIR / COMPANIES_FILE)
    logger.info(f"Extracting companies from {path.name}")

    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    if not isinstance(raw_data, list):
        raise ValueError(
            f"Expected a JSON array in {path.name}, got {type(raw_data).__name__}"
        )

    companies = [_normalize_company(item) for item in raw_data]

    empty_desc = sum(1 for c in companies if not c["description"])
    if empty_desc:
        logger.warning(
            f"{empty_desc}/{len(companies)} companies have empty descriptions "
            f"({empty_desc/len(companies)*100:.0f}%) — narrative builder will use fallback fields"
        )

    logger.info(f"Extracted {len(companies)} companies")
    return companies
