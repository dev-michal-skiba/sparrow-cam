# Overview
- Software: Claude Code configuration (skills, subagents, settings)
- Responsibility: Defines project-specific Claude Code behavior — custom slash command skills, subagent definitions, and permission settings.

## Package Layout
- Package location: `.claude/`
    - `settings.local.json` — project-level permissions (allowed/denied Bash commands, MCP servers, plugins)
    - `skills/` — custom slash command skills
        - `implement-feature/SKILL.md` — skill invoked via `/implement-feature`; fetches a Notion task page, reads package context, and implements or plans the feature
    - `agents/` — custom subagent definitions
        - `update-docs.md` — subagent that updates `agent_docs/` context files after a feature is implemented; only updates on structural changes
        - `verify.md` — subagent that runs tests, formatting, and lint checks for a given package and fixes issues
        - `e2e.md` — subagent that maintains and runs end-to-end tests; updates the test suite only for breaking changes or significant new features

## Skills

### `implement-feature`
Invoked via `/implement-feature <notion-url>`. Fetches the Notion task page, parses the package name(s) and task title from the `Package: Title` page title format, reads the relevant `agent_docs/` context files, and implements or plans the feature. After implementation, runs `verify`, `update-docs`, and `e2e` subagents in parallel per package.

## Subagents

### `update-docs`
Accepts a `package` parameter. Reads the package context file and git diff, then updates `agent_docs/<package>.md` only if a new module was added or something fundamental changed. Skips updates for bug fixes, refactors, or minor changes.

### `verify`
Accepts a `package` parameter. Reads the package context file, runs unit tests (fixing failures and writing tests for new features until coverage ≥90%), formats code, and runs lint/type checks. Uses `make -C local` commands defined in the package context file.

### `e2e`
No parameters. Maintains end-to-end tests by reviewing implemented changes and deciding whether the test suite needs updating. Updates the test suite only for breaking changes or significant new user-facing features; defaults to no change for refactors, bug fixes, and minor enhancements. Runs the e2e test suite to verify changes.

## Settings

### `settings.local.json`
Stores project-level `permissions.allow` entries for Bash commands and MCP tools that Claude Code may use without prompting. Also enables MCP servers (`notion`) and plugins (`frontend-design`).

## Formatting, Linting, and Unit Tests
These steps should be skipped — AI Package has no formatting, linting, or unit test tooling.
