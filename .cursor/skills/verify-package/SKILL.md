---
name: verify-package
description: Verify lab or processor package by running format, lint checks, and tests with coverage. Use when the user mentions verifying code, running validation, checking code quality, or after completing a feature in the lab or processor packages.
---

# Verify Package

Comprehensive validation workflow for SparrowCam packages (lab and processor).

## When to Use

Apply this skill when the user:
- Completes a feature and wants to verify it
- Asks to "run tests", "check coverage", "validate code"
- Mentions "verify lab" or "verify processor"
- Wants to ensure code meets quality standards

## Workflow

Run these three commands in sequence for the target package:

### 1. Format Code

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
- Must pass before proceeding

### 2. Run Checks

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
- All must pass

### 3. Run Tests

**Lab package:**
```bash
make -C local lab-test
```

**Processor package:**
```bash
make -C local test
```

- Runs pytest with coverage
- **Requires ≥90% coverage overall AND for each file separately**
- All tests must pass
- Coverage report shows per-file breakdown

**Coverage Requirements:**
- Overall package: ≥90%
- Each individual file: ≥90%
- Excluded files (not tested):
  - `app/lab/lab/gui.py` (GUI components)

**Passing pytest flags:**
```bash
# Verbose output
make -C local lab-test ARGS="-vv"

# Run specific test file
make -C local test ARGS="tests/test_detector.py"

# Multiple flags
make -C local lab-test ARGS="-vv -k test_sync_single"
```

## Determining the Package

**If user specifies**: Use the specified package

**If unclear**: Check recent file changes or ask the user

Common indicators:
- Files in `app/lab/` → lab package
- Files in `app/processor/` → processor package
- Both → run for both packages sequentially

## Handling Failures

If any command fails, fix issues in this priority order:

1. **Format failures**: 
   - Fix unused variables, imports
   - Re-run the format command

2. **Check failures**: 
   - Fix linting errors
   - Resolve type checking issues
   - Address security warnings
   - Re-run the check command

3. **Test failures**: 
   - **FIRST**: Fix all failing tests
   - Ensure existing tests pass
   - **THEN**: Implement tests for new features
   - Re-run tests until all pass

4. **Coverage failures** (after all tests pass):
   - Check the per-file coverage breakdown in test output
   - **Both overall AND per-file coverage must be ≥90%**
   - Identify files with coverage < 90%
   - Identify uncovered lines in those files
   - Add tests for uncovered code paths
   - Focus on new functions/features first
   - Re-run until all files have ≥90% coverage

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

**Critical**: Always fix broken tests before adding new ones. New features without tests will cause coverage failures, but broken tests must be fixed first.

After each fix, re-run all three commands to ensure everything passes.

## Success Criteria

All three commands must exit with status 0:
- ✅ Code is formatted
- ✅ No linting/type/security issues
- ✅ All tests pass
- ✅ Overall package coverage ≥90%
- ✅ Each file coverage ≥90% (except gui.py which is excluded)

## Example Usage

**User**: "Verify the lab package"

**Response**:
1. Run `make -C local lab-format`
2. If successful, run `make -C local lab-check`
3. If successful, run `make -C local lab-test`
4. Report final status and coverage percentage

**User**: "I finished the feature, make sure everything is good"

**Response**:
1. Check recent changes to determine package (lab or processor)
2. Run the three-command sequence
3. Fix any issues found
4. Re-run until all pass
5. Confirm all validation passed

## Additional Notes

- Commands run in Docker containers (may take a few seconds to start)
- **Coverage excludes GUI files**: `app/lab/lab/gui.py` is omitted from coverage
- GUI files are not tested and don't affect coverage metrics
- Processor commands have no prefix: `format`, `check`, `test`
- Lab commands use `lab-` prefix: `lab-format`, `lab-check`, `lab-test`
- Each package has independent coverage requirements
- **Both overall AND per-file coverage must be ≥90%**
