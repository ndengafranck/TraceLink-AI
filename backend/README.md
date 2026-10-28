# TraceLink AI backend

Modular monolith: one FastAPI service, one PostgreSQL database.

## Slice 1 (done): accounts and authentication

- `POST /auth/register`: email + password (10 to 128 characters). Passwords are hashed with Argon2.
- `POST /auth/login`: returns a short-lived bearer token (JWT, 30 minutes by default).
- `GET /me`: the logged-in user. Every later endpoint will use the same `get_current_user` dependency.
- `GET /health`

## Slice 2 (done): device registration

- `POST /devices`: nickname, model, 15-digit IMEI (Luhn check digit verified).
- `GET /devices`, `GET /devices/{id}`, `DELETE /devices/{id}`: only your own devices.
- The IMEI is stored encrypted (Fernet) plus a keyed hash (HMAC-SHA256) that blocks duplicate registrations. Responses show only `***********1234`.
- Another user's device returns 404, identical to a device that does not exist.
- A second registration of the same IMEI returns 409 without saying who owns it. The ownership-dispute workflow (backlog item 10) will build on this.
- Status is `unverified` until the ownership-proof slice exists.
- Validation errors no longer echo submitted values (passwords, IMEIs).

## Slice 3 (done): ownership proof

- `POST /devices/{id}/ownership/challenge`: issues a 6-digit one-time code (10 minutes, 3 per device per hour; a new code cancels the old one).
- `POST /devices/{id}/ownership/verify` with `{"code": "123456"}`: 5 wrong guesses lock the code; success sets the device to `verified`.
- **The check is simulated for now.** The code has to reach the phone through a channel, and the Android companion app does not exist yet. With `DEMO_MODE=true` the API returns the code, and the device shows `verified_via: "demo"`. With demo mode off the challenge endpoint returns 503. Do not present a demo verification as a real on-device check.
- A new table (`ownership_proofs`) is created automatically; existing databases need no migration.

## Slice 4 (done): cases, sightings and the evidence engine

- `POST /devices/{id}/cases`: open a case (device must be verified; one active case per device).
- `GET /cases`, `GET /cases/{id}`, `POST /cases/{id}/recovered`, `POST /cases/{id}/close`: state machine `open → evidence_received → recovered → closed`.
- `POST /cases/{id}/observations`, `GET /cases/{id}/observations`: store and list sightings.
- `POST /cases/{id}/observations/simulate` with `{"scenario": "fresh_cluster" | "stale" | "conflicting" | "low_accuracy"}`: feeds a synthetic scenario through the same validation.
- The engine (`app/evidence.py`) rejects future, older-than-7-days and duplicate sightings (not stored), and flags `stale`, `low_accuracy` and `implausible_movement`. Replayed report ids get 409.
- **All sightings are simulated** and labelled `source: "simulated"`; the endpoints need `DEMO_MODE=true`. No real BLE source exists yet.
- Two new tables (`cases`, `observations`) are created automatically; existing databases need no migration. Deleting a device deletes its cases and sightings.

## Slice 5 (done): AI explanation (Meta Model API, Muse Spark 1.3)

- `POST /cases/{id}/explanation`: explains the case's stored sightings. Owner only (404 otherwise), 10 per hour per user.
- The model calls **read-only tools** (`get_case_summary`, `list_observations`, `get_observation`). The case is fixed by the backend; the model cannot name another case, and nothing is written.
- It must return JSON in a fixed shape (headline, findings, guidance, uncertainty). Every finding must cite ids of real sightings.
- A guard rejects: unknown ids, words that decide or accuse (stolen, thief, suspect, definitely, ...), and any coordinate that is not a stored sighting. One repair try, then fallback.
- **Fallback**: with no key, an outage, or rejected output, the endpoint returns a fixed-wording explanation with `source: "fallback"` and the reason. The `facts` counts always come from plain code, never the model.
- Data sent to the provider: sighting id, time, coordinates, accuracy, status, flags. Never email, IMEI, nickname or model.
- Set `MODEL_API_KEY` in `.env` (never in chat or git). Standard tier only. If the API rejects `response_format`, set `MODEL_STRUCTURED_OUTPUT=false`.
- Not yet verified against the live API (the cloud workspace cannot reach it). Run the live check on your laptop.

## Slice 7 (done): companion-app endpoints and Bluetooth reports

For the Android app (not built yet). Everything below is tested with a fake finder; no real Bluetooth has been exercised.

- `POST /companion/devices/{id}/challenge`: the phone asks for the ownership code and shows it on its own screen; the owner types it on the website. Proof channel is `companion_app`. Works with `DEMO_MODE` off.
- `POST /companion/devices/{id}/enroll`: after verification, returns the phone's `beacon_secret` (32 bytes, base64url). Stored encrypted. Asking again returns the same secret.
- **Rotating ID** (`app/beacon.py`): every 15 minutes the phone broadcasts `HMAC-SHA256(secret, "tracelink-beacon:" + window)[:8]` (hex), `window = unix_time // 900`. A fixed test vector pins the formula for the Android code.
- `POST /reports`: any signed-in finder says "I heard beacon X here, at this time" (`beacon_id`, `observed_at`, `lat`, `lon`, `accuracy_m`, `nonce`). The server matches it only against devices with an **active case**, adds 50 m for Bluetooth range, and runs the same evidence rules. The sighting is stored with `source: "ble"`. The reply is always `202 {"status":"received"}`, so finders cannot learn who owns a beacon or whether a case exists. 120 reports per hour per account.
- A new table `finder_reports` records which account reported (abuse handling only). New tables `beacon_keys` and `finder_reports` need no migration.
- Limits: the app signs in with the same account, so the code proves "account plus the phone's screen", not hardware attestation. A finder can lie about its own GPS position; the rules catch impossible jumps but not a consistent lie. Reports are not yet signed per device.

Documentation of technologies, patterns and data structures: `../docs/TECHNICAL_DECISIONS.md`.

## Run

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the secrets; set DEMO_MODE=true for demos
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # a good random secret
uvicorn app.main:app --reload
# API docs: http://localhost:8000/docs
```

## Test

```bash
python3 -m pytest -q        # uses an in-memory database, needs no setup
```

## Security notes for this slice

- `JWT_SECRET` has no default; the app will not start without it.
- Tokens are pinned to HS256, so unsigned (`alg: none`) or re-signed tokens are rejected (tested).
- Unknown email and wrong password return the same 401 response and take similar time.
- Registration returns 409 for a taken email, which reveals that an account exists. Accepted for the prototype; a real product would use email verification.

## Known limitations (planned)

- Losing `IMEI_ENCRYPTION_KEY` makes stored IMEIs unreadable; changing `IMEI_HMAC_KEY` breaks duplicate detection for existing rows. Back both up.
- No rate limiting yet (backlog item 11); login can be brute-forced until it is added.
- Tables are created at startup, not by migrations.
- No token revocation or refresh; logging out only discards the token on the client.

## Slice 8 (done): login lockout, audit trail, demo data

- **Login lockout:** 5 failed logins for an email in 15 minutes lock that email for the rest of the window (HTTP 429, `Retry-After: 900`), even for the right password. Unknown emails are counted the same way, so the response never reveals which emails exist. A successful login resets the count. Trade-off: someone can lock a known email out for 15 minutes; that is accepted over allowing unlimited guessing. In-memory, per process.
- **Audit trail:** `GET /audit` returns your own recent actions (registered, login, login_failed, device_added, device_deleted, code_requested, ownership_verified, beacon_enrolled, case_opened/recovered/closed, demo_sightings_added, sighting_received, explanation_requested). It stores ids and short labels only: never passwords, codes, IMEIs, secrets or coordinates (tested). New table `audit_events`; no migration needed.
- **Demo data:** `python seed_demo.py` (with `DEMO_MODE=true`) creates `demo@example.com` / `demo-password-2026` with a verified phone, an open case with simulated sightings, and a second unverified phone. Safe to run again.

## Frontend

See `../frontend/README.md`. Start this API with `DEMO_MODE=true`, then `npm run dev` in `frontend/`.
