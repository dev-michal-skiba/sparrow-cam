---
name: verify
description: Verify a package by running tests, formatting and lint checks. Use when asked to verify, validate or check code quality after changes.
model: haiku
allowedTools:
  - Read
  - Write
  - Edit
  - Bash(make -C local (processor|archive-api|lab|web)-(test|format|check)( ARGS="[^;&|`]*")?)
  - Bash(make -C local e2e)
  - Glob
  - Grep
---

# Verify Package

Run tests, formatting and lint checks for a package. Fix any issues found at each step before proceeding to the next.

**Required parameter:** `package`

## Package Commands

Tests, formatting, and checks are only implemented for **processor**, **archive_api**, and **lab**.

For **web**: commands exist but echo "not implemented" and exit 0 — run them normally.

For **stream**, **infra**, **ai**, or any other package: stop immediately and report success — no
tests, formatting, or checks are implemented.

Command pattern: `make -C local {slug}-{test|format|check}` where slug is:
- `processor` for the processor package
- `archive-api` for the archive_api package
- `lab` for the lab package
- `web` for the web package

## General Guidelines
- Run make commands from repository root: `make -C local ...`

## 1. Understand Changes

- Use the `package` parameter passed to this agent
- Check `## Package Context Files` section of `CLAUDE.md` for the package context file
  - **BLOCKING**: If the package is not listed in `CLAUDE.md`, stop immediately and report the missing package
- Read the package context file
  - For processor, archive_api, and lab: the first line contains `Source: <dir> | Tests: <dir>`
  - Use the source directory for scoped git diff: `git diff <source_dir>`
- Identify what code has been modified and which files have new features or logic changes

## 2. Fix Existing Tests

- Run unit tests: `make -C local {slug}-test`
- If the package has no tests (web, stream, infra, ai), skip this and the next step
- Fix any failing tests — fix broken test logic or the implementation the test is checking
- Re-run until all existing tests pass
- Do not proceed until existing tests pass

## 3. Implement Tests for New Features

- Identify new functions/methods/features from the changes in step 1
- Write direct, comprehensive unit tests for every new function or method — do not rely on indirect coverage through callers, integration tests, or other modules
  - Each new function must have its own dedicated test(s) covering all code paths and edge cases
  - Utility and helper functions are not exempt — they require direct tests regardless of whether they are exercised indirectly
- Write tests following existing test patterns in the tests directory from the context file
- Run tests again and fix failures until all pass
- Verify test coverage: both overall and per-file coverage must be ≥90%
  - If coverage is insufficient, add tests for uncovered code paths
  - Make sure lines changed are covered

## 4. Format Code

- Run: `make -C local {slug}-format`
- Fix any issues and re-run until it passes

## 5. Run Checks

- Run: `make -C local {slug}-check`
- Fix linting, type checking, and security issues
- Re-run until all pass

## Success Criteria

All steps completed in order:
1. Existing tests pass
2. New feature tests implemented and passing
3. Overall and per-file coverage ≥90%
4. Code is formatted
5. No linting/type/security issues
