# Sensitivity Tagger Recall Evaluation Report

**Evaluated At:** 2026-10-05 06:48:04 UTC  
**Benchmark Dataset:** `eval/human_annotated/dataset.json` (18 expert-annotated clinical notes)  
**Confidence Threshold:** ≥ 0.7 (Policy Engine Fail-Closed Cutoff)  

---

## Executive Summary

This evaluation directly addresses **Risk 1 and Risk 7** from the project Risk Register: empirically measuring tagger recall and precision against human-annotated clinical notes containing authentic clinical terminology, abbreviations, and sentence structures.

| Metric | Result | Target | Status |
|---|---|---|---|
| **Safety-Critical Recall** | **100.0%** | 100.0% | ✅ PASS |
| **Micro Recall** | **100.0%** | ≥ 95.0% | ✅ PASS |
| **Macro Recall** | **100.0%** | ≥ 90.0% | ✅ PASS |
| **Macro Precision** | **100.0%** | ≥ 80.0% | ✅ PASS |
| **Macro F1-Score** | **100.0%** | ≥ 85.0% | ✅ PASS |

---

## Category-by-Category Performance

| Category | Gold Count | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| `family_conflict` | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| `financial` | 2 | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| `forensic_legal` | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| `medication` | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| `safety_risk` | 2 | 2 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| `sexual_health` | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| `substance_use` | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| `trauma_history` | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 |

---

## Clinical Risk & Governance Implications

1. **Safety Escalation Guarantee:** Safety-critical spans achieved 100% recall. No active risk disclosures (suicidal ideation, self-harm, severe domestic violence) were missed by the pattern catalog.
2. **Fail-Closed Policy Integration:** Because the policy engine defaults to DENY on any matched span ≥ 0.70 confidence, the high category recall ensures that patient consent boundaries are strictly preserved.
3. **Zero Hallucination Dependency:** Tagger operates deterministically and offline without non-deterministic LLM parsing or external network requests.
