# Overview
- Software: Ansible playbooks + Docker-based runner
- Responsibility: Provisions and deploys all SparrowCam services to a Raspberry Pi over SSH. Manages users, groups, directory layout, Python environments, systemd services, nginx, and external storage mounting.

## Package Layout
- `infra/` — root
    - `Makefile` — all deployment commands (run from repo root as `make -C infra <target>`)
    - `Dockerfile` / `docker-compose.yml` — container that runs Ansible so no local Ansible install is needed
    - `ansible/` — all playbooks and config
        - `inventory.yml` — target host definition
        - `group_vars/all.yml` — `ansible_target_host` and `ansible_target_user`
        - `setup_users.yml` — users, groups, build deps, passwordless sudo
        - `setup_storage.yml` — ext4 mount, fstab, UAS quirk
        - `setup_processor.yml` — processor service deploy
        - `setup_archive_api.yml` — archive API service deploy
        - `setup_stream.yml` — stream service deploy
        - `setup_web.yml` — nginx install and config
        - `archive.yml` — one-shot stream archiver run
        - `tasks/apt_update.yml` — shared apt cache update (included at top of every playbook)
        - `tasks/pyenv_setup.yml` — shared pyenv + virtualenv setup (parameterized, included by app playbooks)

## Users and Groups

| User | Home | Groups | Purpose |
|------|------|--------|---------|
| `sparrow_cam_app` | `/opt/sparrow_cam_app` | `sparrow_cam`, `video` | Runs processor, archive API, and stream services |
| `sparrow_cam_infra` | (pre-existing) | `sparrow_cam` | Ansible deploy user |
| `www-data` | `/var/www` | `sparrow_cam` | nginx workers |

Shared group `sparrow_cam` (mode `0775`) grants cross-service file access without opening world-write permissions.

## Directory Layout on Target

```
/opt/sparrow_cam_app/
  .pyenv/                          # single pyenv install
  .pyenvrc / .bashrc               # pyenv init
  tmp/
  apps/
    processor/                     # Python 3.11.13, venv "sparrow_cam_processor"
    archive_api/                   # Python 3.13.3, venv "sparrow_cam_archive_api"
    stream/                        # symlink to sparse clone of app/stream

/var/www/html/
  hls/                             # owner: sparrow_cam_app, group: sparrow_cam
  annotations/                     # owner: sparrow_cam_app, group: sparrow_cam
  storage/sparrow_cam/archive/     # owner: sparrow_cam_app, group: sparrow_cam (ext4 mount)
```

## Playbooks

### `setup_users.yml`
Creates `sparrow_cam` group, creates `sparrow_cam_app` user, installs build dependencies (for Python apps), enables passwordless sudo for `sparrow_cam_infra`.

### `setup_storage.yml`
Mounts external drive at `/var/www/html/storage`. Formats with ext4 if blank. Persists via fstab using UUID (survives USB resets). Adds UAS quirk to `cmdline.txt` to force stable `usb-storage` driver on Raspberry Pi.

### `setup_processor.yml` / `setup_archive_api.yml`
Each includes `tasks/pyenv_setup.yml` to install the correct Python version and create the named virtualenv, copies app source, runs pip install, and installs/enables a systemd service.

### `setup_stream.yml`
Installs ffmpeg, adds `sparrow_cam_app` to the `video` group (for camera access), clones the repo with sparse checkout (only `app/stream/`), creates a symlink to the cloned directory, makes `stream.sh` executable, changes HLS directory owner from `sparrow_cam_stream` to `sparrow_cam_app`, and deploys/enables the `sparrow-stream` systemd service (runs `stream.sh` as `sparrow_cam_app`).

### `setup_web.yml`
Installs nginx + ufw, configures firewall (ports 22, 80), creates HLS directory, deploys `nginx.conf` with variable substitution for `WEB_PORT` and `ARCHIVE_API_URL`. Configures nginx to serve:
- Static web app files from `/var/www/html/` (built output from `app/web/dist/`)
- Live HLS at `/hls/`
- Archived HLS at `/archive/storage/`
- Archive API proxy at `/archive/api`

### `archive.yml`
Runs `processor.stream_archiver` as `sparrow_cam_app` (one-shot). Accepts optional `LIMIT` variable.

## nginx Configuration

The `nginx.conf` file deployed by `setup_web.yml` defines three main location blocks:

- `/hls/` — serves live HLS segments and playlists from `/var/www/html/hls/`
- `/archive/storage/` — serves archived HLS segments and playlists from `/var/www/html/storage/sparrow_cam/archive/` (using alias to strip the location prefix)
- `/archive/api` — proxies requests to the archive API service with `proxy_pass ${ARCHIVE_API_URL}/` (the trailing slash strips the `/archive/api` path prefix before forwarding)

Both HLS locations include CORS headers and cache-control directives appropriate for streaming.

## Shared Tasks

### `tasks/apt_update.yml`
Runs `apt update` with `cache_valid_time: 3600`. Included as the first task in every playbook.

### `tasks/pyenv_setup.yml`
Parameters: `python_version`, `virtualenv_name`, `app_user`, `app_home`.
Installs pyenv, writes `.pyenvrc` and `.bashrc` block, installs the requested Python version, creates the named virtualenv. Skips steps that are already done (stat-guarded).

## Make Targets

```
make -C infra build               # Build the Ansible Docker container
make -C infra ping                # Test SSH connectivity
make -C infra setup_users         # Users, groups, passwordless sudo
make -C infra setup_storage       # Mount external hard drive (DEVICE=... to override /dev/sda1)
make -C infra setup_processor     # Deploy processor service
make -C infra setup_archive_api   # Deploy archive API service
make -C infra setup_stream        # Deploy stream service
make -C infra web_build           # Build web app (npm ci && npm run build inside docker)
make -C infra setup_web           # Build web app and deploy web server (nginx)
make -C infra setup_all           # Run all of the above in order
make -C infra archive             # Run stream archiver (LIMIT=N to cap segments)
```

## No Tests or Linting
Infra has no automated tests or linters. Validate changes by running the relevant playbook against the target device.
