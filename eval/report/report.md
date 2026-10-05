# Evaluation report

Consent-aware continuity summary for psychiatric discharge handovers.

- Clients evaluated: **60** (synthetic, seed 42)
- Recipient role: **counsellor**, purpose **handover**
- Evaluation date (fixed): **2025-03-01**
- Metrics passing target: **7/7**
- Report generated: 2026-10-05T06:48:03+00:00Z

Baseline is last-three-sessions verbatim concatenation with regex keyword
redaction — what a ward under time pressure actually does today.

## Results

| Metric | Target | Baseline | Prototype | Delta | Better | Status |
|---|---|---|---|---|---|---|
| `consent_leakage_rate` | 0.0 | 1.000 | 0.000 | -1.000 | lower | PASS |
| `action_retention_rate` | 1.0 | 0.000 | 1.000 | +1.000 | higher | PASS |
| `withheld_flag_recall` | >=0.95 | 0.000 | 1.000 | +1.000 | higher | PASS |
| `word_reduction` | <=0.40 | 1.000 | 0.343 | -0.657 | lower | PASS |
| `safety_escalation_recall` | 1.0 | 0.000 | 1.000 | +1.000 | higher | PASS |
| `provenance_coverage` | 1.0 | 0.000 | 1.000 | +1.000 | higher | PASS |
| `fallback_availability` | 1.0 | 1.000 | 1.000 | +0.000 | higher | PASS |

## Metric definitions and error analysis

### `consent_leakage_rate`

Fraction of briefs containing content from a non-permitted category. Target 0.0.

Baseline 1.000 → prototype 0.000 (-1.000).

Keyword redaction removes the word but leaves the sentence, so the disclosure survives and is trivially re-identifiable. Category-level filtering removes the whole span before generation.

### `action_retention_rate`

Open high-priority actions carried forward with owner and due date. Target 1.0.

Baseline 0.000 → prototype 1.000 (+1.000).

Baseline copies prose and has no action model at all. Actions travel on a separate track that consent filtering never touches.

### `withheld_flag_recall`

Withheld topics openly signalled rather than silently dropped. Target >=0.95.

Baseline 0.000 → prototype 1.000 (+1.000).

Baseline cannot flag what it does not model. Every withheld category is named in the notice so the clinician knows a gap exists.

### `word_reduction`

Prototype word count as a fraction of baseline word count. Target <=0.40.

Baseline 1.000 → prototype 0.343 (-0.657).

Baseline concatenates three full sessions verbatim. Tier 2 keeps only permitted sentences and de-duplicates repeats across sessions.

### `safety_escalation_recall`

Clients with withheld safety content whose brief raises an escalation flag. Target 1.0.

Baseline 0.000 → prototype 1.000 (+1.000).

Baseline redacts risk wording and signals nothing, so withheld risk becomes invisible. The carve-out flags existence without disclosing content.

### `provenance_coverage`

Briefs whose disclosed content is traceable to source span ids. Target 1.0.

Baseline 0.000 → prototype 1.000 (+1.000).

Baseline output is an undifferentiated blob with no span links. Every prototype sentence carries the span id it came from.

### `fallback_availability`

Clients receiving a usable non-empty brief without an unhandled error. Target 1.0.

Baseline 1.000 → prototype 1.000 (+0.000).

Baseline is always available but always unfiltered. The ladder keeps availability without giving up the consent guarantee.

## Fallback tier distribution

| Tier | Briefs |
|---|---|
| tier 2 — extractive | 60 |

Tier 1 is disabled by default (`PSYCH_HANDOVER_OLLAMA=0`), so a clean run
sits at tier 2. That is the intended demo posture: the reported numbers
come from the deterministic extractive path and do not depend on a local
model being installed, warm, or reproducible across machines.

## Worked example

Client `C001`, recipient role `counsellor`.

### Baseline

```
Client has outstanding rent arrears; social worker referral made. [REDACTED] officer contacted regarding compliance. No current risk identified; protective factors strong. Client attended OT group; participation noted as positive. | Client reported [REDACTED] urges — safety plan reviewed and updated. Care coordinator handover planned for next week. | Sibling requested information — consent not in place, declined. Benefits claim in progress; Universal Credit application submitted. Lithium level checked: 0.7 mmol/L, within therapeutic range. Discussed discharge goals and community support plan.
```

### Prototype

**Extractive summary — source sentences only (tier 2)**

```
Extractive summary (AI unavailable): Client attended OT group; participation noted as positive. Care coordinator handover planned for next week. Discussed discharge goals and community support plan.
```

**Withheld notice**

> 5 topic(s) withheld under client consent: financial, safety_risk, forensic_legal, medication, family_conflict. Ask the client directly if clinically relevant.

**Escalation flags**

> Safety-relevant content withheld under category 'safety_risk' — escalate to supervisor before session.
> RED FLAG — 'Update safety plan with client' is 11 days overdue (owner: counsellor, due 2025-02-18). Resolve or reassign before the session.
> RED FLAG — 'Refer to housing support' is 8 days overdue (owner: social_worker, due 2025-02-21). Resolve or reassign before the session.
> RED FLAG — 'Submit benefits application' is 11 days overdue (owner: social_worker, due 2025-02-18). Resolve or reassign before the session.

**Uncertainty**

> 7 span(s) carried confidence below 0.85. Verify sensitive history directly with the client if clinically indicated.

**Why each topic was withheld**

| Category | Reason | Explanation shown to the clinician |
|---|---|---|
| `financial` | `low_confidence` | Content was tagged as possibly sensitive but below the confidence threshold, so it was withheld by default. It may not be sensitive at all. |
| `safety_risk` | `low_confidence` | Content was tagged as possibly sensitive but below the confidence threshold, so it was withheld by default. It may not be sensitive at all. |
| `forensic_legal` | `low_confidence` | Content was tagged as possibly sensitive but below the confidence threshold, so it was withheld by default. It may not be sensitive at all. |
| `medication` | `wrong_role` | The client consented to share this with a different role, not yours. |
| `family_conflict` | `no_record` | Consent not on file for this category. Nobody has asked the client — this is an administrative gap, not a refusal. |

## Limitations

Read the numbers above with these in mind.

- **Synthetic data.** All 60 clients come from a template generator with a
  fixed seed. Real clinical notes are messier, less grammatical, and full of
  abbreviations and negation the tagger has never seen. A leakage rate of 0.0
  here means the pipeline is correct on this distribution — it is not a
  claim about real notes.
- **The tagger bounds everything.** Consent filtering is exact, but it can
  only act on spans that were tagged. An untagged sensitive sentence is
  invisible to the engine and flows through as unclassified text. The
  end-to-end guarantee is therefore no stronger than tagger recall, which
  this harness does not measure against human annotation.
- **Leakage detection is lexical.** Content-word overlap catches verbatim and
  partially-redacted disclosure. It would not catch a genuine paraphrase that
  reuses none of the source vocabulary.
- **One role scored.** Metrics are computed for the counsellor. Other roles
  see different consent sets; spot-checking suggests the same behaviour, but
  it is not scored here.
- **Tier 1 largely unevaluated.** With the local model off, these numbers say
  almost nothing about the quality or grounding of AI-generated summaries.
