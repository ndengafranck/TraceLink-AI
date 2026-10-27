from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Device, OwnershipProof

IMEI_1 = "490154203237518"
IMEI_2 = "356938035643809"


def _register_device(client, headers, imei=IMEI_1):
    r = client.post(
        "/devices", json={"nickname": "p", "model": "Infinix", "imei": imei}, headers=headers
    )
    assert r.status_code == 201
    return r.json()["id"]


def _challenge(client, headers, device_id):
    return client.post(f"/devices/{device_id}/ownership/challenge", headers=headers)


def _verify(client, headers, device_id, code):
    return client.post(
        f"/devices/{device_id}/ownership/verify", json={"code": code}, headers=headers
    )


@pytest.fixture()
def fixed_codes(monkeypatch):
    """Make the 'random' codes predictable: 111111, 222222, 333333, ..."""
    counter = iter(range(111111, 999999, 111111))
    monkeypatch.setattr("app.routers.ownership.secrets.randbelow", lambda _n: next(counter))


# --- happy path -----------------------------------------------------------

def test_challenge_then_verify_marks_device_verified(client, auth_header):
    h = auth_header()
    device_id = _register_device(client, h)
    c = _challenge(client, h, device_id)
    assert c.status_code == 201
    body = c.json()
    assert body["channel"] == "demo"
    assert len(body["code"]) == 6 and body["code"].isdigit()

    v = _verify(client, h, device_id, body["code"])
    assert v.status_code == 200
    assert v.json()["status"] == "verified"
    assert v.json()["verified_via"] == "demo"  # simulated proof is labelled as such

    listed = client.get("/devices", headers=h).json()[0]
    assert listed["status"] == "verified" and listed["verified_via"] == "demo"


def test_new_device_has_no_verified_via(client, auth_header):
    h = auth_header()
    _register_device(client, h)
    d = client.get("/devices", headers=h).json()[0]
    assert d["status"] == "unverified" and d["verified_via"] is None


def test_code_is_not_stored_in_plain_text(client, auth_header, db_session):
    h = auth_header()
    device_id = _register_device(client, h)
    code = _challenge(client, h, device_id).json()["code"]
    proof = db_session.scalar(select(OwnershipProof))
    assert code not in proof.code_digest
    assert len(proof.code_digest) == 64


def test_verify_again_after_success_is_harmless(client, auth_header):
    h = auth_header()
    device_id = _register_device(client, h)
    code = _challenge(client, h, device_id).json()["code"]
    assert _verify(client, h, device_id, code).status_code == 200
    assert _verify(client, h, device_id, "000000").status_code == 200  # already verified


def test_challenge_on_verified_device_is_rejected(client, auth_header):
    h = auth_header()
    device_id = _register_device(client, h)
    code = _challenge(client, h, device_id).json()["code"]
    _verify(client, h, device_id, code)
    assert _challenge(client, h, device_id).status_code == 409


# --- wrong, expired, locked -------------------------------------------------

def test_wrong_code_is_rejected_and_device_stays_unverified(client, auth_header, fixed_codes):
    h = auth_header()
    device_id = _register_device(client, h)
    _challenge(client, h, device_id)  # code is 111111
    r = _verify(client, h, device_id, "999999")
    assert r.status_code == 400
    assert client.get(f"/devices/{device_id}", headers=h).json()["status"] == "unverified"


def test_code_locks_after_five_wrong_guesses(client, auth_header, fixed_codes):
    h = auth_header()
    device_id = _register_device(client, h)
    _challenge(client, h, device_id)  # code is 111111
    for _ in range(5):
        assert _verify(client, h, device_id, "000000").status_code == 400
    # Even the correct code no longer works: the challenge is locked.
    assert _verify(client, h, device_id, "111111").status_code == 400
    assert client.get(f"/devices/{device_id}", headers=h).json()["status"] == "unverified"


def test_expired_code_is_rejected(client, auth_header, db_session, fixed_codes):
    h = auth_header()
    device_id = _register_device(client, h)
    _challenge(client, h, device_id)  # code is 111111
    proof = db_session.scalar(select(OwnershipProof))
    proof.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert _verify(client, h, device_id, "111111").status_code == 400


def test_verify_without_any_challenge_is_rejected(client, auth_header):
    h = auth_header()
    device_id = _register_device(client, h)
    assert _verify(client, h, device_id, "123456").status_code == 400


def test_failure_messages_do_not_reveal_the_reason(client, auth_header, fixed_codes):
    h = auth_header()
    device_id = _register_device(client, h)
    no_challenge = _verify(client, h, device_id, "123456")
    _challenge(client, h, device_id)
    wrong = _verify(client, h, device_id, "999999")
    assert no_challenge.json() == wrong.json()


def test_malformed_code_is_rejected_without_echo(client, auth_header):
    h = auth_header()
    device_id = _register_device(client, h)
    r = _verify(client, h, device_id, "abc123x")
    assert r.status_code == 422
    assert "abc123x" not in r.text


# --- replacement, binding, rate limit --------------------------------------

def test_new_challenge_cancels_the_old_code(client, auth_header, fixed_codes):
    h = auth_header()
    device_id = _register_device(client, h)
    _challenge(client, h, device_id)  # 111111
    _challenge(client, h, device_id)  # 222222 replaces it
    assert _verify(client, h, device_id, "111111").status_code == 400
    assert _verify(client, h, device_id, "222222").status_code == 200


def test_code_for_one_device_cannot_verify_another(client, auth_header, fixed_codes):
    h = auth_header()
    first = _register_device(client, h, IMEI_1)
    second = _register_device(client, h, IMEI_2)
    _challenge(client, h, first)   # 111111
    _challenge(client, h, second)  # 222222
    assert _verify(client, h, second, "111111").status_code == 400
    assert client.get(f"/devices/{second}", headers=h).json()["status"] == "unverified"


def test_challenge_requests_are_rate_limited(client, auth_header):
    h = auth_header()
    device_id = _register_device(client, h)
    for _ in range(3):
        assert _challenge(client, h, device_id).status_code == 201
    assert _challenge(client, h, device_id).status_code == 429


# --- who may do this ---------------------------------------------------------

def test_requires_login(client, auth_header):
    device_id = _register_device(client, auth_header())
    assert client.post(f"/devices/{device_id}/ownership/challenge").status_code == 401
    assert (
        client.post(f"/devices/{device_id}/ownership/verify", json={"code": "123456"}).status_code
        == 401
    )


def test_other_users_cannot_challenge_or_verify_my_device(client, auth_header, fixed_codes):
    a = auth_header("a@example.com")
    b = auth_header("b@example.com")
    device_id = _register_device(client, a)
    assert _challenge(client, b, device_id).status_code == 404
    _challenge(client, a, device_id)  # 111111
    assert _verify(client, b, device_id, "111111").status_code == 404


# --- demo mode switch --------------------------------------------------------

def test_without_demo_mode_no_code_is_issued(client, auth_header, monkeypatch):
    h = auth_header()
    device_id = _register_device(client, h)
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    r = _challenge(client, h, device_id)
    assert r.status_code == 503


# --- cleanup -----------------------------------------------------------------

def test_deleting_a_verified_device_removes_its_proofs(client, auth_header, db_session):
    h = auth_header()
    device_id = _register_device(client, h)
    code = _challenge(client, h, device_id).json()["code"]
    _verify(client, h, device_id, code)
    assert client.delete(f"/devices/{device_id}", headers=h).status_code == 204
    assert db_session.scalar(select(Device)) is None
    assert db_session.scalar(select(OwnershipProof)) is None
