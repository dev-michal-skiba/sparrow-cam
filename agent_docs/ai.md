# AI

Defines project-specific Claude Code behavior: custom skills and subagent definitions.

## Purpose

Provides Claude Code skills and subagent definitions tailored to this project's workflow.

## implement-feature Workflow

1. Load the Notion page for the task
2. Read the relevant agent_docs context files for the target package(s)
3. Implement the feature
4. Pause for human review
5. After approval, run verify, update-docs, and e2e in parallel

## update-docs Subagent

Updates agent_docs context files after a feature lands. Only triggers on structural
changes: a new component added, or a component's responsibility changed. Skips bug
fixes, refactors, and minor changes. After editing, validates that size limits pass.

## verify Subagent

Runs tests, code formatting, and lint/type/security checks for the target package.
Fixes failures and writes tests for new features until coverage reaches at least 90%.
Only fully implemented for processor, archive_api, and lab; for all other packages it
stops immediately with a success result.

## e2e Subagent

Maintains and runs the end-to-end test suite. Skipped entirely for frontend-only changes
and for simple single-flag or single-config changes. For all other changes, reviews what
was implemented and updates the test suite only for breaking changes or significant new
user-facing features; defaults to no change for refactors, bug fixes, and minor
enhancements.
