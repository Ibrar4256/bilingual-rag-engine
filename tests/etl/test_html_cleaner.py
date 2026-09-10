"""Tests for HTML cleaner (R2)."""

from bilingual_etl.transform.html_cleaner import strip_html


class TestStripHtml:
    def test_removes_paragraph_tags(self):
        assert strip_html("<p>Hello world</p>") == "Hello world"

    def test_removes_strong_and_em_tags(self):
        result = strip_html("Text with <strong>bold</strong> and <em>italic</em>.")
        assert result == "Text with bold and italic."

    def test_br_becomes_space_not_glued(self):
        result = strip_html("Line one<br>Line two")
        assert result == "Line one Line two"

    def test_nested_tags(self):
        result = strip_html("<p>Text with <strong>bold <em>nested</em></strong>.</p>")
        assert result == "Text with bold nested."

    def test_multiple_paragraphs_preserve_spacing(self):
        result = strip_html("<p>First paragraph.</p><p>Second paragraph.</p>")
        assert result == "First paragraph. Second paragraph."

    def test_collapses_extra_whitespace(self):
        result = strip_html("<p>Too    much   space</p>")
        assert result == "Too much space"

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_none_input(self):
        assert strip_html(None) == ""

    def test_no_html_passthrough(self):
        assert strip_html("Plain text, no tags.") == "Plain text, no tags."

    def test_real_dataset_pattern(self):
        sample = (
            "<p>Altalanos velemeny szerint a <strong>kulso arnyekolok</strong> "
            "sokkal hatasosabbak<br>a belso arnyekoloknal.</p>"
        )
        result = strip_html(sample)
        assert "<" not in result
        assert ">" not in result
        assert "arnyekolok sokkal hatasosabbak a belso" in result

    def test_hr_and_div(self):
        result = strip_html("<div>Section A</div><hr><div>Section B</div>")
        assert result == "Section A Section B"
