# Data schema

Seven tables, defined in `src/models.py` (SQLModel). SQLite in development
(`data/handover.db`); nothing in the schema is SQLite-specific.

Conventions: all ids are strings; all timestamps are ISO-8601 datetimes; fields
marked *JSON list* hold a JSON-encoded array in a text column, which keeps the
audit rows portable across engines without a migration.

---

## `client`

One row per person, per discharge episode.

| Field | Type | Notes |
|---|---|---|
| `client_id` | str, PK | Stable identifier, e.g. `C001` |
| `pseudonym` | str | Display name. Never a real name in this system |
| `episode_id` | str | The admission this discharge closes |
| `discharge_date` | datetime | Anchor for consent expiry and action due dates |

Pseudonymisation is at the data layer, not the presentation layer. There is no
field anywhere in the schema for a legal name, so no rendering bug can leak one.

---

## `sessionsummary`

One row per clinical session note.

| Field | Type | Notes |
|---|---|---|
| `session_id` | str, PK | |
| `client_id` | str, FK → `client` | |
| `author_role` | str | Role that wrote the note |
| `date` | datetime | Briefs use the most recent three sessions |
| `text` | str | Free text as written on the ward |
| `source_span_ids` | str (JSON list) | Spans derived from this note |

`text` is stored verbatim, unredacted. Redaction is a *view* concern: the record
of what was said must stay intact, because consent can be granted later and a
destructively redacted note could not then be disclosed.

---

## `sensitivitytag`

One row per detected sensitive span. Produced by the tagger, consumed by the
policy engine.

| Field | Type | Notes |
|---|---|---|
| `span_id` | str, PK | blake2b digest of (session, index, category) — deterministic |
| `session_id` | str, FK → `sessionsummary` | |
| `category` | str | One of the eight `SensitivityCategory` values |
| `confidence` | float | 0.0–1.0. Below 0.70 the engine denies |
| `is_safety_relevant` | bool | Triggers the escalation carve-out |
| `tagger_version` | str | Which pattern table produced this |

A sentence matching two categories produces two rows. Consent is granted per
category, so a sentence about lithium levels during a relapse must be withheld
if *either* category is withheld.

`tagger_version` is on every row because retagging changes disclosure decisions.
Without it, an audit trail cannot answer "would this have been disclosed under
the rules in force at the time".

Span ids are content-derived rather than random so that eval runs, audit records
and provenance links agree across machines and reruns.

---

## `consentrecord`

The authorisation table. One row per (client, category, role, purpose) grant.

| Field | Type | Notes |
|---|---|---|
| `consent_id` | str, PK | |
| `client_id` | str, FK → `client` | |
| `category` | str | Sensitivity category this grant covers |
| `recipient_role` | str | Who may see it |
| `purpose` | str | `handover`, `audit`, or `research` |
| `granted` | bool | False records an explicit refusal |
| `granted_at` | datetime | |
| `expires_at` | datetime, nullable | Null means no expiry |
| `revoked_at` | datetime, nullable | Null means not revoked |

Consent is granted along three axes at once. A grant to the psychiatrist does
not authorise the counsellor; a grant for research does not authorise handover.

**Revocation is soft.** `revoked_at` is set; the row stays. Hard-deleting would
destroy the evidence that consent once existed and was withdrawn, which is
exactly what an audit needs to see. The engine treats a revoked record as denied
from `revoked_at` onward, so revocation is retroactive for all future briefs and
never rewrites past ones.

**`granted = false` is not the same as no row at all.** A false row means the
client was asked and declined. No row means nobody asked. Both deny, and the
explainer reports them differently, because one is a boundary and the other is
an administrative gap.

---

## `clientgoal`

| Field | Type | Notes |
|---|---|---|
| `goal_id` | str, PK | |
| `client_id` | str, FK → `client` | |
| `text` | str | Goal in the client's own framing where possible |
| `status` | str | `active`, `completed`, `on_hold` |
| `priority` | str | `HIGH`, `MEDIUM`, `LOW` |
| `review_date` | datetime | |

Goals are not consent-filtered. They are the client's own stated intentions,
already shared with the care team by definition.

---

## `pendingaction`

Operational continuity. The table that must survive consent filtering intact.

| Field | Type | Notes |
|---|---|---|
| `action_id` | str, PK | |
| `client_id` | str, FK → `client` | |
| `description` | str | |
| `owner_role` | str | Role responsible |
| `owner_id` | str | Named individual |
| `due_date` | datetime | |
| `priority` | str | `HIGH`, `MEDIUM`, `LOW` |
| `status` | str | `open`, `in_progress`, `completed`, `cancelled` |
| `escalation_level` | int | 0–3, recomputed at read time |

`owner_role` and `owner_id` are both required in practice: a role can cover a
vacancy, a person can be on leave, and an action with neither is a wish rather
than a task. `action_retention_rate` scores owner-plus-due-date presence
directly.

`escalation_level` is stored but always recomputed from `due_date` on read. A
stored level goes stale overnight, and a handover showing yesterday's urgency is
a handover that under-reports.

---

## `disclosureaudit`

Append-only record of what was actually shown to whom.

| Field | Type | Notes |
|---|---|---|
| `event_id` | str, PK | |
| `brief_id` | str | The brief this describes |
| `recipient_role` | str | |
| `categories_shown` | str (JSON list) | |
| `categories_withheld` | str (JSON list) | |
| `override_flag` | bool | A human overrode a policy decision |
| `justification` | str | Required when `override_flag` is true |
| `timestamp` | datetime | |

Withheld categories are recorded alongside shown ones. An audit log that only
records disclosures cannot answer the question a client is most likely to ask:
*was my boundary respected?*

`override_flag` and `justification` exist because a break-glass path will be
needed in any real deployment. It is not implemented in the prototype — the
schema reserves space for it so that adding it later does not require a
migration to the audit table, which is the one table that should never be
rewritten.

---

## Relationships

```
client (1) ──< sessionsummary (1) ──< sensitivitytag
   │
   ├──< consentrecord
   ├──< clientgoal
   └──< pendingaction

disclosureaudit — no FK; keyed by brief_id, retained independently
```

`disclosureaudit` deliberately has no foreign keys. It must outlive the records
it describes: if a client exercises erasure over their clinical data, the
evidence that a disclosure decision was made and on what basis should survive
the deletion of the content it concerned.
