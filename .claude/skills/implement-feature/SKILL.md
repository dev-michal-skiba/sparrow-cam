---
name: implement-feature
description: Implement a feature based on structured task format. Use when the user provides a task starting with a package name, colon and title followed by an optional description, "## Acceptance Criteria" section with bulleted criteria.
---

# Implement Feature

Implement a feature based on a structured task prompt.

## Task Format

The user provides a task in this format:

```
<Package>: <Task title>
<Task description:optional>
## Acceptance Criteria
- <criterion 1>
- <criterion 2>
- ...
```

## Workflow

### 1. Understand the Task

- Parse the package name, task title, optional description and acceptance criteria
- Check `## Package Context Files` section of `CLAUDE.md` file for the package context file
  - **BLOCKING**: If the package is not listed in `CLAUDE.md`, stop immediately and report the missing package
- Read the package context file to understand architecture and existing patterns

### 2. [Optional] Plan Changes

- The user decides before invoking this skill whether to use plan mode (complex features) or proceed directly (simple changes)
- If you're in plan mode: Follow standard Claude Code plan mode workflow before implementation step
- If you're in normal mode: Skip to the implementation step

### 3. Implement

- Make changes to satisfy each acceptance criterion
- Follow existing code style and patterns in the package
- For new business features prefer creating new files over of editing existing ones
- Keep changes minimal and focused on the task
- DO NOT implement or fix any tests, lint and formatting issues

### 4. Verify & Update Documentation

Use the Agent tool to run these two subagents **in parallel**:
- `verify` subagent for the target package
- `update-docs` subagent for the target package
