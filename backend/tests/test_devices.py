import pytest
from sqlalchemy import select

from app.crypto import decrypt_imei, imei_fingerprint, is_valid_imei, mask_imei
from app.models import Device

IMEI_A = "490154203237518"  # passes the Luhn check
IMEI_B = "356938035643809"  # passes the Luhn check


def _body(imei=IMEI_A, nickname="My phone", model="Infinix Smart 7 HD"):
    return {"nickname": nickname, "model": model, "imei": imei}


# --- IMEI helpers ---------------------------------------------------------

def test_sample_imeis_are_valid():
    assert is_valid_imei(IMEI_A) and is_valid_imei(IMEI_B)


@pytest.mark.parametrize(
    "bad", ["490154203237519", "49015420323751", "49015420323751a", "", "0" * 16]
)
def test_invalid_imeis_are_rejected(bad):
    assert not is_valid_imei(bad)


def test_mask_shows_only_last_four():
    assert mask_imei("7518") == "***********7518"


# --- registration ---------------------------------------------------------

def test_requires_login(client):
    assert client.post("/devices", json=_body()).status_code == 401
    assert client.get("/devices").status_code == 401


def test_register_returns_masked_imei_only(client, auth_header):
    r = client.post("/devices", json=_body(), headers=auth_header())
    assert r.status_code == 201
    body = r.json()
    assert body["imei_masked"] == "***********7518"
    assert body["status"] == "unverified"
    assert IMEI_A not in r.text


def test_imei_is_not_stored_in_plain_text(client, auth_header, db_session):
    client.post("/devices", json=_body(), headers=auth_header())
    device = db_session.scalar(select(Device))
    assert IMEI_A not in device.imei_encrypted
    assert IMEI_A not in device.imei_hmac
    assert device.imei_hmac == imei_fingerprint(IMEI_A)
    assert decrypt_imei(device.imei_encrypted) == IMEI_A  # round trip works


def test_invalid_imei_is_rejected_without_echo(client, auth_header):
    r = client.post("/devices", json=_body(imei="490154203237519"), headers=auth_header())
    assert r.status_code == 422
    assert "490154203237519" not in r.text


def test_empty_nickname_rejected(client, auth_header):
    r = client.post("/devices", json=_body(nickname=""), headers=auth_header())
    assert r.status_code == 422


def test_same_imei_cannot_be_registered_twice_by_different_users(client, auth_header):
    a = auth_header("a@example.com")
    b = auth_header("b@example.com")
    assert client.post("/devices", json=_body(), headers=a).status_code == 201
    r = client.post("/devices", json=_body(), headers=b)
    assert r.status_code == 409
    assert IMEI_A not in r.text
    assert "a@example.com" not in r.text  # never reveals who owns it


# --- owner-only access (object-level authorization) ------------------------

def test_list_shows_only_my_devices(client, auth_header):
    a = auth_header("a@example.com")
    b = auth_header("b@example.com")
    client.post("/devices", json=_body(IMEI_A, "A phone"), headers=a)
    client.post("/devices", json=_body(IMEI_B, "B phone"), headers=b)
    names_a = [d["nickname"] for d in client.get("/devices", headers=a).json()]
    names_b = [d["nickname"] for d in client.get("/devices", headers=b).json()]
    assert names_a == ["A phone"]
    assert names_b == ["B phone"]


def test_user_cannot_read_another_users_device(client, auth_header):
    a = auth_header("a@example.com")
    b = auth_header("b@example.com")
    device_id = client.post("/devices", json=_body(), headers=a).json()["id"]
    assert client.get(f"/devices/{device_id}", headers=a).status_code == 200
    assert client.get(f"/devices/{device_id}", headers=b).status_code == 404


def test_user_cannot_delete_another_users_device(client, auth_header, db_session):
    a = auth_header("a@example.com")
    b = auth_header("b@example.com")
    device_id = client.post("/devices", json=_body(), headers=a).json()["id"]
    assert client.delete(f"/devices/{device_id}", headers=b).status_code == 404
    assert db_session.get(Device, device_id) is not None


def test_other_users_device_and_missing_device_look_identical(client, auth_header):
    a = auth_header("a@example.com")
    b = auth_header("b@example.com")
    device_id = client.post("/devices", json=_body(), headers=a).json()["id"]
    theirs = client.get(f"/devices/{device_id}", headers=b)
    missing = client.get("/devices/does-not-exist", headers=b)
    assert theirs.status_code == missing.status_code == 404
    assert theirs.json() == missing.json()


def test_owner_can_delete_and_imei_can_be_registered_again(client, auth_header):
    a = auth_header("a@example.com")
    device_id = client.post("/devices", json=_body(), headers=a).json()["id"]
    assert client.delete(f"/devices/{device_id}", headers=a).status_code == 204
    assert client.get(f"/devices/{device_id}", headers=a).status_code == 404
    assert client.post("/devices", json=_body(), headers=a).status_code == 201
