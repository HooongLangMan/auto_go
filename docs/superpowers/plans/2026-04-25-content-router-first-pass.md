# Content Router First Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-pass routed content pipeline that can generate multiple draft articles per match and store them for later publishing automation.

**Architecture:** Keep the existing CLI, enrichment, preview, and publishing shell, but insert a routing layer that decides content modes and quotas before generation. Expand the content storage model so the database can hold multiple drafts per match with mode/account/status metadata.

**Tech Stack:** Python 3.13, Typer, SQLAlchemy, Pydantic, pytest

---

### Task 1: Cover Routing Rules With Tests

**Files:**
- Create: `D:/auto_go/tests/conftest.py`
- Create: `D:/auto_go/tests/test_routing.py`

- [ ] Write tests for routed content opportunity selection
- [ ] Run the routing tests and confirm they fail

### Task 2: Cover Richer Content Storage With Tests

**Files:**
- Create: `D:/auto_go/tests/test_db_content_storage.py`

- [ ] Write tests for storing multiple content rows per match
- [ ] Run the storage tests and confirm they fail

### Task 3: Implement Routed Content Models And Settings

**Files:**
- Modify: `D:/auto_go/src/auto_football/config.py`
- Modify: `D:/auto_go/src/auto_football/schemas.py`
- Modify: `D:/auto_go/src/auto_football/state.py`
- Create: `D:/auto_go/src/auto_football/routing.py`

- [ ] Add content mode, content status, routed plan, and target config models
- [ ] Add settings for target quotas and optional football-data access
- [ ] Implement the content router

### Task 4: Integrate Router And Multi-Content Storage

**Files:**
- Modify: `D:/auto_go/src/auto_football/db.py`
- Modify: `D:/auto_go/src/auto_football/pipeline.py`
- Modify: `D:/auto_go/src/auto_football/clients.py`

- [ ] Expand content persistence to support multiple drafts
- [ ] Add football-data as an optional structured source
- [ ] Replace fixed per-match content generation with routed plans

### Task 5: Update Preview And Verify

**Files:**
- Modify: `D:/auto_go/src/auto_football/cli.py`
- Modify: `D:/auto_go/src/auto_football/images.py`

- [ ] Update preview queries/rendering for richer content metadata
- [ ] Run targeted pytest verification for routing and storage
- [ ] Run one lightweight import or smoke check if available
