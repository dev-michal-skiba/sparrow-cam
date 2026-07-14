# Cron

Scheduled jobs that maintain the Pi over time. Structured as one package holding
multiple independent jobs, so new scheduled jobs can be added without disturbing
existing ones.

## cleanup_recordings Job

Prunes archived recordings so storage on the Pi does not fill up.

- Runs once per day via a real crontab entry at 23:05 local time, pruning that day's
  recordings. Can also be invoked manually for a single day or an inclusive date range.
- A recording counts as manually annotated when its meta.json has a `manual_annotations`
  key, even if the value is an empty object (reviewed as containing no birds). Manually
  annotated recordings are never removed.
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
