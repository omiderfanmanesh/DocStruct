<!--
Sync Impact Report
- Version change: unknown -> 0.1.0
- Modified principles:
	- [PRINCIPLE_1_NAME] -> Library-First
	- [PRINCIPLE_2_NAME] -> CLI-First Interfaces
	- [PRINCIPLE_3_NAME] -> Test-First (TDD)
	- [PRINCIPLE_4_NAME] -> Integration & Contract Testing
	- [PRINCIPLE_5_NAME] -> Observability, Versioning & Simplicity
- Added sections: none
- Removed sections: none
- Templates requiring review:
	- .specify/templates/plan-template.md: ✅ reviewed
	- .specify/templates/spec-template.md: ✅ reviewed
	- .specify/templates/tasks-template.md: ✅ reviewed
	- .specify/templates/constitution-template.md: ✅ reviewed
- Follow-up TODOs:
	- RATIFICATION_DATE: TODO (confirm original adoption date)
-->

# DocStruct Constitution

## Core Principles

### Library-First
Every feature or capability SHOULD be designed as a reusable library or module when reasonable. Libraries MUST be self-contained, have clear responsibilities, be independently testable, and include minimal, well-scoped public APIs. Rationale: promotes reuse, easier testing, and clearer ownership.

### CLI-First Interfaces
Tools and libraries MUST expose a CLI or lightweight programmatic interface for automation. Text I/O (stdin/args → stdout/stderr) and JSON interchange MUST be supported for reproducibility and scripting. Rationale: simplifies automation, CI integration and debugging.

### Test-First (TDD)
Tests are REQUIRED for all new functionality. Authors SHOULD write failing tests that express desired behavior before implementation (Red-Green-Refactor). Critical bug fixes MUST include regression tests. Rationale: prevents regressions and documents expected behavior.

## Testing & Trust Policy
- Every bugfix must add a regression fixture + an automated test.
- Core logic must have unit tests:
  - heading classification
  - numeric prefix parenting
  - list rendering guards (no list becomes heading)
- End-to-end golden tests are required for at least 2 real documents.
- The pipeline must emit report.json and tests must assert key trust metrics:
  - no list blocks rendered as headings
  - unmatched decimal headings <= configurable threshold
  - unknown headings tracked and stable
- Tests must be runnable with a single command: `pytest`.

### Integration & Contract Testing
Changes that affect cross-module behavior, public contracts, or external integrations MUST include integration tests and contract-level checks. Define minimal end-to-end tests for each integration surface. Rationale: ensures interoperability and guards against hidden breaking changes.

### Observability, Versioning & Simplicity
Projects MUST emit structured logs or machine-readable traces where applicable and include basic metrics or health checks for services. Versioning MUST follow semantic versioning for public packages and APIs. Prefer simple implementations; avoid premature optimization (YAGNI).

## Constraints & Standards
All code MUST pass linting and formatting rules adopted by the repository. Secrets MUST NOT be committed. Long-running or high-cost operations MUST be documented and justified. Security-sensitive features MUST follow minimal risk review and be unit-tested.

## Development Workflow
- Branching: feature branches per task, names prefixed with the tracking ID (e.g., `T123-feature-name`).
- Code Review: all changes MUST be reviewed via pull request; reviewers MUST validate tests and CI status.
- CI Gates: PRs MUST run unit tests; changes touching integration points MUST run integration tests or provide a documented migration plan.
- Releases: public releases should be tagged and accompanied by changelogs describing breaking changes and migration guidance.

## Governance
The Constitution is authoritative for development practices. Amendments require a documented rationale in a PR that references affected specs, a migration or compatibility plan for breaking changes, and approval by the repository maintainers (or a majority of designated approvers). Minor clarifications (typos, wording) MAY be merged with a patch bump; additions or new mandatory rules SHOULD be a minor or major bump based on compatibility impact.

**Version**: 0.1.0 | **Ratified**: TODO(RATIFICATION_DATE) | **Last Amended**: 2026-02-26

