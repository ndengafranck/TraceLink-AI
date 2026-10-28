# TraceLink AI: technical decisions

What is built, why it was chosen, and what was rejected. Everything in sections 1 to 4 exists in the code today (backend slices 1 to 4). Anything planned is marked **Planned** so nothing is claimed that is not built.

Contents: 1. Architecture at a glance, 2. Technologies, 3. Design patterns, 4. Data structures and data model, 5. Security decisions, 6. Testing approach, 7. Limits and what is not built.

---

## 1. Architecture at a glance

One FastAPI service ("modular monolith"), one PostgreSQL database. No queues, no microservices.

```
Client (React, planned)
        |  HTTPS + JSON, Bearer token
        v
 app/main.py            creates the app, error handler, wires routers
   |-- routers/auth.py        register, login, /me
   |-- routers/devices.py     register / list / read / delete devices
   |-- routers/ownership.py   challenge + verify (ownership proof)
   |-- routers/cases.py       lost-device cases and their state machine
   |-- routers/observations.py  sightings: store, list, simulate
   |
   |-- evidence.py      the evidence engine (pure rules, no database, no AI)
   |-- simulator.py     labelled synthetic scenarios for demos and tests
   |
   |-- deps.py          get_current_user  (who is calling?)
   |-- schemas.py       what goes in and out of the API (Pydantic)
   |-- models.py        database tables (SQLAlchemy)
   |-- security.py      password hashing, tokens
   |-- crypto.py        IMEI encryption, hashes, Luhn check
   |-- config.py        settings from environment variables
   |-- db.py            engine and session
        |
        v
   PostgreSQL (SQLite in tests)
```

Request path example, `POST /devices`: token is checked (`deps.py`) → body is validated (`schemas.py`) → IMEI is encrypted and fingerprinted (`crypto.py`) → row is saved (`models.py`) → response shows only the masked IMEI.

**Why a modular monolith:** one developer, ten days. Splitting into services adds deployment, networking and debugging work with no benefit at this size. The folders are already separated by responsibility, so splitting later would be possible.

---

## 2. Technologies and why

| Technology | Used for | Why this one | Rejected alternative |
| --- | --- | --- | --- |
| **Python 3.13** | Backend language | You already know it; strongest library support for security and AI work. | Node.js: also known to you, but I judged Python's crypto and testing libraries more direct for this task. |
| **FastAPI** | Web framework | Type hints become validation and automatic API docs at `/docs`. Dependency injection is built in, which makes login checks and tests clean. You already know it. | Django: heavier, and its admin/templates add little to an API. Flask: needs extra libraries for validation and docs. |
| **Pydantic v2** | Validating and shaping data in and out | Rejects bad input before our code runs (for example an IMEI that fails its check digit). Separate In/Out models control exactly what leaves the API. | Hand-written checks: more code, easier to forget a case. |
| **pydantic-settings** | Configuration | Reads secrets from environment variables and fails at start-up if one is missing. | Hard-coded config: risks committing secrets. |
| **SQLAlchemy 2** | Talking to the database (ORM) | Parameterized queries by default (protects against SQL injection); same code runs on PostgreSQL and SQLite. | Raw SQL strings: injection risk and repetition. |
| **PostgreSQL** | Main database | Real constraints and transactions; what you would deploy. Matches your SQL experience. | SQLite in production: no concurrent-write strength. (SQLite is used only in tests, for speed.) |
| **psycopg 3** | PostgreSQL driver | Current, maintained driver that SQLAlchemy 2 supports. | psycopg2: older. |
| **argon2-cffi** | Password hashing | Argon2id is a memory-hard algorithm designed for passwords; slows down guessing on stolen databases. | Plain SHA-256: far too fast to guess. bcrypt: acceptable, but Argon2 is the newer recommendation. |
| **PyJWT** | Login tokens | Signed tokens mean the server needs no session table. Pinned to HS256 so "unsigned" tokens are refused. | Server-side sessions: need storage and cleanup; can be revoked, which JWTs cannot (see section 7). |
| **cryptography (Fernet)** | Encrypting IMEIs | Fernet is a ready-made recipe (AES with integrity check), so we avoid assembling encryption ourselves. | Own AES code: easy to get wrong. |
| **hmac, hashlib, secrets** (standard library) | Keyed hashes, random codes | Audited, no extra dependency. `secrets` is the cryptographically secure random source; `random` is not. | `random` module: predictable. |
| **uvicorn** | Runs the app | Standard server for FastAPI. | - |
| **pytest + FastAPI TestClient (httpx)** | Tests | Short tests, fixtures, and the ability to swap the database per test. | unittest: more boilerplate. |

**Planned, not built yet:** React + TypeScript frontend (your existing skills); Meta Model API for the AI explanation (access from Cameroon still unconfirmed); Kotlin for the optional Android BLE prototype.

---

## 3. Design patterns and why

Each pattern is named, shown where it lives, and given a reason. Patterns I did **not** use are listed too, so the document does not oversell.

### 3.1 Layered / modular structure
**Where:** the folders in section 1. Routers handle HTTP, schemas handle data shape, models handle storage, `crypto`/`security` handle secrets.
**Why:** a change to hashing touches one file; a reader can find things quickly; it is what examiners expect to see explained.

### 3.2 Dependency Injection (DI)
**Where:** `Depends(get_db)` and `Depends(get_current_user)` in every router; `get_current_user` in `deps.py`.
**What it means:** a function says what it needs ("a database session", "the logged-in user") and the framework supplies it.
**Why:** (1) login checking is written once and reused on every protected route, so one cannot be forgotten by copy-paste; (2) tests replace the real database with an in-memory one without changing application code (`app.dependency_overrides` in `tests/conftest.py`).

### 3.3 Data Transfer Objects (DTOs) via Pydantic schemas
**Where:** `schemas.py`: `DeviceIn` (what a client may send) and `DeviceOut` (what we reveal).
**Why:** the database row holds the encrypted IMEI; the API model has no field for it, only `imei_masked`. A secret cannot leak by accident because the output type has nowhere to put it.

### 3.4 Owner-scoped data access (authorization at the query)
**Where:** `get_owned()` in `routers/devices.py`; reused by `ownership.py`.
**What it means:** the query is `WHERE id = ? AND owner_id = ?`. It never loads another user's row and then checks afterwards.
**Why:** this stops "IDOR" attacks (user A changes an id in the URL to read user B's device). Because the check is inside one helper used by every route, a new route cannot skip it without being obvious. Missing and foreign devices both return 404, so ids cannot be probed.

### 3.5 State machine
**Where:** `Device.status` (`unverified` → `verified`); `OwnershipProof` lifecycle (open → consumed or verified, with `expires_at`, `attempts`); `Case.state` with the `ALLOWED_TRANSITIONS` table in `routers/cases.py` (`open` → `evidence_received` → `recovered` → `closed`).
**Why:** the allowed transitions are few and explicit, so tests can cover each one (expired, locked, replaced, repeated). The same idea will drive the lost-device case states later.
**Honest note:** statuses are plain strings for now. A database CHECK constraint or Enum would stop invalid values; this is a planned improvement.

### 3.5b Functional core, imperative shell (the evidence engine)
**Where:** `evidence.py` is the core: `evaluate()` takes plain values and returns a `Verdict`. It never touches the database, the clock or the network. `routers/observations.py` is the shell: it loads stored sightings, calls `evaluate()`, then saves or rejects.
**Why:** the rules for judging a sighting are the most important logic in the product, and the AI will only explain what they decide. Because `evaluate()` is a pure function, 15 tests exercise every rule in milliseconds with fixed times, and the same input always gives the same answer. That is what lets us say the AI does not decide anything.

### 3.5c Simulator as a labelled test double
**Where:** `simulator.py` produces named scenarios (`fresh_cluster`, `stale`, `conflicting`, `low_accuracy`) that go through exactly the same validation as any real input.
**Why:** judges and tests get repeatable edge cases without hardware. Every stored sighting carries `source = "simulated"`, so simulated data cannot be presented as a real detection.

### 3.5d Database as the last line of defence
**Where:** the partial unique index `uq_one_active_case_per_device` and the unique constraint `uq_observation_case_nonce` in `models.py`.
**Why:** the code checks "is there already an active case?" first, but two requests can arrive at the same instant and both pass that check. The database rule makes the second one fail anyway, and the router turns that failure into a clean 409.

### 3.6 Configuration object + Singleton via `lru_cache`
**Where:** `config.py` (`Settings`, `get_settings()`).
**Why:** settings are read once from the environment and shared. Secrets have no default value, so a missing secret stops the app at start-up instead of running insecurely ("fail closed"). The 12-factor rule: config lives in the environment, not in code.

### 3.7 Session-per-request and Unit of Work
**Where:** `db.py` (`get_db`), `db.commit()` / `db.rollback()` in routers.
**Why:** each request gets its own database session, closed afterwards. A change is saved in one commit, or rolled back if it fails (for example, the IMEI-duplicate race in `register_device`).

### 3.8 Defense in depth for IMEIs
**Where:** `crypto.py`, `Device` model.
**What:** three layers: encrypted copy (Fernet), keyed fingerprint (HMAC) for duplicate checks, and a stored last-4 for display. No layer alone gives the full IMEI to someone with only the database.
**Why:** one stolen database dump, without the keys, reveals nothing usable. See section 4.3.

### 3.9 Uniform failure responses (anti-enumeration)
**Where:** login (same 401 for unknown email and wrong password, plus a dummy hash so timing is similar); ownership verify (one message for wrong, expired, locked and missing code); device 404s; the 422 handler in `main.py`.
**Why:** an attacker learns nothing from differences between failures.

### 3.10 Idempotent operation
**Where:** `POST .../ownership/verify` on an already verified device returns 200 again.
**Why:** a retry after a network failure should not produce an error or a second change.

### 3.11 Test patterns
**Where:** `tests/`: fixtures (`client`, `auth_header`, `db_session`), dependency override, `monkeypatch` to fix "random" codes (`fixed_codes`) or switch demo mode off.
**Why:** each test starts with a fresh database, so tests cannot affect one another; fixing random values makes security tests deterministic instead of flaky.

### 3.12 Patterns deliberately not used
- **Repository pattern:** routers use the SQLAlchemy session directly. With three tables, an extra layer would add files without adding clarity. If queries grow complex, add it then.
- **Microservices / message queue:** no demonstrated need (your brief).
- **Strategy / Adapter for delivery channels and AI providers:** **Planned.** `OwnershipProof.channel` is the hook for delivery channels, and the AI module will sit behind an interface so the model host can change. Not built yet, so not claimed.

---

## 4. Data structures and why

### 4.1 Database tables (relational model)

```
users 1 ───< devices 1 ───< ownership_proofs
                    1 ───< cases 1 ───< observations
```

| Table | Columns that matter | Why |
| --- | --- | --- |
| `users` | `id`, `email` (unique, lower-case), `password_hash`, `created_at` | Unique index on email stops duplicates at the database level, even if two signups arrive at the same moment. |
| `devices` | `id`, `owner_id` → users, `nickname`, `model`, `imei_encrypted`, `imei_hmac` (unique), `imei_last4`, `status`, `created_at` | `imei_hmac` unique = one IMEI, one registration, enforced by the database. `owner_id` is indexed because every query filters on it. |
| `ownership_proofs` | `id`, `device_id` → devices, `code_digest`, `channel`, `attempts`, `created_at`, `expires_at`, `consumed_at`, `verified_at` | One row per challenge keeps an audit trail. Timestamps record what happened; `attempts` enforces the lock. |

| `cases` | `id`, `device_id` → devices, `opened_by` → users, `state`, `opened_at`, `closed_at` | A partial unique index allows only one case in `open` or `evidence_received` per device, so a device cannot have two live cases even under a race. |
| `observations` | `id`, `case_id` → cases, `source`, `observed_at`, `received_at`, `lat`, `lon`, `accuracy_m`, `nonce`, `validation_status`, `flags` (JSON list) | `(case_id, nonce)` is unique: the same report id cannot be stored twice (replay protection). `source` says `simulated` or, later, `ble`. Rejected sightings are never stored (data minimisation). `flags` is a list because one sighting can have several problems. |

**UUID text ids** (not 1, 2, 3...): ids in URLs cannot be guessed or counted. This helps against probing, but it is not the authorization itself; `get_owned()` is.

**Indexes** (B-tree, created by `index=True` or `unique=True`): looking up by email, by `owner_id` or by `imei_hmac` takes about O(log n) instead of scanning every row.

**Foreign keys:** a proof cannot point at a device that does not exist. This is why `delete_device` removes proofs first (tested on SQLite and checked on PostgreSQL).

### 4.2 In-memory structures

| Structure | Where | Why |
| --- | --- | --- |
| **dict** `{device_id: channel}` | `verified_channels()` in `devices.py` | One query with `IN (...)` fetches all proof channels, then each device is looked up in O(1). Avoids the "N+1 query" problem of one query per device in a list. |
| **list** of rows | `list_my_devices` | Needed in order (newest first) and iterated twice (ids, then output). |
| **Pydantic models** | `schemas.py` | Typed records that validate themselves; better than loose dicts, which hide typos. |
| **Constants** (`CODE_TTL`, `MAX_ATTEMPTS`, `MAX_CHALLENGES_PER_HOUR`; `STALE_AFTER`, `MAX_AGE`, `MAX_SPEED_KMH`, `MIN_JUMP_KM`...) | `ownership.py`, `evidence.py` | Named limits in one place, so tests and reviewers can see the rules and change one without hunting. |
| **Frozen dataclasses** `Point`, `Verdict` | `evidence.py` | Small immutable records: the engine cannot accidentally change its inputs, and a verdict is a fixed fact once made. Lighter than a Pydantic model because no outside data is parsed here. |
| **dict of sets** `ALLOWED_TRANSITIONS` | `routers/cases.py` | The whole case lifecycle as data: `{"open": {"recovered","closed"}, ...}`. A move is legal if the target is in the set (O(1)); adding a state means editing one table, not several `if` chains. |
| **tuple** of flags in `Verdict` | `evidence.py` | Immutable and ordered; converted to a list only when stored as JSON. |
| **sorted-by-time neighbours** (`before`, `after`) | `evidence.py` | Each new sighting is compared only with the closest earlier and later sightings, not all of them. Speed between those two is enough to catch an impossible jump. At most 200 sightings per case, so a simple scan is fast and clear; a heap or index would add complexity with no gain. |
| **JWT claims dict** `{sub, iat, exp}` | `security.py` | Minimal: only who (`sub`), when issued, and when it expires. No personal data in the token. |
| **Strings for status/channel** | models | Simple; see the note in 3.5. |

### 4.3 Special values and algorithms

- **Luhn check digit** (`is_valid_imei`): walks the 15 digits from the right, doubling every second digit; O(n) with n = 15. Catches typos before anything is stored. It proves the number is well-formed, **not** that the phone exists or belongs to anyone.
- **Fernet token** (encrypted IMEI): one string that bundles the encrypted data, a timestamp and an integrity check, so tampering is detected on decryption.
- **HMAC-SHA256 fingerprint** (64 hex characters): a one-way value made with a secret key. A plain hash would be unsafe because there are only about 10^14 possible IMEIs, which an attacker could try one by one; without our secret key they cannot.
- **Haversine distance** (`haversine_km`): the great-circle distance between two latitude/longitude points on a sphere (Earth radius 6371 km). Accurate to well under 1% for our purposes, which is far better than the sighting accuracy itself. Test: Douala to Yaounde is about 194 km.
- **Implausible movement rule:** speed = distance / time between two sightings. Flagged only if the jump is over 1 km **and** the speed is over 250 km/h. The 1 km floor exists because GPS noise alone moves a point by 100 m or more (found while testing: two scenarios in one case produced false flags without it).
- **Ownership code:** 6 digits from `secrets.randbelow` (1,000,000 possibilities). That is small on purpose, because a person must type it, so safety comes from the limits: 10-minute expiry, 5 attempts per code, 3 codes per device per hour, one active code at a time. Stored only as an HMAC bound to the device id, so a code for device A cannot verify device B.

---

## 5. Security decisions in this version

| Risk (from the threat model) | What the code does | Test |
| --- | --- | --- |
| Reading another user's device | Owner-scoped queries, 404 for foreign ids | `test_user_cannot_read_another_users_device`, others in `test_devices.py` |
| Database leak exposes IMEIs | Encrypted + keyed hash; masked in responses, errors and logs | `test_imei_is_not_stored_in_plain_text` |
| Weak password storage | Argon2id | `test_password_is_stored_hashed` |
| Forged or expired login tokens | HS256 pinned, expiry required | alg-none, wrong-secret, expired tests |
| Account probing | Same error for unknown email and wrong password | `test_wrong_password_and_unknown_email_look_identical` |
| Secrets in error responses | Custom 422 handler removes submitted values | echo tests in `test_auth.py`, `test_devices.py`, `test_ownership.py` |
| Guessing the ownership code | Expiry, attempt lock, request cap, single use | `test_ownership.py` (18 tests) |
| Replayed or repeated sighting reports | Unique `(case_id, nonce)`; near-copies rejected as duplicates | `test_replayed_report_is_rejected`, `test_duplicate_sighting_is_rejected` |
| Fake, future or ancient sightings | Engine rejects future times and anything over 7 days old; flags stale, low-accuracy and impossible movement | `tests/test_evidence.py` (15 tests) |
| Someone else's case or location data | Cases are reached only through the device owner; 404 otherwise | `tests/test_cases.py`, `test_other_users_cannot_read_or_add_sightings` |
| Flooding a case with sightings | Cap of 200 per case (429) | `test_per_case_limit` |
| Simulated check passing as real | Proof `channel` stored and returned as `verified_via`; code only issued when `DEMO_MODE=true` | `test_without_demo_mode_no_code_is_issued`, `test_challenge_then_verify_marks_device_verified` |

---

## 6. Testing approach

108 automated tests, all passing: 16 auth, 18 devices, 18 ownership, 13 cases, 15 evidence engine, 28 sightings and simulator. Each test runs on a fresh in-memory SQLite database. Key flows were also run once against a real PostgreSQL server, because foreign keys and time handling behave differently there. Tests cover the failure paths (wrong, expired, locked, forged, other user) as much as the success path, because security bugs live in the failure paths.

Run them: `cd backend && python3 -m pytest -q`.

---

## 7. Limits and what is not built

- **Ownership proof is simulated.** Nothing on the phone shows the code yet. In demo mode the API returns the code, and the result is labelled `demo`. A real check needs the Android companion app (or another channel). Decision pending with the project owner.
- **No rate limiting on login or registration yet** (backlog item 11). Login can be brute-forced until it exists.
- **Tokens cannot be revoked.** Logging out discards the token on the client only; it stays valid until it expires (30 minutes).
- **Registration reveals that an email exists** (409). Accepted for the prototype.
- **No migrations.** Tables are created at start-up; adding columns to an existing database needs Alembic. Slice 3 added a new table only, so existing databases keep working.
- **Status values are plain strings,** not database-enforced.
- **Sightings come only from the simulator.** There is no signed report from a real finder device, and no real BLE source. `source: "ble"` is refused until one exists.
- **The engine does not know when the phone was lost,** so it cannot judge a sighting against the loss time. Earlier sightings are treated as normal.
- **Location history has no retention job and no read audit log yet** (backlog item 11). Deleting a device deletes its cases and sightings; nothing else removes them.
- **Not started:** the AI module, frontend, audit log, retention job, Android BLE.
- **Key management:** losing `IMEI_ENCRYPTION_KEY` makes stored IMEIs unreadable; changing `IMEI_HMAC_KEY` breaks duplicate detection and existing ownership codes. Back both up.


## Slice 5: AI module

| Decision | Why |
|---|---|
| Provider interface (`ModelClient`) with an HTTP implementation | Tests use a scripted fake; the model can be swapped without touching logic. Strategy pattern. |
| Read-only tools, case fixed by the backend | The model gathers evidence itself (tool use) but cannot reach other cases or change data. |
| Pydantic output schema with `extra="forbid"` | Model output is untrusted; wrong shape is rejected, not repaired silently. |
| Deterministic guard (ids, forbidden words, coordinates) | Enforces "never invents locations, never accuses" in code, not only in the prompt. |
| One repair try, then fixed fallback | Bounded cost and latency; the product works with the AI off. |
| Facts counted in code | Numbers shown to the user never depend on the model. |
| Low reasoning effort | Short grounded explanations; lower cost. |

Limits: the guard blocks listed words, not every possible bad phrasing; the rate limiter is per process; the live API call is untested until run with a real key.


## Slice 7: companion endpoints and Bluetooth reports

| Decision | Why |
|---|---|
| Rotating ID = truncated HMAC of a per-device secret and a 15-minute window | Nobody but the owner and the server can link two broadcasts or predict the next ID, so the beacon is not a tracking tool. Both sides compute it from the same shared secret; no ID list is stored. |
| Match only devices with an active case | Phones that are not reported lost are never matched, so finders create no data about them. |
| Uniform `202 received` for every report | A finder cannot use the endpoint as an oracle for who owns a beacon. |
| +50 m on every Bluetooth sighting | Hearing a beacon means "within range", not "at the finder's exact GPS point". The ring on the chart stays honest. |
| Separate tables (`beacon_keys`, `finder_reports`) | Existing databases need no migration. |
| Phone requests the code, website verifies it | The code is shown on the device's own screen. Weakness stated in the README: same account, no hardware attestation. |
| Constant-work comparison over three windows | Absorbs clock skew without leaking which window matched. |
