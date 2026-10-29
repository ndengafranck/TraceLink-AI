import json

import pytest

from app.main import app
from app.ratelimit import explain_limiter
from app.routers.explanation import get_model_client
from tests.test_ai import FakeClient, answer, ids, tool_call, use

IMEI = "490154203237518"


@pytest.fixture(autouse=True)
def _reset():
    explain_limiter.reset()
    yield
    app.dependency_overrides.pop(get_model_client, None)


@pytest.fixture()
def case(client, auth_header, verified_device):
    h = auth_header()
    did = verified_device(h)
    cid = client.post(f"/devices/{did}/cases", headers=h).json()["id"]
    client.post(f"/cases/{cid}/observations/simulate", json={"scenario": "fresh_cluster"}, headers=h)
    return cid, h


def post(client, path, h, body=None):
    return client.post(path, headers=h, json=body) if body is not None else client.post(path, headers=h)


def narrative(text="My phone has three sightings that passed the checks. They are recent.", reqs=None):
    return {"content": json.dumps({"summary": text, "requests": reqs or ["Please record this report."]})}


# ---------- language ----------

def test_default_language_is_english_and_invalid_is_rejected(client, case):
    cid, h = case
    use(None)
    assert post(client, f"/cases/{cid}/explanation", h).json()["language"] == "en"
    assert post(client, f"/cases/{cid}/explanation", h, {"language": "de"}).status_code == 422


def test_french_fallback_is_in_french(client, case):
    cid, h = case
    use(None)
    r = post(client, f"/cases/{cid}/explanation", h, {"language": "fr"}).json()
    assert r["language"] == "fr" and "signalement" in r["explanation"]["headline"]
    assert "SIMULÉS" in r["notice"] and r["explanation"]["findings"]


def test_language_reaches_the_model_prompt(client, case):
    cid, h = case
    real = ids(client, cid, h)
    fake = FakeClient(answer(real[:1], text="Un signalement a passé les contrôles."))
    use(fake)
    r = post(client, f"/cases/{cid}/explanation", h, {"language": "fr"}).json()
    assert r["source"] == "ai" and r["language"] == "fr"
    assert "French" in fake.calls[0][0]["content"]


@pytest.mark.parametrize("text", [
    "Le téléphone a été volé.", "Un voleur l'a déplacé.", "C'est certainement ici.",
    "La police devrait accuser le détenteur.", "Vu à 12h08 hier.",
])
def test_french_forbidden_words_and_times_are_rejected(client, case, text):
    cid, h = case
    real = ids(client, cid, h)
    use(FakeClient(answer(real[:1], text=text), answer(real[:1], text=text)))
    assert post(client, f"/cases/{cid}/explanation", h, {"language": "fr"}).json()["fallback_reason"] == "ai_output_rejected"


def test_claiming_more_sightings_than_exist_is_rejected(client, case):
    cid, h = case
    real = ids(client, cid, h)
    bad = answer(real[:1], text="40 sightings were accepted.")
    use(FakeClient(bad, bad))
    assert post(client, f"/cases/{cid}/explanation", h).json()["fallback_reason"] == "ai_output_rejected"


def test_a_correct_count_is_accepted(client, case):
    cid, h = case
    real = ids(client, cid, h)
    use(FakeClient(answer(real[:1], text=f"{len(real)} sightings were stored.")))
    assert post(client, f"/cases/{cid}/explanation", h).json()["source"] == "ai"


# ---------- report draft ----------

def test_draft_without_ai_is_a_complete_fallback(client, case):
    cid, h = case
    use(None)
    r = post(client, f"/cases/{cid}/report-draft", h, {"audience": "operator"}).json()
    assert r["source"] == "fallback" and r["fallback_reason"] == "ai_not_configured"
    assert "block the SIM" in r["body"] and "SIGHTINGS" in r["body"]


def test_draft_facts_come_from_code_and_imei_stays_out(client, case):
    cid, h = case
    fake = FakeClient(tool_call("list_observations"), narrative())
    use(fake)
    r = post(client, f"/cases/{cid}/report-draft", h, {"audience": "police"}).json()
    assert r["source"] == "ai" and r["model"] == "fake-model"
    body = r["body"]
    assert "Infinix" in body and "ending 7518" in body and IMEI not in body
    assert "UTC" in body and "DEMO check only" in body and "SIMULATED" in body
    assert "My phone has three sightings" in body            # the model's sentence
    sent = json.dumps(fake.calls)
    assert IMEI not in sent and "owner@example.com" not in sent and "7518" not in sent


def test_draft_says_when_ownership_was_confirmed_on_the_phone(client, auth_header):
    h = auth_header()
    did = client.post("/devices", json={"nickname": "p", "model": "Tecno Pop 30C", "imei": IMEI}, headers=h).json()["id"]
    code = client.post(f"/companion/devices/{did}/challenge", headers=h).json()["code"]
    client.post(f"/devices/{did}/ownership/verify", json={"code": code}, headers=h)
    cid = client.post(f"/devices/{did}/cases", headers=h).json()["id"]
    client.post(f"/cases/{cid}/observations/simulate", json={"scenario": "fresh_cluster"}, headers=h)
    use(None)
    body = post(client, f"/cases/{cid}/report-draft", h).json()["body"]
    assert "code shown on the phone itself" in body and "DEMO" not in body.split("SUMMARY")[0]


def test_draft_in_french(client, case):
    cid, h = case
    use(None)
    r = post(client, f"/cases/{cid}/report-draft", h, {"language": "fr", "audience": "police"}).json()
    assert r["language"] == "fr" and "SIGNALEMENTS" in r["body"] and "SIMULÉES" in r["body"]
    assert r["title"].startswith("Déclaration")


def test_draft_narrative_is_checked_like_everything_else(client, case):
    cid, h = case
    bad = narrative(text="My phone was stolen by a thief, I am certain of it.")
    use(FakeClient(bad, bad))
    r = post(client, f"/cases/{cid}/report-draft", h).json()
    assert r["source"] == "fallback" and r["fallback_reason"] == "ai_output_rejected"
    assert "stolen" not in r["body"]


def test_draft_with_invented_coordinates_is_rejected(client, case):
    cid, h = case
    bad = narrative(text="My phone was last seen near 5.12345, 7.54321 in the evening.")
    use(FakeClient(bad, bad))
    assert post(client, f"/cases/{cid}/report-draft", h).json()["source"] == "fallback"


def test_draft_with_no_sightings_still_works(client, auth_header, verified_device):
    h = auth_header()
    cid = client.post(f"/devices/{verified_device(h)}/cases", headers=h).json()["id"]
    use(FakeClient())
    r = post(client, f"/cases/{cid}/report-draft", h).json()
    assert r["fallback_reason"] == "no_sightings" and "No sightings have been received." in r["body"]


def test_draft_is_owner_only_logged_and_shares_the_rate_limit(client, case, auth_header):
    cid, h = case
    use(None)
    other = auth_header("other@example.com")
    assert post(client, f"/cases/{cid}/report-draft", other).status_code == 404
    assert client.post(f"/cases/{cid}/report-draft").status_code == 401
    post(client, f"/cases/{cid}/report-draft", h)
    assert "report_draft_requested" in [e["action"] for e in client.get("/audit", headers=h).json()]
    codes = [post(client, f"/cases/{cid}/report-draft", h).status_code for _ in range(20)]
    assert codes[-1] == 429


def test_long_lists_are_cut_and_say_so(client, auth_header, verified_device, db_session):
    from datetime import datetime, timedelta, timezone
    from app.models import Observation
    h = auth_header()
    cid = client.post(f"/devices/{verified_device(h)}/cases", headers=h).json()["id"]
    now = datetime.now(timezone.utc)
    for i in range(20):
        db_session.add(Observation(case_id=cid, source="ble", observed_at=now - timedelta(minutes=i * 30),
                                   lat=4.05 + i * 0.01, lon=9.77, accuracy_m=20, nonce=f"n-{i:06d}",
                                   validation_status="accepted", flags=[]))
    db_session.commit()
    use(None)
    body = post(client, f"/cases/{cid}/report-draft", h).json()["body"]
    assert "... and 5 more not listed." in body and "SIMULATED" not in body
