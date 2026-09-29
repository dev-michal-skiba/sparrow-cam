# Lab

- Source: app/lab/lab/ | Tests: app/lab/tests/
- `local/Dockerfile.lab` builds `FROM sparrow_cam_processor:latest` and resets `ENTRYPOINT []`,
  since it would otherwise inherit processor's index-db init script and fail (lab doesn't mount
  `/var/lib/sparrow_cam`).

## Purpose

Downloads the YOLO dataset from the Raspberry Pi for two-stage detection training. Built
incrementally by archive_api's annotation worker (see archive_api.md Dataset Generation). Provides
tooling to select balanced subsets and train: a generic bird detector (stage 1) and a species
classifier on detector crops (stage 2).

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

## Stage-1 Fine-Tuning (Generic Bird Detector)

Trains a generic bird detector (single class, remaps all original annotations to that class)
by fine-tuning yolo26n on a balanced subset of the synced dataset. This is the first stage
of a two-stage detection pipeline; species classification runs as stage 2.

### Frame Selection and Balancing

Selects up to 365 positive and 55 negative frames, deterministically seeded from dataset file
contents and sizes (re-annotation reseeds). Spreads frames evenly across day-of-year slots,
honors hour-of-day and species distributions, and guarantees each species appears. Clamps with
warning if dataset is smaller than target.

### Annotation Remapping and Training

Rewrites every annotation in the selected frames to a single class (0: bird), discarding the
original species labels. Trains yolo26n (base weights mounted from the processor package) on
the prepared dataset for 100 epochs at batch size 16 and image size 640. The base model and
training parameters are fixed; versions and descriptions vary by invocation.

### Invocation

Invoked via `make -C local lab-fine-tune ARGS="--version v1.0.0 --description '...'"` (or
interactively). Version matches v\d+\.\d+\.\d+; description limited to 1024 chars. Saves weights,
dataset.yaml, and metadata.json under /.storage/fine_tuned/. Rebuild the lab image after updating
dependencies so new versions take effect; a stale image may crash during training.

## Stage-2 Species Classification

Trains yolo26n-cls on crops from stage-1 detections using frame selection with a different salt
for a distinct subset. Extracts crops per labelled bird; generates background crops from bird-free
frames (random crops and false positives from stage-1 base model). Balances per-class crop counts.
Invoked via `make -C local lab-classify ARGS="--version v1.0.0 --description '...'"`.
Saves weights, classes.json, and metadata.json under /.storage/fine_tuned/.
