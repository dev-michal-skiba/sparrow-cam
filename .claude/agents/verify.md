---
name: verify
description: Verify a package by running tests, formatting and lint checks. Use when asked to verify, validate or check code quality after changes.
model: haiku
allowedTools:
  - Read
  - Write
  - Edit
  - Bash(make -C local e2e)
  - Bash(make -C local format)
  - Bash(make -C local check)
  - Bash(make -C local test( ARGS="[^;&|`]*")?)
  - Bash(make -C local lab-format)
  - Bash(make -C local lab-check)
  - Bash(make -C local lab-test( ARGS="[^;&|`]*")?)
  - Glob
  - Grep
---

# Verify Package

Run tests, formatting and lint checks for a package. Fix any issues found at each step before proceeding to the next.

**Required parameter:** `package`

## General Guidelines
- Run make commands from repository root: `make -C local ...`

## 1. Understand Changes

- Use the `package` parameter passed to this agent
- Check `## Package Context Files` section of `CLAUDE.md` file for the package context file
  - **BLOCKING**: If the package is not listed in `CLAUDE.md`, stop immediately and report the missing package
- Read the package context file to understand architecture and find commands for unit tests, e2e tests, formatting and linting
- Examine unstaged and staged changes for the package source code directory (use `git diff`)
- Identify what code has been modified and which files have new features or logic changes

## 2. Fix Existing Tests

- Run unit tests using the command from the package context file
- If the package context file says the package does not implement unit tests, skip this and next step
- Fix any failing tests — fix broken test logic or the implementation the test is checking
- Re-run until all existing tests pass
- Do not proceed until existing tests pass

## 3. Implement Tests for New Features

- Identify new functions/methods/features from the changes in step 1
- Write tests for new features following existing test patterns
- Run tests again and fix failures until all pass
- Verify test coverage: both overall and per-file coverage must be ≥90%
  - If coverage is insufficient, add tests for uncovered code paths

## 4. Verify E2E Tests

- Run E2E tests using the command from the package context file
- If the package context file says the package does not implement E2E tests, skip this step
- Fix any failures and re-run until all pass

## 5. Format Code

- Run the format command from the package context file
- Fix any issues and re-run until it passes

## 6. Run Checks

- Run the checks command from the package context file
- Fix linting, type checking, and security issues
- Re-run until all pass

## Success Criteria

All steps completed in order:
1. Existing tests pass
2. New feature tests implemented and passing
3. Overall and per-file coverage ≥90%
4. E2E tests pass (if implemented)
5. Code is formatted
6. No linting/type/security issues
