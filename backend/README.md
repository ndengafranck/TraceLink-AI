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
