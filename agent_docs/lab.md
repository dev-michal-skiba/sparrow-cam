# Lab

- Source: app/lab/lab/ | Tests: app/lab/tests/

## Purpose

Desktop GUI for managing the bird detection dataset, fine-tuning models, and evaluating results.

## Dataset Splitting

The train/val split targets an 80/20 ratio with per-class balancing. Positive and negative frames
are balanced independently of each other.

## Crop Filtering Rules

When a detection region is applied before training, positive frames are kept only if every
annotation box falls entirely within the crop region. Any frame where even one box extends
outside is excluded entirely — the frame is not trimmed, it is dropped. Partial overlap
breaks annotation integrity.

Negative frames (no annotations) are randomly subsampled after the crop filter runs to
preserve the same positive-to-negative ratio that existed before filtering.

## Testing Notes

The GUI has no unit tests and is excluded from coverage. Do not write tests for it.
