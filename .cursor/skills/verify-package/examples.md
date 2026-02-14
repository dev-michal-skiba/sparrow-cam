# Verify Package Examples

## Scenario 1: After Adding New Function

**User**: "I added `sync_single_folder()` and `remove_hls_files()` to sync.py. Verify everything."

**Steps**:
1. Identify package: `app/lab/lab/sync.py` → lab package
2. Run format: `make -C local lab-format`
3. Run checks: `make -C local lab-check`
4. Run tests: `make -C local lab-test`
5. **If tests fail**: Fix failing tests first, re-run
6. **If coverage < 90%**: Add tests for new functions
7. Re-run until all pass

**Priority**: Broken tests → Coverage tests for new features

## Scenario 2: Format Failures

**Output**:
```
F841 Local variable `files_downloaded` is assigned to but never used
```

**Action**:
- Remove unused variable
- Re-run `make -C local lab-format`
- Continue to next command

## Scenario 3: Test Failures

**Output**:
```
===== FAILURES =====
test_sync_all FAILED
```

**Action**:
1. **Fix the failing test first** (check test logic, update assertions)
2. Re-run tests: `make -C local lab-test`
3. Only after all tests pass, proceed to coverage

## Scenario 4: Test Coverage Failure (All Tests Pass)

**Output**:
```
============================= 122 passed in 16.65s =============================
ERROR: Coverage failure: total of 88 is less than fail-under=90

Name               Stmts   Miss Branch BrPart  Cover   Missing
--------------------------------------------------------------
lab/constants.py      12      0      0      0   100%
lab/converter.py      74      0     42      0   100%
lab/exception.py       6      0      0      0   100%
lab/sync.py          309     50    110     11    83%   ← TOO LOW!
lab/utils.py          54      0     18      0   100%
--------------------------------------------------------------
TOTAL                455     50    170     11    88%   ← TOO LOW!
```

**Action**:
- All tests pass ✓
- **Both** overall (88%) and sync.py (83%) are below 90%
- Identify uncovered lines: 457-469, 568-578
- Add tests for new functions (`sync_single_folder`, `remove_hls_files`)
- Re-run `make -C local lab-test`
- Verify both overall AND per-file coverage ≥90%

**Success Output**:
```
============================= 133 passed in 15.39s =============================

Name               Stmts   Miss Branch BrPart  Cover
------------------------------------------------------
lab/constants.py      12      0      0      0   100%  ✓
lab/converter.py      74      0     42      0   100%  ✓
lab/exception.py       6      0      0      0   100%  ✓
lab/sync.py          309     32    110     11    90%  ✓ NOW PASSING
lab/utils.py          54      0     18      0   100%  ✓
------------------------------------------------------
TOTAL                455     32    170     11    93%  ✓ NOW PASSING

Required test coverage of 90.0% reached. Total coverage: 93.12%
```

## Scenario 5: Individual File Coverage Failure

**Output**:
```
============================= 130 passed in 15.12s =============================

Name               Stmts   Miss Branch BrPart  Cover
------------------------------------------------------
lab/constants.py      12      0      0      0   100%
lab/converter.py      74      0     42      0   100%
lab/exception.py       6      0      0      0   100%
lab/sync.py          309     45    110     11    87%  ← BELOW 90%!
lab/utils.py          54      0     18      0   100%
------------------------------------------------------
TOTAL                455     45    170     11    90%  ← Overall passes

Required test coverage of 90.0% reached. Total coverage: 90.12%
```

**Problem**: Overall coverage is 90.12% ✓, but `sync.py` is only 87% ✗

**Action**:
- Even though overall coverage passes, individual file must also be ≥90%
- Add tests specifically for uncovered code in `sync.py`
- Re-run until `sync.py` reaches ≥90%

## Scenario 7: Both Packages Changed

**User**: "Verify everything"

**Steps**:
1. Run lab sequence:
   - `make -C local lab-format`
   - `make -C local lab-check`
   - `make -C local lab-test`
2. Run processor sequence (note: no prefix):
   - `make -C local format`
   - `make -C local check`
   - `make -C local test`
3. Report both results with per-file coverage breakdown

## Scenario 9: Test with Specific Pytest Flags

**User**: "Run tests with verbose output"

**Lab package:**
```bash
make -C local lab-test ARGS="-vv"
```

**Processor package:**
```bash
make -C local test ARGS="-vv"
```

**Other useful flags:**
```bash
# Run specific test file
make -C local lab-test ARGS="tests/test_sync.py"

# Run tests matching pattern
make -C local lab-test ARGS="-k test_remove_hls"

# Stop on first failure
make -C local test ARGS="-x"

# Show local variables in tracebacks
make -C local lab-test ARGS="-l"
```

## Scenario 10: Type Check Failure

**Output**:
```
error: Argument of type "str | None" cannot be assigned to parameter
```

**Action**:
- Fix type hints or add proper type guards
- Re-run `make -C local lab-check`
- Verify Pyright passes

## Scenario 11: All Tests and Coverage Pass

**Output**:
```
============================= 133 passed in 15.39s =============================

Name               Stmts   Miss Branch BrPart  Cover
------------------------------------------------------
lab/constants.py      12      0      0      0   100%
lab/converter.py      74      0     42      0   100%
lab/exception.py       6      0      0      0   100%
lab/sync.py          309     32    110     11    90%  ← PASSES ≥90%
lab/utils.py          54      0     18      0   100%
------------------------------------------------------
TOTAL                455     32    170     11    93%  ← PASSES ≥90%

1 empty file skipped.
Required test coverage of 90.0% reached. Total coverage: 93.12%
```

**Response**:
"✅ All validation passed! Format ✓, Checks ✓, Tests ✓, Overall Coverage: 93.12%, All files ≥90%"

**Note**: `gui.py` is excluded from coverage and doesn't appear in the report.
