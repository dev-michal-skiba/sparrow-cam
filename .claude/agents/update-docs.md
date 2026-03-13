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

- Keep changes minimal
- Focus on high-level concepts — what the module does and how it fits in the architecture
- Do **not** mention implementation details: variable names, class names, function/method names, specific types
- Match the style and structure of the existing package context file
