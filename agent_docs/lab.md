# Lab

- Source: app/lab/lab/ | Tests: app/lab/tests/

## Purpose

Downloads the YOLO dataset from the Raspberry Pi to local storage for use in model fine-tuning.
The dataset is built incrementally on the Pi by archive_api's annotation worker (see archive_api.md
"Dataset Generation" section for how images and labels are produced). Provides tooling to select
a balanced training subset from the synced dataset and fine-tune a generic bird detector.

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

## Sync Invocation

Manually invoked via `make -C local lab-sync`, which runs the entry point `python -m lab.sync`
inside the lab container. No scheduled automation exists yet.

## Fine-Tuning

Trains a generic bird detector (single class, remaps all original annotations to that class)
by fine-tuning yolo26n on a balanced subset of the synced dataset. This is the first stage
of a two-stage detection pipeline; species classification runs as a separate downstream model.

### Frame Selection and Balancing

Automatically selects up to 365 positive (bird-containing) frames and 55 negative frames from
the synced dataset, deterministically and balancedly. Selection is seeded from a SHA256 hash
of the dataset's file contents and sizes, ensuring the same dataset always yields the same
selection (re-annotation on the Pi changes file sizes and reseeds selection). The algorithm
spreads frames evenly across day-of-year slots to handle multi-year datasets without clustering
on a single year, honors the dataset's hour-of-day and bird-species distributions, and
guarantees every species present appears at least once in the selection. Fewer than target
frames are clamped with a logged warning if the dataset is smaller.

### Annotation Remapping and Training

Rewrites every annotation in the selected frames to a single class (0: bird), discarding the
original species labels. Trains yolo26n (base weights mounted from the processor package) on
the prepared dataset for 100 epochs at batch size 16 and image size 640. The base model and
training parameters are fixed; versions and descriptions vary by invocation.

### Invocation

Invoked via `make -C local lab-fine-tune ARGS="--version v1.0.0 --description 'Fine-tuned
on 2026 dataset'"` (or interactively without ARGS, which prompts for version and description).
Version must match the pattern v\d+\.\d+\.\d+ and is validated before training begins.
Description is limited to 1024 characters. Saves the fine-tuned weights, dataset.yaml, and
metadata.json (version, description, created_at timestamp) under /.storage/fine_tuned/. The
lab Docker image must be rebuilt (`make -C local lab-build`) after updating dependencies (e.g.,
ultralytics pinned version) for the new dependencies to take effect; a stale image will silently
retain its baked-in dependencies and may crash during training (e.g., YOLO signature mismatches).
