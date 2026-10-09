# Infra

Ansible playbooks that provision and deploy all SparrowCam services to a
Raspberry Pi over SSH. Manages users, groups, directory layout, Python
environments, systemd services, nginx, cron jobs, and external storage mounting.

## Deployment Model

Each service receives a sparse git clone containing only its own application
directory. This avoids shipping unrelated code to the Pi and keeps each
service's footprint minimal.

## Cross-Service File Access

A shared group grants the processor, nginx, and other services access to
shared directories (HLS segments, annotations, archive storage) without
opening world-write permissions. Shared directories are owned by this group
with mode 0775.

## Web Build Strategy

The web frontend is built locally, not on the Pi. An npm build runs inside a
temporary Docker container on the deploy machine; only the compiled output is
copied to the Pi. Node.js is never installed on the Pi.

## External Storage

The archive drive is mounted by UUID rather than device path, so the mount
survives USB resets and device renaming. The ext4 filesystem must be
pre-formatted manually before the storage setup playbook is run — the playbook
will fail with guidance if the partition is unformatted.

## Ephemeral Storage (tmpfs)

HLS segments and annotations use tmpfs to reduce SD card wear; mounts persist
via /etc/fstab. The setup_tmpfs.yml playbook manages these exclusively with
ownership and permissions in mount options (uid/gid/mode). Service playbooks
no longer create these directories, which must be managed by setup_tmpfs first.

## Secrets Management

All credentials and SSH keys are stored under `infra/ansible/.secrets/` (git-ignored):
- SSH key pair for Ansible provisioning
- AWS credentials for S3 dataset syncing
- Device latitude and longitude, which the processor uses to compute its civil
  dusk-to-dawn maintenance window. Coordinates are deployed to the processor's
  environment, so a change takes effect only after re-running the processor
  setup playbook, which also restarts the processor.

Example credential files are provided with `.example` suffix for reference during setup.

## Metadata Database

The `setup_index_db.yml` playbook provisions a SQLite database at
`/var/lib/sparrow_cam/index.db`, outside any directory served by nginx. It
holds a `recordings` table (primary key `(date, stream)`, plus `detections`,
`manual_annotations`, and `birds` columns) with an index on `date`, and is
initialized in WAL mode. The database file follows the existing shared-group
permission pattern (`sparrow_cam_app` owner, `sparrow_cam` group) so the
processor, Archive API, and cron users — which all run as `sparrow_cam_app` —
can write to it. The processor writes detections on every archive, the Archive
API writes manual_annotations, and cron reads manual_annotations to determine
which recordings to keep during cleanup.

## Cron Jobs

The `setup_cron.yml` playbook installs and schedules cron jobs for the
`sparrow_cam_app` user. Currently supports:

- **cleanup_recordings**: Runs daily at 23:05 to archive and clean up old
  recording segments. Can also be run manually with `make cleanup_recordings`
  from the `infra/` directory.

- **sync_dataset**: Runs daily at 23:35 to sync the local dataset directory
  (`/var/www/html/storage/sparrow_cam/dataset`) to an S3 bucket
  (`sparrow-cam-dataset`). Requires AWS credentials to be configured via
  `infra/ansible/.secrets/aws_credentials`.

## AWS Integration

The provisioning playbooks install AWS CLI and deploy AWS credentials to the
`sparrow_cam_app` user's home directory. This allows the `sync_dataset` cron job
to authenticate with S3 for automated dataset uploads. The S3 bucket must be
created separately; the playbook assumes it already exists.

## Validation

There are no automated tests or linters. Validate changes by running the
relevant playbook against the target device.
