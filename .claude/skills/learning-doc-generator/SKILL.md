---
name: learning-doc-generator
description: Generate a docs/learning/<NN>-<concept>.md + matching PDF for a non-trivial concept just implemented, and update docs/learning/INDEX.md. Use after implementing any non-trivial concept/pattern (ORM relationship, caching layer, algorithm, auth flow, design pattern) — not for trivial boilerplate.
---

# Learning Doc Generator

This project's owner is learning software development through this build. Every non-trivial concept implemented needs a learning artifact — this is a hard requirement (REQUIREMENTS.md Phase 5 context), not optional polish.

## When to trigger

After implementing something conceptually non-trivial: hash-based change detection, atomic swap/transactions, RRF fusion, dual-path indexing, protected-terms masking, bilingual language routing, pgvector/vector search, BM25/tsvector, chunking strategy, etc. Skip trivial boilerplate (a getter, a config constant, a straightforward CRUD endpoint with no new pattern).

## Steps

1. Determine the next `NN` by checking the highest-numbered file already in `docs/learning/` (or `01` if empty).
2. Write `docs/learning/<NN>-<concept-name>.md` with these exact sections:
   - **What it is** — plain-language explanation, no jargon left unexplained.
   - **Real-life analogy** — a concrete, non-technical comparison.
   - **Why we used it here** — tied to the specific requirement ID (Rn) and file just written.
   - **Code walkthrough** — the actual code just written, with inline comments explaining each meaningful line/block.
   - **How to explain this in an interview/to a teammate** — a 3-5 sentence spoken summary.
3. Convert that markdown file to PDF at the same path with `.pdf` extension. Check what's available in this order: `pandoc`, then a Python script using `weasyprint` or `reportlab`. Only install a tool if nothing is available and it's low-risk (ask first if it would need sudo or a large download).
4. Update `docs/learning/INDEX.md` — append a line linking the new `.md` and `.pdf`, in build order.
5. **Delegate steps 2-4 to a subagent** if generating the PDF requires multiple exploratory steps (checking installed tools, trial-and-error rendering) — don't let this bloat the main conversation's context. The subagent should report back only the final file paths, not intermediate output.
