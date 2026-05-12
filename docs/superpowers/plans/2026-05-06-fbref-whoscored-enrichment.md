# FBref And WhoScored Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add FBref and WhoScored as optional enrichment sources that feed better football context into content generation.

**Architecture:** Extend the existing `soccerdata`-backed client layer with browser-aware FBref and WhoScored readers, merge the resulting summaries into `MergedMatchContext`, and surface those signals through `FactPackService` so both LLM prompts and fallback copy can benefit.

**Tech Stack:** Python 3.12, `soccerdata`, Pydantic, pytest

---

### Scope

- [ ] Add browser-aware optional settings for `soccerdata`
- [ ] Upgrade `FBrefClient` from site snapshot to structured recent-stat summaries
- [ ] Add `WhoScoredClient` for missing-player and preview summaries
- [ ] Merge both sources into `knowledge.py`
- [ ] Expose richer summaries through `FactPackService`
- [ ] Verify with targeted pytest coverage
