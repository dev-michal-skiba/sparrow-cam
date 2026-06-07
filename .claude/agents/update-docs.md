---
name: update-docs
description: Update agent_docs/ package context files after a feature is implemented. Only updates if new modules are added or fundamental changes occur.
model: haiku
allowedTools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(bash bin/validate_agent_docs agent_docs/[^;&|`]*)
---

# Update Package Documentation

Review implemented changes and update `agent_docs/` package context file if needed.

**Required parameter:** `package`

## 1. Understand Changes

- Use the `package` parameter passed to this agent
- Check `## Package Context Files` section of `CLAUDE.md` file for the package context file
  - **BLOCKING**: If the package is not listed in `CLAUDE.md`, stop immediately and report the missing package
- Read the package context file
- Examine unstaged and staged changes (use `git diff`)

## 2. Decide Whether to Update

Only update documentation if:
- A new module or component was added that needs to be described
- Something fundamental changed in an existing module (e.g., new responsibility, changed architecture)

Do **not** update documentation for:
- Internal refactoring or code reorganization
- Bug fixes or minor enhancements
- Optimization changes

If no update is needed, stop and report that no documentation changes are required.

## 3. Update Documentation

Keep changes minimal. Agent docs must contain **only** domain/business knowledge:

**Include:**
- What the package does in business terms
- Non-obvious design decisions and their rationale
- Key constraints and invariants an implementer would violate without knowing
- Cross-package data contracts (shared formats, protocols, semantics)
- Critical "don't do this" warnings

**Exclude:**
- Module, class, function, method, or variable names
- File paths (beyond the source/tests line present in testable packages)
- Specific type names
- Test/format/lint command syntax
- Step-by-step implementation descriptions
- Anything directly readable from the code

Match the style and structure of the existing package context file.

## 4. Validate

Run `bash bin/validate_agent_docs agent_docs/<package>.md`. If it reports errors (too many
non-empty lines or lines exceeding 99 characters), revise the file until it passes.
