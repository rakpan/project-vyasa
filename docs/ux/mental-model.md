# Vyasa UX Mental Model

This document explains how users interact with Vyasa without needing to understand the backend. It aligns the UI with the underlying governance model.

## 1) Project Sub-Nav

Vyasa is organized around a project sub-navigation with four primary workspaces:

- Evidence
  - Your source documents and extracted chunks.
  - The only place where citeable facts come from.
- Perspectives (Analytical Notes)
  - Your framing, analogies, and glossary notes.
  - Influence-only; never citeable.
- Blueprint
  - The manuscript plan: sections, goals, and evidence clusters.
  - Governs how the manuscript is built.
- Manuscript
  - The compiled text assembled from sections.
  - Locks and budgets apply here.

## 2) What the User Controls vs What the System Enforces

User controls:
- Draft and revise section text.
- Create and edit Analytical Notes.
- Resolve review comments.
- Decide when a section is ready to lock.

System enforces:
- Locks: once locked, section text is immutable unless explicitly unlocked.
- Review comments: required responses before lock.
- Budgets: word limits and visual budgets are enforced at compile time.
- Compilation: the compiler, not the editor, finalizes citations and formatting.

## 3) Section-First Interaction

- Each section is refined independently to keep evidence traceable and audits clear.
- Section-level evidence packets make it obvious what supports each claim.
- Locking is explicit to preserve immutability and reproducibility.

## 4) Markdown-First Philosophy

- Vyasa favors Markdown drafts over heavy WYSIWYG editors.
- Markdown keeps author intent clear and audit-friendly.
- The compiler handles the final rendering, citations, and formatting.
- Markdown + compiler = clarity, control, and reproducibility.

## 5) Feedback Loops

- Review comments:
  - Human or Critic feedback that must be addressed before locking.
- Critic flags:
  - Automated warnings for unsupported claims, tone drift, or evidence gaps.
- Evidence drift warnings:
  - Alerts when the evidence basis for a section changes and requires re-review.

## Summary

Vyasa is designed so the user focuses on meaning and structure while the system guarantees evidence integrity, reproducibility, and governance. The UI mirrors this by separating Evidence, Perspectives, Blueprint, and Manuscript into distinct, purposeful spaces.
