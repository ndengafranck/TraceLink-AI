import base64
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.beacon import beacon_id, window_of
from app.models import BeaconKey, FinderReport, Observation
from app.ratelimit import report_limiter


@pytest.fixture(autouse=True)
def _reset():
    report_limiter.reset()


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat()


# ---------- ownership code shown on the phone ----------

def test_phone_requests_code_and_owner_verifies_with_it(client, auth_header):
    h = auth_header()
    did = client.post("/devices", json={"nickname": "p", "model": "m", "imei": "490154203237518"},
                      headers=h).json()["id"]
    r = client.post(f"/companion/devices/{did}/challenge", headers=h)
    assert r.status_code == 201 and r.json()["channel"] == "companion_app"
    code = r.json()["code"]
    v = client.post(f"/devices/{did}/ownership/verify", json={"code": code}, headers=h)
    assert v.status_code == 200 and v.json()["verified_via"] == "companion_app"


def test_other_users_device_is_404(client, auth_header):
    h = auth_header()
    did = client.post("/devices", json={"nickname": "p", "model": "m", "imei": "490154203237518"},
                      headers=h).json()["id"]
    other = auth_header("o@example.com")
    assert client.post(f"/companion/devices/{did}/challenge", headers=other).status_code == 404
    assert client.post(f"/companion/devices/{did}/enroll", headers=other).status_code == 404


def test_phone_codes_share_the_hourly_limit_and_verified_device_is_refused(client, auth_header, verified_device):
    h = auth_header()
    did = client.post("/devices", json={"nickname": "p", "model": "m", "imei": "490154203237518"},
                      headers=h).json()["id"]
    codes = [client.post(f"/companion/devices/{did}/challenge", headers=h).status_code for _ in range(4)]
    assert codes == [201, 201, 201, 429]
    h2 = auth_header("b@example.com")
    did2 = verified_device(h2, imei="356938035643809")
    assert client.post(f"/companion/devices/{did2}/challenge", headers=h2).status_code == 409


# ---------- enrolment ----------

def test_enroll_requires_verified_device(client, auth_header):
    h = auth_header()
    did = client.post("/devices", json={"nickname": "p", "model": "m", "imei": "490154203237518"},
                      headers=h).json()["id"]
    assert client.post(f"/companion/devices/{did}/enroll", headers=h).status_code == 409


def test_enroll_is_stable_and_secret_is_encrypted_at_rest(client, auth_header, verified_device, db_session):
    h = auth_header()
    did = verified_device(h)
    a = client.post(f"/companion/devices/{did}/enroll", headers=h).json()
    b = client.post(f"/companion/devices/{did}/enroll", headers=h).json()
    assert a == b and a["window_seconds"] == 900 and a["id_bytes"] == 8
    raw = base64.urlsafe_b64decode(a["beacon_secret"])
    assert len(raw) == 32
    stored = db_session.get(BeaconKey, did).secret_encrypted
    assert a["beacon_secret"] not in stored


# ---------- finder reports ----------

@pytest.fixture()
def lost(client, auth_header, verified_device):
    """A verified, enrolled phone with an open case; returns what a finder needs."""
    h = auth_header()
    did = verified_device(h)
    secret = base64.urlsafe_b64decode(client.post(f"/companion/devices/{did}/enroll", headers=h).json()["beacon_secret"])
    cid = client.post(f"/devices/{did}/cases", headers=h).json()["id"]
    return {"h": h, "did": did, "cid": cid, "secret": secret}


def report(client, headers, lost, *, at=None, bid=None, nonce="finder-nonce-0001", lat=4.0511, lon=9.7679, acc=20.0):
    at = at or now() - timedelta(minutes=2)
    return client.post("/reports", headers=headers, json={
        "beacon_id": bid or beacon_id(lost["secret"], window_of(at)),
        "observed_at": iso(at), "lat": lat, "lon": lon, "accuracy_m": acc, "nonce": nonce})


def test_matching_report_becomes_a_ble_sighting(client, lost, auth_header, db_session):
    finder = auth_header("finder@example.com")
    r = report(client, finder, lost)
    assert r.status_code == 202 and r.json() == {"status": "received"}
    obs = client.get(f"/cases/{lost['cid']}/observations", headers=lost["h"]).json()
    assert len(obs) == 1 and obs[0]["source"] == "ble"
    assert obs[0]["accuracy_m"] == 70.0  # 20 m GPS + 50 m Bluetooth range
    assert client.get(f"/cases/{lost['cid']}", headers=lost["h"]).json()["state"] == "evidence_received"
    assert db_session.scalar(select(FinderReport)).reporter_id is not None


def test_unknown_beacon_gets_the_same_answer_and_stores_nothing(client, lost, auth_header):
    finder = auth_header("finder@example.com")
    r = report(client, finder, lost, bid="0123456789abcdef")
    assert r.status_code == 202 and r.json() == {"status": "received"}
    assert client.get(f"/cases/{lost['cid']}/observations", headers=lost["h"]).json() == []


def test_replayed_report_is_stored_once(client, lost, auth_header):
    finder = auth_header("finder@example.com")
    for _ in range(3):
        assert report(client, finder, lost).status_code == 202
    assert len(client.get(f"/cases/{lost['cid']}/observations", headers=lost["h"]).json()) == 1


def test_only_active_cases_are_matched(client, lost, auth_header):
    client.post(f"/cases/{lost['cid']}/recovered", headers=lost["h"])
    finder = auth_header("finder@example.com")
    assert report(client, finder, lost).status_code == 202
    assert client.get(f"/cases/{lost['cid']}/observations", headers=lost["h"]).json() == []


def test_unenrolled_or_caseless_device_is_never_matched(client, auth_header, verified_device):
    h = auth_header()
    did = verified_device(h)  # verified but never enrolled, no case
    finder = auth_header("finder@example.com")
    lostlike = {"secret": bytes(32)}
    assert report(client, finder, lostlike).status_code == 202
    assert did


def test_rules_still_apply_to_ble_reports(client, lost, auth_header):
    finder = auth_header("finder@example.com")
    stale = now() - timedelta(hours=30)
    report(client, finder, lost, at=stale, nonce="stale-nonce-0001")
    report(client, finder, lost, at=now() - timedelta(days=9), nonce="old-nonce-00001")  # rejected silently
    obs = client.get(f"/cases/{lost['cid']}/observations", headers=lost["h"]).json()
    assert len(obs) == 1 and obs[0]["flags"] == ["stale"]


def test_report_with_wrong_window_is_ignored(client, lost, auth_header):
    finder = auth_header("finder@example.com")
    at = now() - timedelta(minutes=2)
    old_id = beacon_id(lost["secret"], window_of(at) - 5)
    report(client, finder, lost, at=at, bid=old_id)
    assert client.get(f"/cases/{lost['cid']}/observations", headers=lost["h"]).json() == []


def test_reports_need_login_and_valid_fields(client, lost, auth_header):
    assert client.post("/reports", json={}).status_code == 401
    finder = auth_header("finder@example.com")
    bad = report(client, finder, lost, bid="NOT-HEX")
    assert bad.status_code == 422 and "NOT-HEX" not in bad.text


def test_reports_are_rate_limited_per_account(client, lost, auth_header):
    finder = auth_header("finder@example.com")
    codes = [report(client, finder, lost, nonce=f"nonce-{i:04d}-xx").status_code for i in range(121)]
    assert codes[:120] == [202] * 120 and codes[120] == 429


def test_deleting_the_device_removes_keys_and_reports(client, lost, auth_header, db_session):
    finder = auth_header("finder@example.com")
    report(client, finder, lost)
    assert client.delete(f"/devices/{lost['did']}", headers=lost["h"]).status_code == 204
    assert db_session.scalar(select(BeaconKey)) is None
    assert db_session.scalar(select(FinderReport)) is None
    assert db_session.scalar(select(Observation)) is None
