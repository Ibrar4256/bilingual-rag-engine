"""
Narrative Builder (R6)

Assembles natural-language prose narratives from structured category/company
fields, per language. This is deliberately NOT a keyword or JSON dump — R6
requires natural sentences, with category/activity lists placed near the end
rather than dumped at the top.

This module makes no LLM calls. Three kinds of fields are handled differently
depending on how "translatable" they are:
  - Free/open-vocabulary fields (`description`, `activities`) must already be
    in the target language when passed in — the caller resolves that via
    bilingual_etl/enrichment/translator.py (or a cached lookup) beforehand.
    Same for `category_names`, passed as a separate parameter since it comes
    from a join against the categories dataset, not a flat company field.
  - Small closed-vocabulary fields (`legal_form`, `company_status`,
    `services` — a handful of fixed values across the whole dataset) are
    translated here via static lookup tables — the "simplest robust
    solution" for a closed set, no LLM call needed per record.
  - Proper-noun-like fields (`brands`, `certificates`) are language-invariant
    and included as-is regardless of language.

Usage:
    narrative = build_company_narrative(company, language="en", category_names=[...])
    narrative = build_category_narrative(category, language="hu")
"""

from loguru import logger

LEGAL_FORM_LABELS = {
    "hu": {
        "Korlátolt felelősségű társaság": "korlátolt felelősségű társaság (Kft.)",
        "Betéti társaság": "betéti társaság (Bt.)",
        "Közkereseti társaság": "közkereseti társaság (Kkt.)",
        "Egyéni vállalkozó": "egyéni vállalkozó",
        "Részvénytársaság": "részvénytársaság (Rt.)",
        "Külföldiek magyarországi közvetlen kereskedelmi képviselete": (
            "külföldi vállalkozás magyarországi közvetlen kereskedelmi képviselete"
        ),
        "Külföldi vállalkozás magyarországi fióktelepe": "külföldi vállalkozás magyarországi fióktelepe",
    },
    "en": {
        "Korlátolt felelősségű társaság": "Limited Liability Company (Kft.)",
        "Betéti társaság": "Limited Partnership (Bt.)",
        "Közkereseti társaság": "General Partnership (Kkt.)",
        "Egyéni vállalkozó": "Sole Proprietorship",
        "Részvénytársaság": "Joint-Stock Company (Rt.)",
        "Külföldiek magyarországi közvetlen kereskedelmi képviselete": (
            "Direct Commercial Representation of a Foreign Company in Hungary"
        ),
        "Külföldi vállalkozás magyarországi fióktelepe": "Hungarian Branch Office of a Foreign Company",
    },
}

COMPANY_STATUS_LABELS = {
    "hu": {
        "Működő": "működő",
        "Bírósági eljárás alatt": "bírósági eljárás alatt álló",
    },
    "en": {
        "Működő": "active",
        "Bírósági eljárás alatt": "under court proceedings",
    },
}

SERVICE_LABELS = {
    "hu": {
        "engineering": "mérnöki szolgáltatás",
        "installation": "beszerelés",
        "logistics": "logisztika",
        "manufacturing": "gyártás",
        "rental": "bérlés",
        "retail": "kiskereskedelem",
        "service": "szerviz",
        "webshop": "webáruház",
        "wholesale": "nagykereskedelem",
    },
    "en": {
        "engineering": "engineering",
        "installation": "installation",
        "logistics": "logistics",
        "manufacturing": "manufacturing",
        "rental": "rental",
        "retail": "retail",
        "service": "servicing",
        "webshop": "webshop",
        "wholesale": "wholesale",
    },
}

HU_VOWELS = set("aáeéiíoóöőuúüű")


def _translate_label(value: str, mapping: dict, language: str) -> str:
    labels = mapping.get(language, {})
    if value not in labels:
        logger.warning(f"No {language} label for value {value!r}; using original text.")
        return value
    return labels[value]


def join_natural(items: list[str], language: str) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    conjunction = "és" if language == "hu" else "and"
    return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"


def _hu_article(word: str) -> str:
    """'A' before a consonant, 'Az' before a vowel — e.g. 'Az ABS Kft.', 'A Zultzer Kft.'."""
    return "Az" if word and word[0].lower() in HU_VOWELS else "A"


def build_category_narrative(category: dict, language: str) -> str:
    sentences = []

    name = category.get("category_name", "")
    hierarchy = category.get("hierarchy") or []

    if hierarchy:
        path = " > ".join(hierarchy)
        if language == "hu":
            sentences.append(f"{_hu_article(name)} {name} kategória a következő besorolási úton található: {path}.")
        else:
            sentences.append(f"The {name} category falls under: {path}.")

    description = category.get("description") or category.get("short_description") or ""
    if description:
        sentences.append(description)

    synonyms = category.get("synonyms")
    if synonyms:
        syn_list = synonyms if isinstance(synonyms, list) else [s.strip() for s in synonyms.split(",") if s.strip()]
        if syn_list:
            joined = join_natural(syn_list, language)
            if language == "hu":
                sentences.append(f"Kapcsolódó kifejezések: {joined}.")
            else:
                sentences.append(f"Related terms: {joined}.")

    supplements = category.get("supplements") or []
    if supplements:
        joined = join_natural(supplements, language)
        if language == "hu":
            sentences.append(f"Ehhez a kategóriához kapcsolódó szolgáltatások: {joined}.")
        else:
            sentences.append(f"Services associated with this category: {joined}.")

    return " ".join(sentences)


def build_company_narrative(
    company: dict,
    language: str,
    category_names: list[str] | None = None,
) -> str:
    sentences = []
    name = company.get("company_name", "")

    year_founded = company.get("year_founded")
    nr_employees = company.get("nr_employees")
    legal_form_raw = company.get("legal_form")
    legal_form = _translate_label(legal_form_raw, LEGAL_FORM_LABELS, language) if legal_form_raw else None

    if language == "hu":
        opening = _hu_article(name) + f" {name}"
        if legal_form:
            opening += f" egy {legal_form}"
        if year_founded:
            opening += f", amelyet {year_founded}-ban alapítottak"
        if nr_employees:
            opening += f", és jelenleg {nr_employees} főt foglalkoztat"
        opening += "."
    else:
        opening = f"{name} is a"
        if legal_form:
            opening += f" {legal_form}"
        else:
            opening += " company"
        if year_founded:
            opening += f" founded in {year_founded}"
        if nr_employees:
            opening += f" with {nr_employees} employees"
        opening += "."
    sentences.append(opening)

    status_raw = company.get("company_status")
    if status_raw:
        status = _translate_label(status_raw, COMPANY_STATUS_LABELS, language)
        if language == "hu":
            sentences.append(f"A cég jelenleg {status} státuszú.")
        else:
            sentences.append(f"The company currently has {status} status.")

    description = company.get("description")
    if description:
        sentences.append(description)

    activities = company.get("activities") or []
    if activities:
        joined = join_natural(activities, language)
        if language == "hu":
            sentences.append(f"Fő tevékenységi területeik: {joined}.")
        else:
            sentences.append(f"Their main areas of activity include: {joined}.")

    services_raw = company.get("services") or []
    if services_raw:
        translated_services = [_translate_label(s, SERVICE_LABELS, language) for s in services_raw]
        joined = join_natural(translated_services, language)
        if language == "hu":
            sentences.append(f"Kínált szolgáltatások: {joined}.")
        else:
            sentences.append(f"Services offered: {joined}.")

    certificates = company.get("certificates") or []
    if certificates:
        joined = join_natural(certificates, language)
        if language == "hu":
            sentences.append(f"Tanúsítványaik: {joined}.")
        else:
            sentences.append(f"They hold the following certifications: {joined}.")

    brands = company.get("brands") or []
    if brands:
        joined = join_natural(brands, language)
        if language == "hu":
            sentences.append(f"Forgalmazott márkák: {joined}.")
        else:
            sentences.append(f"Brands they distribute: {joined}.")

    counties = company.get("counties") or []
    if counties:
        if language == "hu":
            sentences.append(f"Lefedett megyék száma: {len(counties)}.")
        else:
            sentences.append(f"They cover {len(counties)} counties.")

    # Category list — deliberately placed near the end, per R6.
    if category_names:
        joined = join_natural(category_names, language)
        if language == "hu":
            sentences.append(f"A cég a következő kategóriákban aktív: {joined}.")
        else:
            sentences.append(f"The company is active in the following categories: {joined}.")

    return " ".join(sentences)
