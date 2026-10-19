"""Citizen register: import, suggestion-only matching and cross-case alerts."""
from backend.modules.citizen_import import SEED_PATH, read_rows
from backend.modules.citizen_match import ALERT_THRESHOLD, candidates_for
from backend.routes.citizens import _alert_from


def citizen(i, name, phone=""):
    return {"id": i, "full_name": name, "norm_name": name.lower(), "phone": phone,
            "phone_digits": "".join(ch for ch in phone if ch.isdigit())[-15:]}


REGISTER = [
    citizen(1, "Jonathan Vance", "+1 555 0101"),
    citizen(2, "Arthur Dent"),
    citizen(3, "Arthur Dent"),
    citizen(4, "Maria Lopez", "+1 555 0199"),
]


def test_seed_workbook_parses():
    rows = read_rows(SEED_PATH)
    assert len(rows) >= 50
    assert all(r["full_name"] and r["norm_name"] for r in rows)
    assert all(r["criminal_record"] for r in rows)          # defaults to "None"


def test_initial_and_surname_matches_one_person():
    got = candidates_for({"name": "J. Vance", "aliases": [], "identifiers": []}, REGISTER)
    assert [g["citizen_id"] if "citizen_id" in g else g["id"] for g in got][:1] == [1]
    assert got[0]["score"] >= ALERT_THRESHOLD


def test_surname_alone_is_not_a_match():
    assert candidates_for({"name": "Vance", "aliases": [], "identifiers": []}, REGISTER) == []


def test_identical_names_stay_ambiguous_and_below_alert_threshold():
    got = candidates_for({"name": "Arthur Dent", "aliases": [], "identifiers": []}, REGISTER)
    assert len(got) == 2
    assert all(g["score"] < ALERT_THRESHOLD for g in got)
    assert any("equally" in " ".join(g["reasons"]) for g in got)


def test_phone_number_lifts_the_right_person():
    person = {"name": "Maria Lopez", "aliases": [],
              "identifiers": [{"kind": "PHONE", "value": "555-0199"}]}
    got = candidates_for(person, REGISTER)
    assert got and got[0]["score"] >= ALERT_THRESHOLD


def test_rejected_citizen_is_excluded():
    got = candidates_for({"name": "J. Vance", "aliases": [], "identifiers": []}, REGISTER, rejected=[1])
    assert got == []


def link(case, status="SUGGESTED", role=None, counts=True):
    return {"case_id": case, "case_number": f"FS-{case}", "status": status, "role": role, "counts_for_alert": counts}


def test_single_case_raises_no_alert():
    assert _alert_from(REGISTER[0], [link("a", "CONFIRMED")]) is None


def test_weak_suggestions_do_not_count():
    assert _alert_from(REGISTER[0], [link("a"), link("b", counts=False)]) is None


def test_two_cases_alert_and_priority():
    medium = _alert_from(REGISTER[0], [link("a"), link("b")])
    assert medium and medium["priority"] == "MEDIUM" and medium["case_count"] == 2
    high = _alert_from(REGISTER[0], [link("a", "CONFIRMED", "SUSPECT"), link("b", "CONFIRMED", "SUSPECT")])
    assert high["priority"] == "HIGH"
