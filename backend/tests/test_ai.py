import json

import httpx
import pytest

from app.ai import guard
from app.ai.client import HttpModelClient, ModelUnavailable
from app.ai.schemas import Explanation
from app.ai.tools import run_tool
from app.config import Settings
from app.main import app
from app.ratelimit import explain_limiter
from app.routers.explanation import get_model_client


class FakeClient:
    """Scripted model: returns the queued assistant messages in order."""

    name = "fake-model"

    def __init__(self, *script):
        self.script = list(script)
        self.calls = []

    def chat(self, *, messages, tools=None, response_format=None):
        self.calls.append([dict(m) for m in messages])
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def tool_call(name, args=None, cid="c1"):
    return {"content": None, "tool_calls": [
        {"id": cid, "type": "function",
         "function": {"name": name, "arguments": json.dumps(args or {})}}]}


def answer(ids, text="Two sightings passed every check.", **over):
    body = {"headline": "Sightings stored", "findings": [{"text": text, "observation_ids": ids}],
            "guidance": ["Contact the police."], "uncertainty": ["Who holds the phone is unknown."]}
    body.update(over)
    return {"content": json.dumps(body)}


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
    client.post(f"/cases/{cid}/observations/simulate", json={"scenario": "fresh_cluster"},
                headers=h)
    return cid, h


def use(fake):
    app.dependency_overrides[get_model_client] = lambda: fake


def ids(client, cid, h):
    return [o["id"] for o in client.get(f"/cases/{cid}/observations", headers=h).json()]


def explain(client, cid, h):
    return client.post(f"/cases/{cid}/explanation", headers=h)


def test_no_sightings_skips_the_model(client, auth_header, verified_device):
    h = auth_header()
    cid = client.post(f"/devices/{verified_device(h)}/cases", headers=h).json()["id"]
    fake = FakeClient()
    use(fake)
    body = explain(client, cid, h).json()
    assert body["source"] == "fallback" and body["fallback_reason"] == "no_sightings"
    assert fake.calls == []


def test_ai_not_configured_gives_fallback(client, case):
    cid, h = case
    use(None)
    body = explain(client, cid, h).json()
    assert body["source"] == "fallback" and body["fallback_reason"] == "ai_not_configured"
    assert body["explanation"]["findings"]  # still useful without AI


def test_happy_path_uses_tools_and_cites_real_ids(client, case):
    cid, h = case
    real = ids(client, cid, h)
    fake = FakeClient(tool_call("list_observations"), answer(real[:2]))
    use(fake)
    r = explain(client, cid, h)
    body = r.json()
    assert r.status_code == 200 and body["source"] == "ai" and body["model"] == "fake-model"
    assert body["explanation"]["findings"][0]["observation_ids"] == real[:2]
    tool_msgs = [m for m in fake.calls[1] if m["role"] == "tool"]
    assert tool_msgs and real[0] in tool_msgs[0]["content"]


def test_facts_are_counted_by_code_not_the_model(client, case):
    cid, h = case
    use(FakeClient(answer(ids(client, cid, h)[:1])))
    facts = explain(client, cid, h).json()["facts"]
    assert facts["total"] == len(ids(client, cid, h))
    assert facts["accepted"] + facts["flagged"] == facts["total"]


def test_notice_says_simulated(client, case):
    cid, h = case
    use(None)
    assert "SIMULATED" in explain(client, cid, h).json()["notice"]


def test_unknown_observation_id_is_repaired_once(client, case):
    cid, h = case
    real = ids(client, cid, h)
    fake = FakeClient(answer(["not-a-real-id"]), answer(real[:1]))
    use(fake)
    body = explain(client, cid, h).json()
    assert body["source"] == "ai"
    assert "unknown observation ids" in fake.calls[1][-1]["content"]


def test_repeated_bad_output_falls_back(client, case):
    cid, h = case
    use(FakeClient(answer(["x"]), answer(["y"])))
    body = explain(client, cid, h).json()
    assert body["source"] == "fallback" and body["fallback_reason"] == "ai_output_rejected"


@pytest.mark.parametrize("text", [
    "The phone was stolen.", "A thief moved it.", "This is definitely the location.",
    "Police should accuse the holder.",
])
def test_decision_and_accusation_words_are_rejected(client, case, text):
    cid, h = case
    real = ids(client, cid, h)
    use(FakeClient(answer(real[:1], text=text), answer(real[:1], text=text)))
    assert explain(client, cid, h).json()["fallback_reason"] == "ai_output_rejected"


def test_invented_coordinates_are_rejected(client, case):
    cid, h = case
    real = ids(client, cid, h)
    bad = answer(real[:1], text="It was at 5.12345, 7.54321.")
    use(FakeClient(bad, bad))
    assert explain(client, cid, h).json()["fallback_reason"] == "ai_output_rejected"


def test_real_coordinates_rounded_are_allowed(client, case):
    cid, h = case
    obs = client.get(f"/cases/{cid}/observations", headers=h).json()[0]
    text = f"Latest point near {obs['lat']:.4f}, {obs['lon']:.4f}."
    use(FakeClient(answer([obs["id"]], text=text)))
    assert explain(client, cid, h).json()["source"] == "ai"


def test_invalid_json_and_wrong_shape_fall_back(client, case):
    cid, h = case
    use(FakeClient({"content": "sure! here you go"}, {"content": '{"headline": "x"}'}))
    assert explain(client, cid, h).json()["fallback_reason"] == "ai_output_rejected"


def test_extra_fields_are_rejected():
    with pytest.raises(ValueError):
        Explanation.model_validate({"headline": "h", "findings": [], "guidance": ["g"],
                                    "uncertainty": ["u"], "verdict": "stolen"})


def test_model_outage_gives_fallback(client, case):
    cid, h = case
    use(FakeClient(ModelUnavailable("down")))
    r = explain(client, cid, h)
    assert r.status_code == 200 and r.json()["fallback_reason"] == "ai_unavailable"


def test_endless_tool_calls_stop(client, case):
    cid, h = case
    fake = FakeClient(*[tool_call("get_case_summary") for _ in range(6)])
    use(fake)
    assert explain(client, cid, h).json()["fallback_reason"] == "ai_too_many_steps"
    assert len(fake.calls) == 6


def test_other_users_case_is_404(client, case, auth_header):
    cid, _ = case
    other = auth_header("other@example.com")
    use(FakeClient())
    assert explain(client, cid, other).status_code == 404


def test_requires_login(client, case):
    assert client.post(f"/cases/{case[0]}/explanation").status_code == 401


def test_explanation_requests_are_rate_limited(client, case):
    cid, h = case
    use(None)
    codes = [explain(client, cid, h).status_code for _ in range(21)]
    assert codes[:20] == [200] * 20 and codes[20] == 429


def test_tools_only_see_this_cases_observations(client, case, db_session):
    from sqlalchemy import select
    from app.models import Observation
    from datetime import datetime, timezone
    mine = list(db_session.scalars(select(Observation)))
    now = datetime.now(timezone.utc)
    out = json.loads(run_tool("get_observation", {"observation_id": "someone-elses"}, mine, now))
    assert "error" in out
    assert "error" in json.loads(run_tool("delete_everything", {}, mine, now))
    assert "error" in json.loads(run_tool("list_observations", "not json", mine, now))


def test_tool_output_has_no_personal_data(client, case, db_session):
    from sqlalchemy import select
    from app.models import Observation
    from datetime import datetime, timezone
    mine = list(db_session.scalars(select(Observation)))
    text = run_tool("list_observations", {}, mine, datetime.now(timezone.utc))
    for banned in ("imei", "email", "owner", "nickname", "model"):
        assert banned not in text.lower().replace("validation_status", "")


def test_guard_accepts_clean_output(client, case, db_session):
    from sqlalchemy import select
    from app.models import Observation
    mine = list(db_session.scalars(select(Observation)))
    e = Explanation(headline="ok", findings=[{"text": "fine", "observation_ids": [mine[0].id]}],
                    guidance=["call police"], uncertainty=["unknown holder"])
    assert guard.check(e, mine) == []


# --- the real HTTP client, with the network replaced ---------------------------------

def _settings():
    return Settings(jwt_secret="x" * 20, imei_encryption_key="k", imei_hmac_key="h",
                    model_api_key="SECRET-KEY-123", model_name="muse-spark-1.3")


def test_http_client_sends_key_and_model(monkeypatch):
    seen = {}

    def fake_post(url, json, headers, timeout):
        seen.update(url=url, body=json, headers=headers)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    msg = HttpModelClient(_settings()).chat(messages=[{"role": "user", "content": "x"}])
    assert msg["content"] == "hi"
    assert seen["url"] == "https://api.meta.ai/v1/chat/completions"
    assert seen["body"]["model"] == "muse-spark-1.3" and seen["body"]["reasoning_effort"] == "low"
    assert seen["headers"]["Authorization"] == "Bearer SECRET-KEY-123"


@pytest.mark.parametrize("failure", ["status", "network", "malformed"])
def test_http_client_errors_never_leak_the_key(monkeypatch, failure):
    def fake_post(url, json, headers, timeout):
        req = httpx.Request("POST", url, headers=headers)
        if failure == "network":
            raise httpx.ConnectTimeout("timeout", request=req)
        if failure == "status":
            return httpx.Response(401, json={"error": "bad"}, request=req)
        return httpx.Response(200, json={"nope": 1}, request=req)

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(ModelUnavailable) as e:
        HttpModelClient(_settings()).chat(messages=[])
    assert "SECRET-KEY-123" not in str(e.value)


# --- found on the first live run with the real model ----------------------------

@pytest.mark.parametrize("text", [
    "One sighting from 2026-10-27 at 06:19 is stale.",
    "Three sightings were accepted from 12:08 to 12:16.",
])
def test_clock_times_and_dates_are_rejected(client, case, text):
    cid, h = case
    real = ids(client, cid, h)
    use(FakeClient(answer(real[:1], text=text), answer(real[:1], text=text)))
    assert explain(client, cid, h).json()["fallback_reason"] == "ai_output_rejected"


def test_leaked_field_names_are_rejected(client, case):
    cid, h = case
    real = ids(client, cid, h)
    bad = answer(real[:1], text="It is demo data with source simulated.")
    use(FakeClient(bad, bad))
    assert explain(client, cid, h).json()["fallback_reason"] == "ai_output_rejected"


def test_relative_wording_is_accepted(client, case):
    cid, h = case
    real = ids(client, cid, h)
    use(FakeClient(answer(real[:1], text="This sighting is about 2 hours old, simulated demo data.")))
    assert explain(client, cid, h).json()["source"] == "ai"


def test_model_never_sees_absolute_times(client, case, db_session):
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.models import Observation
    mine = list(db_session.scalars(select(Observation)))
    out = run_tool("list_observations", {}, mine, datetime.now(timezone.utc))
    assert "observed_at" not in out and "age_minutes" in out


# --- retry and timeout behaviour of the real HTTP client ---------------------------

def test_http_client_retries_once_on_a_server_error_then_succeeds(monkeypatch):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append(timeout)
        req = httpx.Request("POST", url)
        if len(calls) == 1:
            return httpx.Response(503, json={}, request=req)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}, request=req)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr("app.ai.client.time.sleep", lambda s: None)
    assert HttpModelClient(_settings()).chat(messages=[])["content"] == "ok"
    assert len(calls) == 2 and calls[0] == 60.0


def test_http_client_does_not_retry_a_timeout_or_a_client_error(monkeypatch):
    n = {"calls": 0}

    def timeout_post(url, json, headers, timeout):
        n["calls"] += 1
        raise httpx.ReadTimeout("slow", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", timeout_post)
    with pytest.raises(ModelUnavailable):
        HttpModelClient(_settings()).chat(messages=[])
    assert n["calls"] == 1

    n["calls"] = 0

    def bad_request(url, json, headers, timeout):
        n["calls"] += 1
        return httpx.Response(400, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", bad_request)
    with pytest.raises(ModelUnavailable):
        HttpModelClient(_settings()).chat(messages=[])
    assert n["calls"] == 1


def test_http_client_gives_up_after_two_failures(monkeypatch):
    n = {"calls": 0}

    def always_503(url, json, headers, timeout):
        n["calls"] += 1
        return httpx.Response(503, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", always_503)
    monkeypatch.setattr("app.ai.client.time.sleep", lambda s: None)
    with pytest.raises(ModelUnavailable):
        HttpModelClient(_settings()).chat(messages=[])
    assert n["calls"] == 2


def test_the_model_is_given_the_counted_summary_up_front(client, case):
    cid, h = case
    real = ids(client, cid, h)
    fake = FakeClient(answer(real[:1]))
    use(fake)
    explain(client, cid, h)
    first_user = fake.calls[0][1]["content"]
    assert "Case summary (counted by the system)" in first_user and f'"total": {len(real)}' in first_user
