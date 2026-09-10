"""Tests for hash-based change detection (R10)."""

from bilingual_etl.transform.hash_gate import compute_content_hash, has_changed


class TestComputeContentHash:
    def test_same_record_same_hash(self):
        record = {"company_id": "1", "name": "Test Kft.", "nr_employees": 10}
        assert compute_content_hash(record) == compute_content_hash(record)

    def test_key_order_does_not_affect_hash(self):
        record_a = {"a": 1, "b": 2}
        record_b = {"b": 2, "a": 1}
        assert compute_content_hash(record_a) == compute_content_hash(record_b)

    def test_different_values_produce_different_hash(self):
        record_a = {"nr_employees": 10}
        record_b = {"nr_employees": 11}
        assert compute_content_hash(record_a) != compute_content_hash(record_b)

    def test_nested_structures(self):
        record = {"brands": ["ABS", "Piranha"], "meta": {"x": 1}}
        h1 = compute_content_hash(record)
        h2 = compute_content_hash(record)
        assert h1 == h2

    def test_returns_md5_hex_digest(self):
        result = compute_content_hash({"a": 1})
        assert len(result) == 32
        int(result, 16)  # raises ValueError if not valid hex

    def test_empty_dict(self):
        assert compute_content_hash({}) == compute_content_hash({})


class TestHasChanged:
    def test_no_previous_hash_means_changed(self):
        assert has_changed("abc123", None) is True

    def test_same_hash_means_unchanged(self):
        assert has_changed("abc123", "abc123") is False

    def test_different_hash_means_changed(self):
        assert has_changed("abc123", "def456") is True

    def test_end_to_end_unchanged_record(self):
        record = {"company_id": "1", "nr_employees": 10}
        first_hash = compute_content_hash(record)
        # Simulate a rerun with identical source data
        second_hash = compute_content_hash(dict(record))
        assert has_changed(second_hash, first_hash) is False

    def test_end_to_end_changed_record(self):
        record = {"company_id": "1", "nr_employees": 10}
        first_hash = compute_content_hash(record)
        edited = dict(record)
        edited["nr_employees"] = 11
        second_hash = compute_content_hash(edited)
        assert has_changed(second_hash, first_hash) is True
