---
name: e2e
description: Maintain local/e2e-test.sh after a feature is implemented. Decides whether e2e tests need updating or expanding, then runs them until they pass.
model: haiku
allowedTools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(git diff)
  - Bash(make -C local e2e)
---

# E2E Test Maintenance

Review implemented changes and update `local/e2e-test.sh` only if necessary.

**WARNING**: A successful e2e run can take up to 10 minutes. Be very skeptical about making changes — only do so when there is strong evidence they are required.

## 1. Understand Changes

- Examine unstaged and staged changes (use `git diff`)
- Read `local/e2e-test.sh` to understand what is currently tested

## 2. Decide Whether to Update

Update the e2e test only if at least one of these conditions clearly applies:

- **Breaking change**: the implementation changes existing behavior in a way that will make the current e2e script fail (e.g., renamed endpoint, changed log message, removed feature, changed users/permissions)
- **Significant new feature**: a major new user-facing capability was introduced that the e2e suite has no coverage for and it is clearly worth the cost of a slow run

Do **not** update the e2e test for:
- Internal refactors, code reorganization, or optimizations
- Bug fixes that don't change observable behavior
- Minor enhancements already covered by existing tests
- Any case where you are uncertain — default to no change

If no update is needed, report that no e2e changes are required and proceed to step 4.

## 3. Update

Make the minimal necessary change to `local/e2e-test.sh`.

## 4. Decide Whether to Run

Run the e2e tests if either:
- The e2e tests were updated in step 3
- There is a reasonable suspicion the existing tests may fail given the changes

Otherwise, stop and report that e2e tests were not run.

## 5. Run

- Run `make -C local e2e`
- Fix any failures and re-run until the test passes
