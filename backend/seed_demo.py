"""Fill the database with a ready-made demo account.

    python seed_demo.py

Creates (or reuses) demo@example.com and, through the real API:
  - "Demo phone" with ownership confirmed and an open case holding a fresh
    cluster of simulated sightings plus one conflicting jump;
  - "Spare phone", added but not yet verified (to show the ownership step).
Everything is labelled simulated in the app. Needs DEMO_MODE=true in .env.
Safe to run again: it never duplicates the account or the phones.
"""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

EMAIL = "demo@example.com"
PASSWORD = "demo-password-2026"
PHONES = [("Demo phone", "Infinix Smart 10 HD", "490154203237518"),
          ("Spare phone", "Tecno Pop 30C", "356938035643809")]


def main() -> None:
    if not get_settings().demo_mode:
        raise SystemExit("Set DEMO_MODE=true in backend/.env first.")
    with TestClient(app) as c:
        c.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})  # 409 if it exists: fine
        r = c.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code != 200:
            raise SystemExit(f"Could not sign in as {EMAIL}: {r.json().get('detail')}")
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        existing = {d["nickname"]: d for d in c.get("/devices", headers=h).json()}
        for nick, model, imei in PHONES:
            if nick not in existing:
                resp = c.post("/devices", json={"nickname": nick, "model": model, "imei": imei}, headers=h)
                if resp.status_code != 201:
                    raise SystemExit(f"Could not add {nick}: {resp.json().get('detail')} "
                                     "(is this IMEI registered to another account?)")
                existing[nick] = resp.json()

        main_phone = existing["Demo phone"]
        if main_phone["status"] != "verified":
            code = c.post(f"/devices/{main_phone['id']}/ownership/challenge", headers=h).json()["code"]
            c.post(f"/devices/{main_phone['id']}/ownership/verify", json={"code": code}, headers=h)

        cases = [x for x in c.get("/cases", headers=h).json()
                 if x["device_id"] == main_phone["id"] and x["state"] in ("open", "evidence_received")]
        if cases:
            print("The demo case already exists; leaving it as it is.")
        else:
            case = c.post(f"/devices/{main_phone['id']}/cases", headers=h).json()
            for scenario in ("fresh_cluster", "conflicting"):
                c.post(f"/cases/{case['id']}/observations/simulate", json={"scenario": scenario}, headers=h)
            print("Created the demo case with simulated sightings.")

    print(f"\nSign in on the website with:\n  email:    {EMAIL}\n  password: {PASSWORD}")


if __name__ == "__main__":
    main()
