---
name: verify
description: Verify lab or processor package by running tests with coverage, format and lint checks. Supports `/verify` to verify both packages, `/verify processor` to verify processor only, and `/verify lab` to verify lab only.
---

## Workflow

Follow this sequence in order for the target package:

### 1. Understand Changes

First, examine unstaged and staged changes for the package:

**Lab package:**
```bash
git diff app/lab/lab/
git diff --staged app/lab/lab/
```

**Processor package:**
```bash
git diff app/processor/processor/
git diff --staged app/processor/processor/
```

- Identify what code has been modified
- Note which files have new features or logic changes
- This determines what tests need to exist or be fixed

### 2. Run Tests and Fix Failures

**Lab package:**
```bash
make -C local lab-test
```

**Processor package:**
```bash
make -C local test
```

**Priority**: Fix failing tests FIRST
- Run the tests to identify failures
- Fix broken tests and their underlying issues
- Re-run until all existing tests pass
- Only then proceed to new feature tests

### 3. Implement Tests for New Features

After all existing tests pass:

- Identify new functions/methods added in code changes
- Write tests for new features
- Run tests again: `make -C local lab-test` or `make -C local test`
- Fix test failures until all pass

### 4. Verify Test Coverage

After all tests pass:

- Check coverage report from test output
- **Both overall AND per-file coverage must be ≥90%**
- Coverage Requirements:
  - Overall package: ≥90%
  - Each individual file: ≥90%
  - Excluded files (not tested):
    - `app/lab/lab/gui.py` (GUI components)

If coverage is insufficient:
- Identify files with coverage < 90%
- Add more tests for uncovered code paths
- Re-run tests until all files have ≥90% coverage

**Coverage Report Example:**
```
Name               Stmts   Miss Branch BrPart  Cover
------------------------------------------------------
lab/constants.py      12      0      0      0   100%
lab/converter.py      74      0     42      0   100%
lab/exception.py       6      0      0      0   100%
lab/sync.py          309     32    110     11    90%  ← Must be ≥90%
lab/utils.py          54      0     18      0   100%
------------------------------------------------------
TOTAL                455     32    170     11    93%  ← Must be ≥90%
```

**Useful pytest flags:**
```bash
# Verbose output
make -C local lab-test ARGS="-vv"

# Run specific test file
make -C local test ARGS="tests/test_detector.py"

# Multiple flags
make -C local lab-test ARGS="-vv -k test_sync_single"
```

### 5. Format Code

Once all tests pass with sufficient coverage:

**Lab package:**
```bash
make -C local lab-format
```

**Processor package:**
```bash
make -C local format
```

- Runs Black formatter
- Applies Ruff auto-fixes
- Fix any formatting issues and re-run until it passes

### 6. Run Checks

Final step after formatting passes:

**Lab package:**
```bash
make -C local lab-check
```

**Processor package:**
```bash
make -C local check
```

- Ruff linting
- Pyright type checking
- Bandit security analysis
- Fix any issues and re-run until all pass

## Determining the Package

**If user specifies**: Use the specified package

**If unclear**: Check recent file changes or ask the user

Common indicators:
- Files in `app/lab/` → lab package
- Files in `app/processor/` → processor package
- Both → run for both packages sequentially

## Handling Failures

Fix issues in this strict order:

### 1. Test Failures (Existing Tests)

When `make -C local lab-test` or `make -C local test` shows failures:

1. Identify which tests are failing
2. Fix the test logic or the implementation that the test is checking
3. Re-run tests until all existing tests pass
4. **Do not proceed to new feature tests until existing tests pass**

### 2. New Feature Tests

After all existing tests pass:

1. Identify new functions/methods in the code changes
2. Write tests for these new features
3. Run tests again
4. Fix test failures until all tests pass

### 3. Coverage Failures

After all tests pass but coverage is insufficient:

1. Check the per-file coverage breakdown in test output
2. **Both overall AND per-file coverage must be ≥90%**
3. Identify files with coverage < 90%
4. Add tests for uncovered code paths in those files
5. Re-run tests until both overall AND per-file coverage reach ≥90%

**Critical**: Test failures must be fixed first, then new feature tests added, then coverage improved. Do not skip or reorder these steps.

### 4. Format Failures

After all tests pass with sufficient coverage:

1. Run format command
2. Fix any formatting issues (unused variables, imports, etc.)
3. Re-run format command until it passes

### 5. Check Failures

Final step after formatting passes:

1. Run check command
2. Fix linting errors
3. Resolve type checking issues
4. Address security warnings
5. Re-run check command until it passes

## Success Criteria

All steps completed in order:
1. ✅ Existing tests all pass
2. ✅ New feature tests implemented and passing
3. ✅ Overall package coverage ≥90%
4. ✅ Each file coverage ≥90% (except gui.py which is excluded)
5. ✅ Code is formatted (make -C local lab-format or make -C local format returns 0)
6. ✅ No linting/type/security issues (make -C local lab-check or make -C local check returns 0)

## Example Usage

**User**: `/verify lab`

**Response**:
1. Examine git changes in app/lab/lab/
2. Run `make -C local lab-test` - fix any failing existing tests
3. Implement tests for new features - fix until all tests pass
4. Verify overall and per-file coverage ≥90% - add tests if needed
5. Run `make -C local lab-format` - fix formatting until it passes
6. Run `make -C local lab-check` - fix linting/type/security issues until it passes
7. Report final status

**User**: `/verify processor`

**Response**:
1. Examine git changes in app/processor/processor/
2. Run `make -C local test` - fix any failing existing tests
3. Implement tests for new features - fix until all tests pass
4. Verify overall and per-file coverage ≥90% - add tests if needed
5. Run `make -C local format` - fix formatting until it passes
6. Run `make -C local check` - fix linting/type/security issues until it passes
7. Report final status

**User**: `/verify`

**Response**:
1. Run lab validation sequence (changes → tests → coverage → format → check)
2. Run processor validation sequence (changes → tests → coverage → format → check)
3. Report results for both packages

**User**: "I finished the feature, make sure everything is good" (via `/verify`)

**Response**:
1. Check recent changes to determine package (lab or processor)
2. Follow the workflow in order:
   - Examine unstaged/staged changes
   - Fix failing tests
   - Implement new feature tests
   - Verify coverage
   - Fix formatting
   - Fix checks
3. Fix any issues found at each step
4. Re-run until that step passes before proceeding
5. Confirm all validation passed

## Additional Notes

- Commands run in Docker containers (may take a few seconds to start)
- **Coverage excludes GUI files**: `app/lab/lab/gui.py` is omitted from coverage
- GUI files are not tested and don't affect coverage metrics
- Processor commands have no prefix: `format`, `check`, `test`
- Lab commands use `lab-` prefix: `lab-format`, `lab-check`, `lab-test`
- Each package has independent coverage requirements
- **Both overall AND per-file coverage must be ≥90%**
