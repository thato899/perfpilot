# agents/performance-investigator

**Owner:** Developer 1/Thatayaone (AI / Orchestration)

The most important AI component in the system: turns validated metrics into observations, evidence-backed hypotheses, confidence scores, and recommended follow-up experiments. Never presents speculation as fact — see the hallucination guardrails in its contract.

Implemented in `investigator.py`. The investigator consumes metrics and
deterministic comparisons, validates all metric/source references, and emits
grounded findings and hypotheses without recalculating numeric results.
