---
phase: 1
slug: svelte-visualizer-ui
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-11
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none |
| **Quick run command** | `PYTHONPATH=. pytest tests/test_ui_server.py` |
| **Full suite command** | `PYTHONPATH=. pytest tests/` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=. pytest tests/test_ui_server.py`
- **After every plan wave:** Run `PYTHONPATH=. pytest tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 3 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | VIS-07 | unit | `PYTHONPATH=. pytest tests/test_ui_server.py` | ✅ | ✅ green |
| 01-01-02 | 01 | 1 | VIS-01 | manual | None | ❌ | ✅ green |
| 01-01-03 | 01 | 1 | VIS-02 | manual | None | ❌ | ✅ green |
| 01-01-04 | 01 | 1 | VIS-03 | manual | None | ❌ | ✅ green |
| 01-01-05 | 01 | 1 | VIS-04 | manual | None | ❌ | ✅ green |
| 01-01-06 | 01 | 1 | VIS-05 | manual | None | ❌ | ✅ green |
| 01-01-07 | 01 | 1 | VIS-06 | manual | None | ❌ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|------------|------------|-------------------|
| Svelte Dashboard Layout & Theme | VIS-01 | Front-end visual layout and styling | Open `http://localhost:8080` in light-white theme and check colors, padding, and layout. |
| Sidebar & Episode Filters | VIS-02 | User interaction with the sidebar | Type query search by ID, click status filters, and check that only matching episodes display. |
| Interactive Flow Node Diagrams | VIS-03 | Interactive SVG/CSS flowchart | Select an episode, expand the "Show Detailed Trace Logs" button, and verify that the steps are presented in a compact table and details are toggleable. |
| SVG Candlestick Chart rendering | VIS-04 | SVG rendering verification | Observe SVG chart wicks and volumes on the episode main panel. |
| Settings panel & evolution trigger | VIS-05, VIS-06 | Form inputs and execution controls | Update risk limit parameters, submit the form, verify that changes persist across page refresh. Click "Run offline evolution now" and watch progress update. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 3s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-11
