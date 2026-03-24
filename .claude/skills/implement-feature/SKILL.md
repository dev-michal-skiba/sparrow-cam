---
name: implement-feature
description: Implement or plan a feature from a Notion page URL.
---

# Implement Feature

Implement a feature based on a Notion task page.

## Workflow

### 1. Load Task

- Use the Notion MCP tool to retrieve the page content from the provided URL
- Parse the package name, task title, optional description and acceptance criteria from the page
  - The page title follows the format `Package name: Task title`
    - Extract the package name as the prefix before the colon
    - Extract the task title as the suffix after the colon
  - The page content contains optional description and acceptance criteria

### 2. Understand the Task

- Check `## Package Context Files` section of `CLAUDE.md` file for the package context file
  - **BLOCKING**: If the package is not listed in `CLAUDE.md`, stop immediately and report: `Package '<name>' is not listed in CLAUDE.md`
- Read the package context file to understand architecture and existing patterns

### 3. [Optional] Plan Changes

- The user decides before invoking this skill whether to use plan mode (complex features) or proceed directly (simple changes)
- If you're in plan mode: Follow standard Claude Code plan mode workflow before implementation step
- If you're in normal mode: Skip to the implementation step

### 4. Implement

- Make changes to satisfy each acceptance criterion
- Follow existing code style and patterns in the package
- For new business features prefer creating new files over of editing existing ones
- Keep changes minimal and focused on the task
- DO NOT implement or fix any tests, lint and formatting issues

### 5. Verify & Update Documentation

Use the Agent tool to run these two subagents **in parallel**:
- `verify` subagent for the target package
- `update-docs` subagent for the target package
