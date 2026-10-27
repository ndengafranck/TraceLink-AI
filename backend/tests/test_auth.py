from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select

from app.config import get_settings
from app.models import User
from tests.conftest import PASSWORD


def _token(sub="x", secret=None, alg="HS256", exp_delta=timedelta(minutes=5)):
    secret = secret or get_settings().jwt_secret
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": sub, "iat": now, "exp": now + exp_delta}, secret, algorithm=alg)


# --- registration ---------------------------------------------------------

def test_register_returns_user_without_password(register):
    r = register()
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "owner@example.com"
    assert "password" not in body and "password_hash" not in body


def test_password_is_stored_hashed(register, db_session):
    register()
    user = db_session.scalar(select(User))
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2")


def test_duplicate_email_is_rejected_case_insensitively(register):
    assert register("Owner@Example.com").status_code == 201
    assert register("owner@example.COM").status_code == 409


def test_short_password_is_rejected(register):
    assert register(password="short").status_code == 422


def test_invalid_email_is_rejected(register):
    assert register(email="not-an-email").status_code == 422


# --- login ----------------------------------------------------------------

def test_login_returns_bearer_token(client, register):
    register()
    r = client.post("/auth/login", json={"email": "owner@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_wrong_password_and_unknown_email_look_identical(client, register):
    register()
    wrong = client.post(
        "/auth/login", json={"email": "owner@example.com", "password": "wrong password!!"}
    )
    unknown = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "wrong password!!"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


# --- protected route ------------------------------------------------------

def test_me_requires_a_token(client):
    assert client.get("/me").status_code == 401


def test_me_returns_the_logged_in_user(client, auth_header):
    r = client.get("/me", headers=auth_header())
    assert r.status_code == 200
    assert r.json()["email"] == "owner@example.com"


def test_garbage_token_is_rejected(client):
    r = client.get("/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_expired_token_is_rejected(client, register, db_session):
    register()
    user = db_session.scalar(select(User))
    expired = _token(sub=user.id, exp_delta=timedelta(minutes=-1))
    assert client.get("/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_token_signed_with_another_secret_is_rejected(client, register, db_session):
    register()
    user = db_session.scalar(select(User))
    forged = _token(sub=user.id, secret="attacker-secret-attacker-secret-1234")
    assert client.get("/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_unsigned_alg_none_token_is_rejected(client, register, db_session):
    register()
    user = db_session.scalar(select(User))
    now = datetime.now(timezone.utc)
    unsigned = jwt.encode(
        {"sub": user.id, "exp": now + timedelta(minutes=5)}, key=None, algorithm="none"
    )
    assert client.get("/me", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


def test_token_for_deleted_user_is_rejected(client, auth_header, db_session):
    header = auth_header()
    db_session.delete(db_session.scalar(select(User)))
    db_session.commit()
    assert client.get("/me", headers=header).status_code == 401


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_validation_errors_do_not_echo_the_password(register):
    r = register(password="tiny-pw")
    assert r.status_code == 422
    assert "tiny-pw" not in r.text
