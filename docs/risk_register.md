# Risk register

Scored for the prototype as built: synthetic data, no real clients, no clinical
deployment. Likelihood and impact would both need rescoring before any pilot
with real notes.

**Residual** is the risk that remains *after* the listed mitigation.

---

| # | Risk | Likelihood | Impact | Harm to whom | Detection signal | Mitigation | Residual | Owner |
|---|---|---|---|---|---|---|---|---|
| 1 | **Tagger misses a sensitive span**, so the engine never sees it and it flows through as unclassified text | High | High | Client — unconsented disclosure of trauma, forensic or sexual-health history to a clinician they did not authorise | `consent_leakage_rate > 0` against human-annotated notes; clinician reports seeing content the client says they withheld | Broad, low-specificity patterns bias toward over-tagging; sub-threshold matches fail closed; unclassified sentences pass through unaltered so they remain auditable | **High.** This is the system's binding constraint. The engine is provably correct over spans it receives; nothing proves the tagger finds them all. Recall is unmeasured against human annotation | Tagger owner |
| 2 | **Clinician over-trusts an AI-generated summary** and acts on an invented detail — a dose, a date, a diagnosis | Medium | High | Client — clinical decision made on fabricated information | Grounding score below threshold in logs; clinician cannot trace a statement to a source span | Tier 1 off by default; 85% content-word grounding check rejects ungrounded output; tier badge on every brief; provenance links from summary to span ids | **Medium.** The grounding check cannot catch recombination of real words into a false claim ("denies" from "reports"). Tier badge relies on the reader noticing it | Generator owner |
| 3 | **Withheld topic read as absent** — clinician assumes the brief is complete and never asks the client | Medium | High | Client — repeats their history for the fourth time, the original harm; or a clinician proceeds unaware of relevant context | Client complaint; `withheld_flag_recall < 1.0`; UI usability testing showing the ledger is skipped | Every withheld category named with a reason; disclosure ledger placed above the summary so absence is seen before text is read; five distinct withhold reasons rather than one grey box | **Low–Medium.** Mitigation is a UI affordance, and a rushed reader can skip any affordance. Not yet tested with real clinicians under time pressure | UX owner |
| 4 | **Safety-relevant content withheld and the escalation flag is missed or ignored** | Low | Critical | Client and clinician — a session opens with no awareness that a risk conversation is needed | `safety_escalation_recall < 1.0`; incident review finds a withheld risk span with no corresponding flag | Carve-out fires on both `SAFETY_RISK` category and the per-span `is_safety_relevant` flag, so a safety span in any category escalates; flag rendered top-of-page with `role="alert"`; flag names the category and required action without quoting content | **Low** for detection (property-tested, 1.0 on the eval set); **Medium** for human response — the system cannot force anyone to act on a flag | Policy owner |
| 5 | **Consent revoked but a cached or previously-generated brief still circulates** — printed, emailed, or held in a browser tab | Medium | High | Client — a withdrawn boundary is not actually withdrawn | Audit log shows a disclosure after `revoked_at`; client reports content resurfacing | Revocation is retroactive for all future briefs; briefs are generated per request, never stored server-side; TanStack Query configured not to refetch stale briefs silently | **High.** The prototype has no control over a brief once it leaves the screen. A printed handover cannot be revoked. This is a process problem that no amount of code fixes | Deployment owner |
| 6 | **Pattern table drift** — someone raises a pattern weight to "fix" a span being withheld, quietly widening disclosure across every client | Medium | High | All clients — systemic, silent widening of what is shared | Diff on `patterns.py` in review; `consent_leakage_rate` regression in CI; unexplained fall in `withheld_flag_recall` | Weights documented with explicit bands and a written warning against raising them to unblock a case; policy engine protected from agent modification by `AGENTS.md`; property tests fail on threshold changes | **Medium.** A determined edit passes tests if it only changes weights, not thresholds. Needs a CI check that fails when aggregate disclosure rate moves more than a set margin | Policy owner |
| 7 | **Synthetic-to-real distribution shift** — patterns tuned on template-generated notes perform far worse on real ward writing (abbreviations, negation, shorthand, typos) | High | High | Client — silent collapse in tagger recall, feeding risk 1 | Sharp drop in spans-per-session on real notes; clinician reports of obviously-missed content; leakage against human annotation | Documented explicitly in the eval report's limitations; stdlib and spaCy backends share one pattern table so behaviour does not change with environment | **High and unmitigated.** No real notes have been tested. The eval numbers describe one synthetic distribution and should not be quoted as clinical performance | Research owner |

---

## Notes on the scoring

**Three residual-high rows is the honest picture, not an oversight.** Risks 1, 5
and 7 are all versions of the same admission: the parts of this system that are
provably correct are not the parts that bound its real-world safety. The consent
engine is the most rigorous component and the least likely to be the cause of a
real incident.

**Risk 5 is the one that code cannot fix.** Everything else has a plausible
engineering response. A brief that has been printed and left on a desk is
outside the system's control entirely, and any deployment needs a handling
policy — retention limits, no printing, or accepting the risk explicitly.

**Risk 4 is scored critical on impact and low on likelihood**, which is the
correct shape for a safety carve-out. The mechanism is property-tested and
scores 1.0 on the eval set. The residual sits almost entirely in whether a human
acts on the flag, which is a training and workflow question.

**What would change these scores.** A recall study against human-annotated real
notes would move risks 1 and 7 from "unmeasured" to "measured", which is a
prerequisite for any pilot. Everything else is comparatively cheap.
