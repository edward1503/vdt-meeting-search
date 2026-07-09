# HotpotQA Bridge Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tune `tv_bridge_title_entities_rrf` for a better latency and quality balance on HotpotQA.

**Architecture:** Reuse the existing benchmark-only bridge method and vary only runtime parameters. Store one benchmark artifact per configuration so results are comparable and auditable.

**Tech Stack:** Python benchmark runner, Elasticsearch, TurboVec, Harness CLI.

---

### Task 1: Prepare Harness Artifacts

**Files:**
- Create: `docs/stories/epics/E05-sprint5-explainable-retrieval/US-S5-012-tune-bridge-aware-second-support-retrieval.md`
- Create: `docs/sprint5/bridge-aware-tuning-report.md`

- [ ] Create a normal-lane story.
- [ ] Create a report shell with table columns for beam size, bridge terms, quality, latency, and decision.

### Task 2: Run Benchmark Grid

**Files:**
- Generate: `evaluation/results/hotpotqa_full/bridge_title_entities_tuning/*.json`
- Generate: `evaluation/runs/hotpotqa_full/bridge_title_entities_tuning/*/*.trec`

- [ ] Run `tv_bridge_title_entities_rrf` with `beam_size=2` and `max_bridge_terms=4`.
- [ ] Run `tv_bridge_title_entities_rrf` with `beam_size=2` and `max_bridge_terms=6`.
- [ ] Run `tv_bridge_title_entities_rrf` with `beam_size=2` and `max_bridge_terms=8`.
- [ ] Run `tv_bridge_title_entities_rrf` with `beam_size=1` and `max_bridge_terms=6`.

### Task 3: Summarize and Decide

**Files:**
- Modify: `docs/sprint5/bridge-aware-tuning-report.md`
- Modify: `docs/stories/epics/E05-sprint5-explainable-retrieval/US-S5-012-tune-bridge-aware-second-support-retrieval.md`
- Modify: `harness.db`

- [ ] Extract metrics from all tuning artifacts.
- [ ] Compare against quality-first baseline `beam_size=3`, `max_bridge_terms=8`.
- [ ] Pick a recommended operating point.
- [ ] Update Harness story evidence and record a trace.
