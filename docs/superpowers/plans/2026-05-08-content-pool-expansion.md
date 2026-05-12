# Content Pool Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the number of publishable football content items without sacrificing quality by widening match eligibility, widening content windows, and adding lighter-weight content shapes.

**Architecture:** Keep the current quality gate, but let the router score more match types and more time windows, then introduce a lighter content mode that can publish with fewer signals than a full long-form preview. Reuse the same enrichment and hit-layer foundation so every new content shape benefits from the same source stack.

**Tech Stack:** Python 3.12, LangGraph pipeline, PostgreSQL, Redis, `soccerdata`, pytest

---

### Immediate expansion slices

- [ ] Add “elite fallback but lower weight” routing for more current-window matches
- [ ] Add one lighter content shape for low-to-medium signal matches
- [ ] Add extra time windows around the same fixture instead of requiring same-day only
- [ ] Keep `coverage.ready` as the gate for long-form pieces
- [ ] Verify new output counts on current-window samples before discussing any new external source
