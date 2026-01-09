# Vyasa Manuscript Config and Word Governance

This document defines the ManuscriptConfig schema and the governance rules that preserve word budgets, section priority, and clarity without sacrificing technical rigor.

## 1) ManuscriptConfig Schema

ManuscriptConfig is the authoritative configuration for manuscript-level constraints and policies.

Required fields:
- total_word_limit: integer
- abstract_limit: integer (word or character, must specify)
- visual_budgets:
  - max_tables: integer
  - max_figures: integer
- citation_style: string (e.g., IEEE, AMA, Vancouver)
- section_lock_policy:
  - min_review_status: string (e.g., all comments Addressed)
  - allow_deferred: boolean
  - lock_requires_compile: boolean

## 2) Section Priority Weights

Purpose:
- Each section has a priority weight that guides compression decisions when the manuscript is over budget.
- Priority reflects the section’s role in the blueprint (e.g., Methods > Introduction > Discussion for some journals).

Influence on compression:
- Higher priority sections are protected from aggressive compression.
- Lower priority sections absorb the majority of required reductions.

Why auto-compression is forbidden across locked sections:
- Locked sections are immutable by contract.
- Any compression of locked text would violate auditability and evidence compliance.
- The compiler must never modify locked prose, even to meet budget targets.

## 3) Over-Budget Resolution Flow

Detection:
- Compiler validates aggregate word count against total_word_limit.
- Per-section counts are also validated against section-level limits (if defined).

Analysis:
- Identify which sections exceed proportional budgets.
- Compute delta required to meet total_word_limit.
- Highlight which sections are eligible for reduction (unlocked only).

Required user intervention:
- User must approve a reduction plan (which sections to compress).
- User may unlock sections to allow edits or adjust ManuscriptConfig.

Compiler behavior:
- If locked sections prevent compliance, compilation fails with an explicit report.
- Compiler may not truncate or rewrite text autonomously.
- Compiler produces an over-budget report with recommended targets.

## 4) Accessibility vs Technical Depth

Principle:
- Vyasa enforces “high-school explainable” clarity while preserving technical correctness.

Enforcement mechanisms:
- Analytical Notes guide framing, analogies, and pedagogy.
- Evidence Packet A anchors all factual claims and technical details.
- Critic review flags jargon without explanation or unsupported simplification.

Balance rules:
- Clarity is achieved by better explanation, not by removing essential technical content.
- Analytical Notes may suggest simplifications, but they cannot replace evidence or alter facts.
- Any simplification must remain faithful to Primary Sources.

## Governance Summary

- ManuscriptConfig defines immutable constraints for compilation.
- Section priority weights guide human-directed compression, not automated rewriting.
- Locked sections are protected from all automated compression.
- Accessibility goals are achieved through framing and explanation, never by evidence dilution.
