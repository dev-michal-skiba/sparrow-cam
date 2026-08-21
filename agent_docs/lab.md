# Lab

- Source: app/lab/lab/ | Tests: app/lab/tests/

## Purpose

Downloads the YOLO dataset from the Raspberry Pi to local storage for use in model fine-tuning.
The dataset is built incrementally on the Pi by archive_api's annotation worker (see archive_api.md
"Dataset Generation" section for how images and labels are produced).

## Dataset Sync Behavior

The sync is one-way and additive — it never deletes files. A remote file is downloaded if:
- It does not exist locally, OR
- Its size differs from the local copy (indicates re-annotation on the Pi)

Local-only files (e.g., a manually maintained dataset.yaml) are left untouched. This design
allows local dataset customization without sync interference.

## Connection Resilience

Syncs via SFTP using an SSH key mounted from the host (parameterized by ansible_target_host
and ansible_target_user read from the mounted config file, using the same convention as other
components). The sync has aggressive retry logic to tolerate flaky Pi connections: if any
network operation fails, the connection drops, reconnects, and retries the failed file up to 15
times before giving up.

## Invocation

Manually invoked via `make -C local lab-sync`, which runs the entry point `python -m lab.sync`
inside the lab container. No scheduled automation exists yet.
