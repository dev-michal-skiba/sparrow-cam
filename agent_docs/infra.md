# Infra

Ansible playbooks that provision and deploy all SparrowCam services to a
Raspberry Pi over SSH. Manages users, groups, directory layout, Python
environments, systemd services, nginx, and external storage mounting.

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

## Validation

There are no automated tests or linters. Validate changes by running the
relevant playbook against the target device.
