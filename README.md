# url-shortener

A URL shortener built as a system-design study: start from a single client–server–DB
service and evolve it toward a distributed, horizontally scalable system, using load
tests to find the capacity "knee" at each stage.

---

## 1. Overview

The system is modeled as **two logical services** that share one data store:

| Service | Responsibility | Traffic profile |
| --- | --- | --- |
| `url-service` | Create short URLs from original URLs (writes) | Low volume |
| `redirect-service` | Resolve a short code back to its original URL (reads) | High volume |

They are split conceptually so **reads can scale independently of writes** — URL
shortening is a read-heavy workload, so redirects will eventually run more replicas /
caching than creation. Today they live in one FastAPI app; splitting them into separate
deployables is part of the scaling roadmap (§8).

---

## 2. Architecture

Each request flows through clean layers so persistence and business rules can evolve
independently:

```
route  →  service  →  repository  →  DB
(HTTP)    (business    (SQL only)     (Postgres)
           logic)
```

- **Routes** — HTTP concerns only: parse request, translate exceptions → HTTP status.
- **Services** — business rules (collision handling, expiry semantics, alias rules).
- **Repositories** — the only place that talks SQL; swappable without touching logic.
- **Strategies** — short-code generation is behind a `UrlCreationStrategy` interface so
  the algorithm (hashing today, counter-based later) can be swapped without service changes.

Stack: **FastAPI + SQLAlchemy + Alembic + Postgres**, packaged with `uv`.

---

## 3. API

| Method | Path | Purpose | Status |
| --- | --- | --- | --- |
| `POST` | `/urls` | Create a short URL | Implemented |
| `GET` | `/{shortCode}` | Redirect to the original URL (302) | Implemented |
| `GET` | `/healthz` | Liveness (process up, no DB) | Planned |
| `GET` | `/readyz` | Readiness (checks DB, e.g. `SELECT 1`) | Planned |

**Routing decision.** `GET /{shortCode}` is a greedy catch-all — Starlette matches routes
in **registration order, first match wins** (it does *not* prefer literal paths over
parameterized ones). So the redirect router must be registered **last**, and all
non-redirect routes (creation, health) are namespaced/registered before it so they can
never fall into the catch-all. Health endpoints are split into **liveness** (cheap, no DB —
decides restarts) and **readiness** (hits the DB — decides whether to route traffic; fails
loudly when the connection pool is exhausted, which is a useful load-test signal).

---

## 4. Short-code generation

Current strategy: **SHA-256 hash → base62 encode → take the first N characters**.

- **Why base62?** Compact representation over `[a-z A-Z 0-9]`. It excludes `+` and `/`
  (from base64) because `/` is a path separator and `+` decodes to a space in query strings.
- **Choosing N.** Target ≈ 1B (10⁹) URLs. base62 gives 62 symbols, so we need `62^N > 10^9`:
  - `62^5 ≈ 916M` (just under 1B)
  - `62^6 ≈ 56.8B` → **N = 6**, comfortable headroom.

The strategy is **deterministic**: the same original URL always produces the same code
(for a given probe attempt — see §5). This lets us compute the code first, then check the
DB, rather than reading the DB to invent a unique code.

---

## 5. Collision handling *(implemented)*

Truncating a 256-bit hash to 6 base62 chars means two **different** URLs can map to the
same code. By the birthday bound, collisions become likely around `√(56.8B) ≈ 240k` URLs —
so this must be handled, and it surfaces under load, not in a quick manual test.

On a code hit we compare `original_url` and take one of three branches:

```
code = create_short_code(original_url, attempt)
mapping = find_by_short_code(code)

mapping is None                       -> free slot: insert, return code
mapping.original_url == original_url  -> ours: reuse code (see expiry rules, §6)
mapping.original_url != original_url  -> collision: attempt += 1, re-hash and retry
```

**Deterministic probing.** The collision branch re-hashes with an incremented salt:
`create_short_code(url, attempt)` hashes `f"{url}#{attempt}"`. The `#` delimiter keeps the
`(url, attempt) → string` mapping unambiguous.

> **Invariant:** the probe sequence depends **only** on `(original_url, attempt)`, never on
> DB state. This is what makes probing safe: a later re-submit of the same URL replays the
> identical sequence — `hash(url,0)`, `hash(url,1)`, … — and re-lands on the same code, so
> deduplication survives collisions.

The "free slot" insert is done atomically via the upsert in §7. **Still planned:** an attempt
cap (`attempt > MAX_PROBE_ATTEMPTS` → error) so a pathological input can't loop forever.

---

## 6. Product decisions

### Original URL (deterministic code)

```
If a code hit is the SAME original_url:
    reuse the same code (never mint a new one)
    LAST-WRITE-WINS on expiration:
        overwrite expiration_time with the request's value
        (extend, shorten, dated→null, or null→dated — all honored)

If a code hit is a DIFFERENT original_url (collision):
    probe to a new code (regardless of the other mapping's expiry)

If no mapping exists:
    create it; expiration_time = request value or None (never expires)
```

- **Absent == null == "never expires".** The request field is `datetime | None`, so an
  omitted field and an explicit `null` are indistinguishable. We treat both as "no
  expiration," consistent with creation. Consequence: a re-submit that omits
  `expirationTime` **clears** any existing expiration (makes the URL immortal). This is
  intentional last-write-wins; if we ever want "omit = leave unchanged," we'd distinguish
  absent from null via `model_fields_set`.
- **Expired hash codes are NOT reclaimable by a different URL.** A different URL always
  probes past an occupied code, even if that code's mapping is expired. Reclaiming would
  make code assignment depend on *who happened to be expired when* — i.e. on timing/DB
  state — which breaks the determinism invariant (§5). Expired rows are therefore garbage
  that accumulates and slowly raises collision probability → a GC job is on the roadmap (§8).

### Alias (user-chosen code)

```
If alias is free:
    create mapping with short_code = alias

If alias is held by a DIFFERENT url and still ACTIVE:
    reject with 409 Conflict

If alias is held by the SAME url (owner re-request):
    keep the alias; last-write-wins on expiration (same rule as hash codes)

If alias is held by ANY url but EXPIRED:
    reclaim it for the new original_url (keep the alias string)
    set expiration from the request
```

- **Expired aliases ARE reclaimable by a different URL** — the opposite of hash codes.
  Aliases are scarce, human-chosen strings (`promo2024`); it's desirable that an expired one
  can be grabbed by someone else. Determinism doesn't apply because the code isn't derived
  from the URL.
- **Same-owner re-request is allowed (reconciled).** An active alias returns 409 only for a
  *different* URL; the owning URL may re-request to extend/update its expiration, matching the
  hash-code path. This resolves the earlier inconsistency where owners were wrongly 409'd.
- **Shared namespace with hash codes.** Aliases are stored in the same `short_code` column as
  hash codes, so an alias can collide with an existing hash code (and vice versa). Availability
  is therefore keyed on `short_code`, not `alias` — the alias path reads back the occupant via
  `find_by_short_code`, so a hash code occupying the string correctly blocks the alias.

### Redirects

- **302 (temporary), not 301 (permanent).** 301 is cached by browsers, which would prevent
  changing/expiring targets and would hide click traffic from the server. 302 keeps every
  hit flowing through us — needed for expiry enforcement and future analytics.

### Timezones *(planned enforcement)*

- Rule: **everything is UTC and timezone-aware.** The DB columns are `timezone=True`, but
  request datetimes may arrive naive. A naive-vs-aware `!=`/`==` doesn't crash but always
  reads as "unequal," and `<`/`>` would raise — both are latent expiry bugs. Planned: a
  Pydantic validator at the edge that rejects or coerces naive input.

---

## 7. Concurrency: read-then-write race *(implemented)*

A naive "find then insert" is two statements, so two concurrent creates of the same new URL
can both see "empty," both insert, and the loser hits the `unique(short_code)` constraint →
unhandled 500. This is a **data-layer** race and is *not* solved by async; it needs atomicity
at the DB.

Fix: `find_and_store_short_code` does an **atomic upsert then reads back the occupant**:

```
INSERT ... ON CONFLICT (short_code) DO NOTHING     -- one atomic statement
SELECT ... WHERE short_code = :code                -- read back whoever now holds it
```

`DO NOTHING` swallows the conflict (no exception), and the read-back returns the row that
occupies the code — whether we inserted it or someone else did. The service then compares
`original_url`: if it's ours, reuse (and last-write-wins on expiration); if it's a different
URL, it's a collision and the loop advances `attempt` and probes the next code. No
`IntegrityError` handling is needed because `DO NOTHING` never raises.

- **Why `DO NOTHING` + read-back, not `DO UPDATE ... RETURNING`?** `DO UPDATE` writes the row
  on *every* conflict (MVCC dead tuples + a row lock), turning every duplicate create into a
  write. An indexed point-lookup read-back is cheaper than that write amplification. `DO NOTHING`
  also returns nothing on conflict, which is why a separate read is required to get the row.
- **Optimization (not yet applied):** add `RETURNING` so the insert path returns the row in
  one round trip, falling back to the read only on conflict.

---

## 8. Design deep-dives & roadmap

### Deterministic vs non-deterministic codes

- **Deterministic (hash + base62, current):** compute code → check DB → done. Same URL
  always yields the same code, giving free dedup. Cost: must handle collisions (§5).
- **Non-deterministic (random):** either (a) generate → check for collision → store, which
  can yield *multiple* codes per URL, or (b) read-by-URL first to dedup, which is an extra
  read on every create. Rejected for the read cost / duplication.

### The design triangle

Short-code schemes trade off three properties — you get two easily and work for the third:

| Scheme | Same URL → same code | Collision-free | Simplicity |
| --- | --- | --- | --- |
| Truncated hash *(current)* | ✅ | ❌ (needs probing) | Medium |
| Counter / sequence + base62 | ❌ (needs a URL→code index to dedup) | ✅ | High |

Counter-based IDs are the likely next step for scale (no probing, no collision math), at the
cost of adding a reverse index on `original_url` to keep dedup.

### Roadmap

- [x] Atomic-upsert race fix (§7)
- [ ] Attempt cap on the probe loop (§5)
- [ ] Health endpoints + explicit connection-pool config
- [ ] Timezone validator (UTC-only at the edge)
- [ ] GC job for expired rows
- [ ] Redis cache in front of redirects (read-heavy path)
- [ ] Split `url-service` / `redirect-service` into separate deployables
- [ ] Load testing (open-model, e.g. k6) to find the capacity knee at each stage
```
