import base64
import os

# Must be set before the app is imported: settings are read at import time.
os.environ["JWT_SECRET"] = "test-secret-not-used-anywhere-else-0123456789"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEMO_MODE"] = "true"
os.environ["IMEI_HMAC_KEY"] = "test-hmac-key-not-used-anywhere-else-0123456789"
# A fixed throwaway Fernet key (32 bytes, url-safe base64) used only in tests.
os.environ["IMEI_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"0" * 32).decode()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.ratelimit import reset_all


@pytest.fixture(autouse=True)
def _fresh_limiters():
    reset_all()
    yield


@pytest.fixture()
def db_session():
    # One shared in-memory database per test, so tests cannot affect each other.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


PASSWORD = "correct horse battery"


@pytest.fixture()
def register(client):
    def _register(email="owner@example.com", password=PASSWORD):
        return client.post("/auth/register", json={"email": email, "password": password})

    return _register


@pytest.fixture()
def auth_header(client, register):
    def _header(email="owner@example.com", password=PASSWORD):
        register(email, password)
        r = client.post("/auth/login", json={"email": email, "password": password})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _header


@pytest.fixture()
def verified_device(client):
    """Register a device and verify ownership (demo channel); returns its id."""

    def _make(headers, imei="490154203237518"):
        did = client.post(
            "/devices", json={"nickname": "p", "model": "Infinix", "imei": imei}, headers=headers
        ).json()["id"]
        code = client.post(f"/devices/{did}/ownership/challenge", headers=headers).json()["code"]
        client.post(f"/devices/{did}/ownership/verify", json={"code": code}, headers=headers)
        return did

    return _make
