"""Plate correction and voting (pure logic)."""
import pytest

from backend.modules.plate_postprocess import cluster_reads, parse_plate, vote


@pytest.mark.parametrize("raw,expected", [
    ("TN O9 A8 1234", "TN09AB1234"),     # O->0 in digit slot, 8->B in letter slot
    ("TN09AB1234", "TN09AB1234"),         # already valid -> untouched
    ("MH 12 D6 1433", "MH12DG1433"),      # 6->G in series
    ("KA 5I AB 4821", "KA51AB4821"),      # I->1
])
def test_indian_format_correction(raw, expected):
    p = parse_plate(raw)
    assert p.text == expected and p.pattern == "IN"


def test_state_code_validity_flag():
    assert parse_plate("TN09AB1234").state_valid is True
    assert parse_plate("ZZ09AB1234").state_valid is False


def test_uk_format_correction():
    p = parse_plate("AB1Z CDE")
    assert p.pattern == "UK" and p.text == "AB12CDE"


def test_non_plate_text_is_left_alone():
    p = parse_plate("HELLO")
    assert p.pattern == "RAW" and p.text == "HELLO" and p.edits == 0


def test_voting_removes_random_single_frame_errors():
    reads = [("TN09AB1234", 0.8), ("TN09A81234", 0.5), ("TN09AB1284", 0.4),
             ("TN09AB1234", 0.7), ("TNO9AB1234", 0.6)]
    v = vote(reads)
    assert v.text == "TN09AB1234" and v.n_reads == 5 and v.agreement > 0.9
    assert v.confidence > 0.5


def test_single_read_is_discounted_vs_many_reads():
    one = vote([("TN09AB1234", 0.9)])
    many = vote([("TN09AB1234", 0.9)] * 4)
    assert one.confidence < many.confidence


def test_voting_returns_none_for_junk():
    assert vote([("A", 0.9), ("12", 0.4)]) is None


def test_cluster_reads_separates_different_plates():
    cl = cluster_reads([("TN09AB1234", .8), ("TN09AB1284", .5), ("KA01XY9999", .9)])
    assert len(cl) == 2 and sorted(len(c) for c in cl) == [1, 2]


def test_invalid_state_code_is_repaired_when_unambiguous():
    p = parse_plate("OJ65T5253")          # G misread as O; only GJ is a real code
    assert p.text == "GJ65T5253" and p.state_valid is True and p.edits == 1


def test_ambiguous_invalid_state_code_is_left_alone():
    p = parse_plate("ZZ65T5253")
    assert p.text == "ZZ65T5253" and p.state_valid is False
