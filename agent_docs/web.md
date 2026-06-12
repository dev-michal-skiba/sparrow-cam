# Web

## Purpose
The web package provides the user-facing interface for SparrowCam:
- Live stream view showing the current camera feed with real-time bird detection status
- Archive browsing by calendar date with filtering by detected bird species
- Manual annotation of archived streams, allowing users to draw bounding boxes on
  video frames and label each box with a bird species

## Filtering Rules
Bird filter and annotation filter are mutually exclusive. Applying both at the same
time produces a 400 error from the API. The UI enforces this constraint so users
cannot select both simultaneously.

The annotation filter has two options that reflect the state of manual annotation
work on a stream:
- "Exclude annotated" — omits streams where annotation work has been done
- "Exclude false positives" — hides streams reviewed and confirmed as false positives
  (default; selected on load)

When viewing an archived stream, if manual annotations exist for that stream, they
take precedence: the bird species filter sources its options from manual annotations
rather than auto detections. The status display also shows manual annotations
separately (dimmed auto detections alongside highlighted manual annotations on
desktop; stacked vertically on mobile). This precedence ensures annotated streams
show only the manually-verified bird species to the user.

In the playback view, annotation filters are conditionally shown based on stream
state: "Exclude false positives" displays only when the current stream is NOT a
false positive, and "Exclude annotated" displays only when the current stream has
no manual annotations. The calendar view always shows both options.

## Manual Annotation State
The `manual_annotations` field in stream metadata carries specific meaning:
- `null` — no annotation work has been done on this stream
- `{}` (empty object) — the stream was reviewed and confirmed as a false positive
  (a bird was detected by the model but no real bird was present)

This distinction drives the `exclude_false_positives` API filter: only streams with
`manual_annotations` not equal to `{}` are returned when that filter is active.

## Filter Persistence
Filter state persists in the URL query string (`birds`, `annotation` keys) across
page refreshes and navigation. Calendar year/month are also tracked in the URL to
maintain position when filters change. The calendar view includes a Reset button
(disabled when filters are already at default) to clear all filters at once.

## Bird Type Slugs
The web layer maps slugs to human-readable display names. Slugs communicate with
the API; display names are only used for rendering.

## Development Rules
Never run npm directly on the host machine. All development happens inside Docker.
To add or change dependencies, edit the package file and rebuild the Docker image —
npm runs inside the image build step, not on the host.

There are no automated tests, no formatting checks, and no lint checks for this
package.
