---
name: implement-feature
description: Implement or plan a feature from a Notion page URL.
---

# Implement Feature

Implement a feature based on a Notion task page.

## Workflow

### 1. Load Task

- Use the Notion MCP tool to retrieve the page content from the provided URL
- Parse the package names, task title, optional description and acceptance criteria from the page
  - The page title follows the format `Package name: Task title` or `Package1|Package2: Task title` for multiple packages
    - Extract package names as the prefix before the colon, splitting on `|` if multiple are present
    - Extract the task title as the suffix after the colon
  - The page content contains optional description and acceptance criteria

### 2. Understand the Task

- Check `## Package Context Files` section of `CLAUDE.md` file for each package's context file
  - **BLOCKING**: If any package is not listed in `CLAUDE.md`, stop immediately and report: `Package '<name>' is not listed in CLAUDE.md`
- Read all package context files to understand architecture and existing patterns

### 3. Implement

- Make changes to satisfy each acceptance criterion
- Follow existing code style and patterns in the package
- For new business features prefer creating new files over of editing existing ones
- Keep changes minimal and focused on the task
- DO NOT implement or fix any tests, lint and formatting issues — this is intentional: the
  `verify` subagent in step 5 owns implementing/fixing tests, lint, and formatting for the
  package. Do not tell it otherwise when spawning it.

### 4. Human Review

- Stop and present a summary of all changes made, organized by acceptance criterion
- Ask the user to review the implementation and provide feedback or approval
- If the user requests changes, implement them and return to the top of this step
- Only proceed to the next step once the user explicitly approves

### 5. Verify, Update Documentation & E2E

Use the Agent tool to run subagents **in parallel** — one `verify` and one `update-docs` per package.

These are **project-specific subagents** defined in `.claude/agents/`. You **must** use `subagent_type` matching their filenames exactly:
- `subagent_type: "verify"` → `.claude/agents/verify.md`
- `subagent_type: "update-docs"` → `.claude/agents/update-docs.md`

Do **not** use `subagent_type: "claude"` or any other generic agent for these tasks.

Agents to spawn:
- For each package: a `verify` subagent targeting that package
- For each package: an `update-docs` subagent targeting that package

When prompting the `verify` subagent, do not tell it that tests were skipped or that it
should skip writing tests — per `.claude/agents/verify.md`, it is responsible for running
lint and checks, and for implementing/fixing tests (including writing tests for new
functions/features) until coverage requirements are met.
