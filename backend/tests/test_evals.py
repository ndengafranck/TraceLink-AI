from evals import run as ev
from evals.cases import CASES, build


def test_cases_build_without_a_database():
    for name in CASES:
        obs = build(name)
        assert len(obs) == len(CASES[name])
        assert all(o.id.startswith("eval-") for o in obs)


def test_language_check():
    assert ev.language_ok("Les signalements sont récents et ce n'est pas sûr.", "fr")
    assert not ev.language_ok("The sightings are recent and this is not sure.", "fr")
    assert ev.language_ok("The sightings are recent and this is not sure.", "en")


def test_mock_run_exercises_the_guard_and_the_report(tmp_path):
    result = ev.main(["--mock", "--out", str(tmp_path)])
    rows = result["rows"]
    assert len(rows) == len(CASES) * 2
    assert any(r["problems"] for r in rows)                      # the guard caught something
    assert all(r["ai_output_clean"] is not False for r in rows)  # nothing bad was shown
    empty = [r for r in rows if r["case"] == "empty_case"]
    assert all(r["final"] == "fallback" and r["calls"] == 0 for r in empty)
    assert all(r["language_ok"] for r in rows)
    report = (tmp_path / "REPORT.md").read_text()
    assert "MOCK RUN" in report and "not a real model" in report
    assert (tmp_path / "results.json").exists()


def test_live_without_a_key_stops_with_a_clear_message(tmp_path, monkeypatch):
    import pytest
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "model_api_key", "")
    with pytest.raises(SystemExit):
        ev.main(["--live", "--out", str(tmp_path)])


def test_mock_run_shows_every_kind_of_mistake_being_caught(tmp_path):
    result = ev.main(["--mock", "--out", str(tmp_path)])
    text = " ".join(" ".join(r["problems"]) for r in result["rows"])
    for expected in ("unknown observation ids", "forbidden word", "clock times", "not valid JSON", "only"):
        assert expected in text
    assert any(r["json_ok_first"] is False for r in result["rows"])
