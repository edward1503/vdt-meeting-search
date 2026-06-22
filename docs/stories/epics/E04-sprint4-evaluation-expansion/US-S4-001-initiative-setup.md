# US-S4-001 Sprint 4 Initiative Setup

## Status

implemented

## Lane

normal

## Product Contract

Sprint 4 starts from a documented, reviewable initiative plan rather than ad hoc implementation. The plan identifies benchmark validity risks, story order, validation expectations, exit criteria, non-goals, and open questions before implementation begins.

## Relevant Product Docs

- `README.md`
- `docs/architecture/current-architecture.md`
- `docs/sprint4/plan.md`
- `docs/stories/epics/E04-sprint4-evaluation-expansion/README.md`

## Acceptance Criteria

- `docs/sprint4/plan.md` exists and is marked as the finalized Sprint 4 execution plan.
- Epic README exists under `docs/stories/epics/E04-sprint4-evaluation-expansion/`.
- Stories `US-S4-001` through `US-S4-009` have draft or planned skeletons.
- Plan includes exit criteria, non-goals, validation expectations, schedule, and MVP cuts.
- Harness intake and story records are created or updated for Sprint 4 setup.

## Design Notes

- Commands: Harness CLI remains the operational source of truth.
- Queries: no retrieval query behavior changes in this story.
- API: no API changes in this story.
- Tables: Harness durable records only.
- Domain rules: Sprint 4 is high-risk at initiative level but each story can start in the normal lane.
- UI surfaces: no UI changes in this story.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-001 --unit 0 --integration 0 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Not required for planning docs. |
| Integration | Not required for planning docs. |
| E2E | Not required. |
| Platform | `scripts/bin/harness-cli query matrix` shows Sprint 4 story rows after records are added. |
| Release | Not required. |

## Harness Delta

No Harness policy change is planned. This story creates Sprint 4 planning artifacts and durable records.

## Evidence

Implemented. `docs/sprint4/plan.md` is finalized with four workstreams,
priority order, MVP outputs, deadline schedule, exit criteria, and explicit
non-goals including Redis cache hardening. The Sprint 4 epic README and story
skeletons exist for `US-S4-001` through `US-S4-009`. Harness matrix platform
proof is the Sprint 4 story rows plus this implemented setup story.
