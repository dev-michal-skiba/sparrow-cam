## Unit Tests
- To run unit tests run `make -C local test` from project root
- Unit tests cover python `app/processor/processor/` package with a test coverage requirement of ≥90%
- Unit tests files are located in `app/processor/tests/`
## End-to-end Test
- To run end-to-end test run `make -C local e2e` from project root
- End-to-end test covers full SparrowCam pipeline
- End-to-end test file is located in `local/e2e-test.sh`