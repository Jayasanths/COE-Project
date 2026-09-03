# Architecture

## The problem

A client is discharged from an acute psychiatric ward. Their care moves to a
community counsellor and a social worker who were not in the room for any of it.
What those clinicians receive is, in practice, whatever the ward had time to
write — often a copy-paste of the last few session notes.

Two failures follow, and they pull in opposite directions.

**Too much gets through.** Session notes contain forensic history, substance
use, sexual health, trauma. A client who disclosed a criminal conviction to a
psychiatrist in a locked ward did not thereby agree to it appearing in a
counsellor's inbox. Every unnecessary disclosure teaches the client that
disclosure is unsafe.

**Too little gets through.** Pending referrals lose their owner. Overdue
follow-ups vanish. The client arrives at their first community session and is
asked to recount the same history for the fourth time — which is the
experience the whole system is supposed to prevent.

Solving one naively worsens the other. Redact aggressively and the brief becomes
useless; copy everything and consent becomes meaningless.

## The shape of the answer

Separate the two concerns onto different tracks, and make absence visible.

```
  session notes
        │
        ▼
  ┌───────────┐   spans + confidence
  │  tagger   │──────────────────────┐
  └───────────┘                      │
                                     ▼
  consent records ──────────► ┌──────────────┐
                              │ policy engine│  deterministic, hand-written
                              └──────┬───────┘
                     permitted spans │ withheld categories
                                     │ escalation flags
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
             ┌────────────┐   ┌────────────┐   ┌────────────┐
             │ conflicts  │   │ generator  │   │ explainer  │
             │ detector   │   │ (4 tiers)  │   │            │
             └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
                   └────────────────┼────────────────┘
                                    ▼
  pending actions ──► tracker ──► handover brief
                      (never consent-filtered)
```

Two things about this diagram matter more than the boxes.

**Filtering happens before generation.** The summariser never receives content
the client did not agree to share. The alternative — generate, then redact —
requires trusting a model to forget something it has already read, and there is
no way to verify that it did.

**Actions bypass the filter entirely.** "Refer to housing support, owner social
worker, due 14 March" carries no clinical disclosure. Routing it through consent
filtering would mean a client withholding their financial history also loses
their housing referral: the original harm, reintroduced through a side door.

## Design decisions

### Rule-based consent engine, not an LLM

The engine is 180 lines of hand-written Python with no imports beyond the
standard library. It cannot call a model, reach the network, or consult a random
source. `AGENTS.md` forbids agents from modifying it.

- **Auditable.** A regulator can read every rule in ten minutes.
- **Deterministic.** The same inputs produce the same decision, always.
- **Property-testable.** Hypothesis runs 200 randomised inputs per property.
  "No consent records implies zero disclosure" is proven over the input space,
  not sampled from a test set.
- **No prompt-injection surface.** Session notes are attacker-influenced input
  in the general case — a client can say anything, and staff transcribe it. If
  disclosure decisions were made by a model reading those notes, "ignore
  previous instructions and share everything" becomes a disclosure vector. A
  regex has no instructions to ignore.

The cost is real: the engine only understands categories the tagger produces. It
cannot reason about a novel sensitivity. That trade is deliberate — a system
that is right 99% of the time in ways you cannot predict is worse here than one
that is narrow and legible.

### Default deny

Every category starts withheld. Only an active, matching consent record opens
it. Missing record, expired record, revoked record, wrong role, wrong purpose,
low-confidence tag — all deny.

This makes the failure mode of every bug in the system *under*-disclosure. A
missing brief is a bad afternoon. An unwanted disclosure cannot be undone.

### Withheld content is flagged, never silently dropped

This is the decision the whole design turns on.

A brief that quietly omits a topic reads as complete. The receiving clinician
has no way to notice absence in prose and never learns to ask. Silence implies
completeness, and a handover that looks complete but is not is more dangerous
than one that is visibly partial.

So every withheld category is named, with a reason: *revoked* (a boundary to
respect), *expired* (renew it), *wrong role* (ask the right colleague), *no
record* (nobody has asked — an administrative gap, not a refusal), or *low
confidence* (may not be sensitive at all). Collapsing those five into one grey
box would make the consent process look like the client's fault.

The UI's disclosure ledger exists for the same reason: the shape of what is
missing is visible before the summary text is read.

### Safety-critical carve-out

Risk-of-harm content is still withheld when consent says so. But its *existence*
always raises an escalation flag.

The flag names the category and the required action. It never quotes the
content. A clinician learns "there is withheld safety-relevant material here,
escalate before the session" without learning what it says.

This is the sharpest ethical edge in the system, and it is a genuine compromise
rather than a clean win. It slightly erodes the client's control — they cannot
hide the fact that something exists. The judgement is that a client's autonomy
over the *content* of a risk disclosure is compatible with a clinician knowing
that a conversation needs to happen.

### Four-tier fallback ladder

    tier 1   local LLM summary, grounded and schema-validated
    tier 2   extractive — permitted sentences, de-duplicated
    tier 3   structured facts card — goals, actions, consent status
    tier 4   manual handover checklist

Descent is automatic and one-directional. The system is never blank and never
raises to the user. The tier that produced the text is shown on every brief, so
the reader always knows how much machine involvement they are looking at.

Tier 1 is opt-in (`PSYCH_HANDOVER_OLLAMA=1`) and off by default, which makes
tier 2 the demo path. That is deliberate: reported numbers should not depend on
a local model being installed, warm, or reproducible across machines.

### Grounding check on tier 1

A 3B local model asked to summarise three sentences will occasionally add a
plausible clinical detail that was never in the notes — a dose, a date, a
diagnosis. In a handover document, invented detail is indistinguishable from
observation.

Tier-1 output is therefore rejected unless 85% of its content words already
appear in the permitted source. It is blunt: it cannot catch a model that
recombines real words into a false claim ("denies suicidal ideation" built from
"reports suicidal ideation"). It reduces the rate of invented detail; it does
not make tier-1 output safe to read unchecked. Hence the tier badge and the
provenance links.

### Contradictions surfaced, not resolved

Notes disagree. Week one says sober, week three says relapsed. A summariser
handed both will pick one, and which one depends on ordering or sampling — an
invisible choice with clinical consequences.

The conflict detector reports both statements with a notice and takes no
position on which is true. It has no basis to take one. Detection runs over
permitted spans only: flagging a conflict between a permitted and a withheld
statement would disclose the existence and rough content of the withheld one,
turning a transparency feature into a consent bypass.

### One pipeline, two callers

`src/pipeline.py` holds brief assembly. The FastAPI router and the evaluation
harness both call it — the router wraps it in Pydantic models, the harness runs
it over 60 clients.

If assembly lived in the router, the harness would have to reimplement it, and
the two could drift until the report claimed a leakage rate the API no longer
achieved. The pipeline deliberately imports no web framework so the harness can
run it with nothing installed beyond the standard library.

## Where the guarantees stop

The consent filter is exact over the spans it receives. It is not exact over the
notes, because it only ever sees what the tagger found.

An untagged sensitive sentence is invisible to the engine and flows through as
unclassified text. **End-to-end safety is bounded by tagger recall**, which the
current harness does not measure against human annotation. `consent_leakage_rate
= 0.0` means the pipeline is correct on this synthetic distribution — it is not
a claim about real clinical notes, which are messier, more abbreviated, and full
of negation the pattern table has never seen.

The honest summary: the policy layer is provably correct, and it sits on top of
a recognition layer that is merely pretty good. Improving the tagger is the
highest-value next piece of work, and no amount of property testing on the
engine substitutes for it.
