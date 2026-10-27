from sqlalchemy import select

from app.models import Case


def _open(client, headers, device_id):
    return client.post(f"/devices/{device_id}/cases", headers=headers)


def test_requires_login(client, auth_header, verified_device):
    device_id = verified_device(auth_header())
    assert client.post(f"/devices/{device_id}/cases").status_code == 401
    assert client.get("/cases").status_code == 401


def test_unverified_device_cannot_open_a_case(client, auth_header):
    h = auth_header()
    device_id = client.post(
        "/devices", json={"nickname": "p", "model": "x", "imei": "490154203237518"}, headers=h
    ).json()["id"]
    assert _open(client, h, device_id).status_code == 409


def test_open_case_for_verified_device(client, auth_header, verified_device):
    h = auth_header()
    device_id = verified_device(h)
    r = _open(client, h, device_id)
    assert r.status_code == 201
    body = r.json()
    assert body["state"] == "open" and body["device_id"] == device_id
    assert body["closed_at"] is None


def test_only_one_active_case_per_device(client, auth_header, verified_device):
    h = auth_header()
    device_id = verified_device(h)
    assert _open(client, h, device_id).status_code == 201
    assert _open(client, h, device_id).status_code == 409


def test_new_case_allowed_after_the_old_one_is_closed(client, auth_header, verified_device):
    h = auth_header()
    device_id = verified_device(h)
    case_id = _open(client, h, device_id).json()["id"]
    assert client.post(f"/cases/{case_id}/close", headers=h).status_code == 200
    assert _open(client, h, device_id).status_code == 201


def test_database_itself_blocks_two_active_cases(client, auth_header, verified_device, db_session):
    """The partial unique index is the safety net if two requests race."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    h = auth_header()
    device_id = verified_device(h)
    first = _open(client, h, device_id).json()
    db_session.add(Case(device_id=device_id, opened_by="someone"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert first["state"] == "open"


# --- state machine ---------------------------------------------------------

def test_open_to_recovered_to_closed(client, auth_header, verified_device):
    h = auth_header()
    case_id = _open(client, h, verified_device(h)).json()["id"]
    r = client.post(f"/cases/{case_id}/recovered", headers=h)
    assert r.status_code == 200 and r.json()["state"] == "recovered"
    r = client.post(f"/cases/{case_id}/close", headers=h)
    assert r.status_code == 200 and r.json()["state"] == "closed"
    assert r.json()["closed_at"] is not None


def test_open_can_be_closed_directly(client, auth_header, verified_device):
    h = auth_header()
    case_id = _open(client, h, verified_device(h)).json()["id"]
    assert client.post(f"/cases/{case_id}/close", headers=h).json()["state"] == "closed"


def test_closed_case_is_final(client, auth_header, verified_device):
    h = auth_header()
    case_id = _open(client, h, verified_device(h)).json()["id"]
    client.post(f"/cases/{case_id}/close", headers=h)
    assert client.post(f"/cases/{case_id}/recovered", headers=h).status_code == 409
    assert client.post(f"/cases/{case_id}/close", headers=h).status_code == 409


def test_recovered_cannot_be_recovered_again(client, auth_header, verified_device):
    h = auth_header()
    case_id = _open(client, h, verified_device(h)).json()["id"]
    client.post(f"/cases/{case_id}/recovered", headers=h)
    assert client.post(f"/cases/{case_id}/recovered", headers=h).status_code == 409


# --- who may do this -----------------------------------------------------------

def test_other_users_cannot_see_or_change_my_case(client, auth_header, verified_device):
    a = auth_header("a@example.com")
    b = auth_header("b@example.com")
    device_id = verified_device(a)
    case_id = _open(client, a, device_id).json()["id"]
    assert _open(client, b, device_id).status_code == 404
    assert client.get(f"/cases/{case_id}", headers=b).status_code == 404
    assert client.post(f"/cases/{case_id}/recovered", headers=b).status_code == 404
    assert client.post(f"/cases/{case_id}/close", headers=b).status_code == 404
    assert client.get(f"/cases/{case_id}", headers=a).json()["state"] == "open"


def test_list_shows_only_my_cases(client, auth_header, verified_device):
    a = auth_header("a@example.com")
    b = auth_header("b@example.com")
    _open(client, a, verified_device(a, "490154203237518"))
    _open(client, b, verified_device(b, "356938035643809"))
    assert len(client.get("/cases", headers=a).json()) == 1
    assert len(client.get("/cases", headers=b).json()) == 1


def test_other_users_case_and_missing_case_look_identical(client, auth_header, verified_device):
    a = auth_header("a@example.com")
    b = auth_header("b@example.com")
    case_id = _open(client, a, verified_device(a)).json()["id"]
    theirs = client.get(f"/cases/{case_id}", headers=b)
    missing = client.get("/cases/does-not-exist", headers=b)
    assert theirs.status_code == missing.status_code == 404
    assert theirs.json() == missing.json()
    assert db_has_case_count_one(client, a)


def db_has_case_count_one(client, headers):
    return len(client.get("/cases", headers=headers).json()) == 1
