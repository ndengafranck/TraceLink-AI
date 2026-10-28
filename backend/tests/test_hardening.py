from sqlalchemy import select

from app.models import AuditEvent

PW = "correct horse battery"


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


# ---------- login lockout ----------

def test_five_failures_lock_the_account_even_for_the_right_password(client, register):
    register()
    for _ in range(5):
        assert login(client, "owner@example.com", "wrong-password-1").status_code == 401
    r = login(client, "owner@example.com", PW)
    assert r.status_code == 429 and r.headers["retry-after"] == "900"


def test_unknown_email_is_limited_the_same_way(client):
    codes = [login(client, "nobody@example.com", "whatever-12345").status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]


def test_lockout_is_per_email(client, register):
    register()
    register("other@example.com")
    for _ in range(5):
        login(client, "owner@example.com", "wrong-password-1")
    assert login(client, "other@example.com", PW).status_code == 200


def test_success_resets_the_counter(client, register):
    register()
    for _ in range(4):
        login(client, "owner@example.com", "wrong-password-1")
    assert login(client, "owner@example.com", PW).status_code == 200
    for _ in range(4):
        assert login(client, "owner@example.com", "wrong-password-1").status_code == 401


def test_email_case_does_not_bypass_the_lockout(client, register):
    register()
    for i in range(5):
        login(client, ("OWNER@example.com" if i % 2 else "owner@example.com"), "wrong-password-1")
    assert login(client, "Owner@Example.com", PW).status_code == 429


# ---------- audit trail ----------

def actions(client, headers):
    return [e["action"] for e in client.get("/audit", headers=headers).json()]


def test_audit_records_the_whole_lifecycle(client, auth_header, verified_device):
    h = auth_header()
    did = verified_device(h)
    cid = client.post(f"/devices/{did}/cases", headers=h).json()["id"]
    client.post(f"/cases/{cid}/observations/simulate", json={"scenario": "fresh_cluster"}, headers=h)
    client.post(f"/cases/{cid}/recovered", headers=h)
    client.post(f"/cases/{cid}/close", headers=h)
    got = actions(client, h)
    for expected in ["registered", "login", "device_added", "code_requested", "ownership_verified",
                     "case_opened", "demo_sightings_added", "case_recovered", "case_closed"]:
        assert expected in got
    assert got[0] == "case_closed"  # newest first


def test_failed_logins_are_recorded_against_the_account(client, register, auth_header):
    register()
    login(client, "owner@example.com", "wrong-password-1")
    h = auth_header()
    assert "login_failed" in actions(client, h)


def test_unknown_email_failure_is_recorded_without_a_user(client, db_session):
    login(client, "ghost@example.com", "whatever-12345")
    ev = db_session.scalar(select(AuditEvent).where(AuditEvent.action == "login_failed"))
    assert ev.user_id is None


def test_users_only_see_their_own_activity(client, auth_header, verified_device):
    a = auth_header()
    verified_device(a)
    b = auth_header("b@example.com")
    assert "device_added" not in actions(client, b)


def test_audit_requires_login_and_limit_is_bounded(client, auth_header):
    assert client.get("/audit").status_code == 401
    h = auth_header()
    assert len(client.get("/audit?limit=1", headers=h).json()) == 1


def test_audit_never_contains_secrets(client, auth_header, verified_device, db_session):
    h = auth_header()
    did = verified_device(h)
    code = client.post(f"/companion/devices/{did}/enroll", headers=h).json()["beacon_secret"]
    dump = " ".join(
        f"{e.action}{e.target_type}{e.target_id}{e.detail}" for e in db_session.scalars(select(AuditEvent))
    )
    assert code not in dump and PW not in dump and "490154203237518" not in dump


def test_deleting_a_device_keeps_a_record_of_it(client, auth_header, verified_device):
    h = auth_header()
    did = verified_device(h)
    client.delete(f"/devices/{did}", headers=h)
    events = client.get("/audit", headers=h).json()
    assert events[0]["action"] == "device_deleted" and events[0]["target_id"] == did
