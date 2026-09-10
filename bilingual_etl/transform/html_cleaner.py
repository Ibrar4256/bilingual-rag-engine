"""
HTML Cleaner (R2)

Category descriptions in the source data are HTML-formatted (<p>, <strong>,
<br>, <em>, etc). This module strips tags and produces plain text, preserving
paragraph/line breaks as spaces so words don't get glued together.

Must run before lemmatization and embedding — raw HTML tags would otherwise
pollute both the BM25 tokens and the embedding vectors.

Usage:
    clean_text = strip_html("<p>Altalanos <strong>velemeny</strong> szerint...</p>")
"""

from bs4 import BeautifulSoup

BLOCK_TAGS = {"p", "br", "div", "hr", "li"}


def strip_html(text: str) -> str:
    if not text:
        return ""

    soup = BeautifulSoup(text, "html.parser")

    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before(" ")
        tag.insert_after(" ")

    plain = soup.get_text()
    return " ".join(plain.split())
