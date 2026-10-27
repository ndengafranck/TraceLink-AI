import secrets
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Case, Device, Observation

DOUALA = (4.0511, 9.7679)


def _iso(minutes_ago=5):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def _body(minutes_ago=5, lat=DOUALA[0], lon=DOUALA[1], accuracy=30, nonce=None, **extra):
    body = {
        "source": "simulated",
        "observed_at": _iso(minutes_ago),
        "lat": lat,
        "lon": lon,
        "accuracy_m": accuracy,
        "nonce": nonce or f"n-{secrets.token_hex(6)}",
    }
    body.update(extra)
    return body


@pytest.fixture()
def case(client, auth_header, verified_device):
    h = auth_header()
    device_id = verified_device(h)
    case_id = client.post(f"/devices/{device_id}/cases", headers=h).json()["id"]
    return {"headers": h, "id": case_id, "device_id": device_id}


def _post(client, case, body):
    return client.post(f"/cases/{case['id']}/observations", json=body, headers=case["headers"])


def _state(client, case):
    return client.get(f"/cases/{case['id']}", headers=case["headers"]).json()["state"]


# --- storing sightings ---------------------------------------------------------

def test_good_sighting_is_accepted_and_moves_case_forward(client, case):
    assert _state(client, case) == "open"
    r = _post(client, case, _body())
    assert r.status_code == 201
    body = r.json()
    assert body["validation_status"] == "accepted" and body["flags"] == []
    assert body["source"] == "simulated"
    assert body["age_seconds"] >= 290
    assert _state(client, case) == "evidence_received"


def test_stale_sighting_is_stored_with_a_flag(client, case):
    r = _post(client, case, _body(minutes_ago=30 * 60))
    assert r.status_code == 201
    assert r.json()["validation_status"] == "flagged" and r.json()["flags"] == ["stale"]


def test_future_sighting_is_rejected_and_not_stored(client, case, db_session):
    r = _post(client, case, _body(minutes_ago=-30))
    assert r.status_code == 422
    assert r.json()["detail"]["reason"] == "future_timestamp"
    assert db_session.scalar(select(Observation)) is None
    assert _state(client, case) == "open"


def test_duplicate_sighting_is_rejected(client, case):
    assert _post(client, case, _body(minutes_ago=5)).status_code == 201
    r = _post(client, case, _body(minutes_ago=4))  # same place, one minute later
    assert r.status_code == 422 and r.json()["detail"]["reason"] == "duplicate"


def test_replayed_report_is_rejected(client, case, db_session):
    first = _body(nonce="same-report-id-1")
    assert _post(client, case, first).status_code == 201
    replay = dict(first)  # byte-for-byte resend
    assert _post(client, case, replay).status_code == 409
    other = _body(minutes_ago=60, lat=DOUALA[0] + 0.01, nonce="same-report-id-1")
    assert _post(client, case, other).status_code == 409  # same id, different content
    assert len(list(db_session.scalars(select(Observation)))) == 1


def test_conflicting_sightings_are_flagged(client, case):
    _post(client, case, _body(minutes_ago=6))
    r = _post(client, case, _body(minutes_ago=4, lat=3.8480, lon=11.5021))
    assert r.status_code == 201
    assert r.json()["validation_status"] == "flagged"
    assert "implausible_movement" in r.json()["flags"]


# --- input checks ----------------------------------------------------------------

@pytest.mark.parametrize(
    "change",
    [
        {"source": "ble"},                       # no real source exists yet
        {"observed_at": "2026-10-27T10:00:00"},  # no time zone
        {"lat": 91},
        {"lon": -181},
        {"accuracy_m": 0},
        {"accuracy_m": -5},
        {"nonce": "short"},
        {"nonce": "has spaces in it!"},
    ],
)
def test_bad_input_is_rejected(client, case, change):
    assert _post(client, case, _body(**change)).status_code == 422


# --- case state and access ------------------------------------------------------

@pytest.mark.parametrize("final", ["recovered", "close"])
def test_finished_case_accepts_no_more_evidence(client, case, final):
    client.post(f"/cases/{case['id']}/{final}", headers=case["headers"])
    assert _post(client, case, _body()).status_code == 409


def test_requires_login(client, case):
    r = client.post(f"/cases/{case['id']}/observations", json=_body())
    assert r.status_code == 401
    assert client.get(f"/cases/{case['id']}/observations").status_code == 401


def test_other_users_cannot_read_or_add_sightings(client, case, auth_header):
    b = auth_header("b@example.com")
    _post(client, case, _body())
    assert client.get(f"/cases/{case['id']}/observations", headers=b).status_code == 404
    r = client.post(f"/cases/{case['id']}/observations", json=_body(minutes_ago=50), headers=b)
    assert r.status_code == 404


def test_without_demo_mode_no_source_exists(client, case, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert _post(client, case, _body()).status_code == 503
    r = client.post(
        f"/cases/{case['id']}/observations/simulate",
        json={"scenario": "fresh_cluster"},
        headers=case["headers"],
    )
    assert r.status_code == 503


def test_per_case_limit(client, case, monkeypatch):
    monkeypatch.setattr("app.routers.observations.MAX_OBSERVATIONS_PER_CASE", 2)
    assert _post(client, case, _body(minutes_ago=50, lat=4.00)).status_code == 201
    assert _post(client, case, _body(minutes_ago=40, lat=4.0001)).status_code == 201
    assert _post(client, case, _body(minutes_ago=30, lat=4.0002)).status_code == 429


def test_list_is_newest_first(client, case):
    _post(client, case, _body(minutes_ago=50, lat=4.00))
    _post(client, case, _body(minutes_ago=10, lat=4.0003))
    times = [o["observed_at"] for o in
             client.get(f"/cases/{case['id']}/observations", headers=case["headers"]).json()]
    assert times == sorted(times, reverse=True) and len(times) == 2


# --- simulator --------------------------------------------------------------------

def _simulate(client, case, scenario):
    return client.post(
        f"/cases/{case['id']}/observations/simulate",
        json={"scenario": scenario},
        headers=case["headers"],
    )


def test_fresh_cluster_is_all_accepted(client, case):
    r = _simulate(client, case, "fresh_cluster")
    assert r.status_code == 200
    assert [x["status"] for x in r.json()["results"]] == ["accepted"] * 3
    assert _state(client, case) == "evidence_received"
    stored = client.get(f"/cases/{case['id']}/observations", headers=case["headers"]).json()
    assert len(stored) == 3 and {o["source"] for o in stored} == {"simulated"}


def test_stale_scenario_is_flagged(client, case):
    results = _simulate(client, case, "stale").json()["results"]
    assert results[0]["status"] == "flagged" and results[0]["flags"] == ["stale"]


def test_conflicting_scenario_flags_the_second_sighting(client, case):
    results = _simulate(client, case, "conflicting").json()["results"]
    assert results[0]["status"] == "accepted"
    assert results[1]["status"] == "flagged" and "implausible_movement" in results[1]["flags"]


def test_low_accuracy_scenario_is_flagged(client, case):
    results = _simulate(client, case, "low_accuracy").json()["results"]
    assert results[0]["flags"] == ["low_accuracy"]


def test_unknown_scenario_is_rejected(client, case):
    assert _simulate(client, case, "teleport").status_code == 422


def test_simulate_checks_ownership(client, case, auth_header):
    b = auth_header("b@example.com")
    r = client.post(
        f"/cases/{case['id']}/observations/simulate",
        json={"scenario": "fresh_cluster"},
        headers=b,
    )
    assert r.status_code == 404


# --- cleanup -------------------------------------------------------------------------

def test_deleting_a_device_removes_its_cases_and_sightings(client, case, db_session):
    _simulate(client, case, "fresh_cluster")
    assert client.delete(f"/devices/{case['device_id']}", headers=case["headers"]).status_code == 204
    assert db_session.scalar(select(Observation)) is None
    assert db_session.scalar(select(Case)) is None
    assert db_session.scalar(select(Device)) is None
