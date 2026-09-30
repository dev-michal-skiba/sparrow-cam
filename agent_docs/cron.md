# Cron

Scheduled jobs that maintain the Pi over time. Structured as one package holding
multiple independent jobs, so new scheduled jobs can be added without disturbing
existing ones.

## cleanup_recordings Job

Prunes archived recordings so storage on the Pi does not fill up.

### Scheduled daily invocation

Runs once per day via a real crontab entry at 23:05 local time. Rather than pruning a fixed
calendar day, it runs a free-space-pressure sweep: it prunes the oldest not-yet-cleaned
archived day one at a time, rechecking disk free space after each, until free space reaches
15 GB. The last cleaned-up day is persisted to disk so the sweep never reprocesses days
across runs. If the sweep exhausts all archived days and free space is still below the
threshold, it stops and logs the condition.

On first run (no previous sweep history), the sweep starts from the earliest day present in
the archive and steps forward one day at a time; after that, it starts the day after the
last recorded cleanup and steps forward.

### Manual invocation

Can be invoked manually for a single day or an inclusive date range using `--from-date`
and/or `--to-date` arguments. This bypasses the free-space threshold and persistent
watermark—it prunes exactly the specified day(s) directly.

### Per-day pruning rules

The following logic applies when pruning any day, whether as part of the sweep or via
manual invocation:

- A recording counts as manually annotated when its database row has a non-null
  `manual_annotations` field, even if the value is an empty object (reviewed as containing
  no birds). Manually annotated recordings are never removed.
- Recordings with more than 60 segments are always removed, regardless of the keep budget
  below. This does not apply to manually annotated recordings.
- Of the remaining non-annotated recordings, up to 10 are kept. This budget is reduced
  by one for every manually annotated recording that day, so a day can end up keeping
  more than 10 recordings in total once annotated ones are counted.
- Kept recordings are chosen by splitting the day's remaining recordings into that many
  time-ordered groups and picking one at random from each group, so survivors are spread
  across the day rather than clustered by chance.

## Deployment

Jobs run under the existing sparrow_cam_app user, in their own pyenv virtualenv built
from a Python version already installed for that user — no new OS user or Python
version is provisioned for cron jobs.
