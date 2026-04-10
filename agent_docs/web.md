# Overview
- Software: Vue 3 + Vite + TypeScript single-page application (SPA)
- Responsibility: Frontend UI that displays the live HLS video stream, detects bird activity in the current segment, and provides stream status information.

## Package Layout
- Package location: `app/web/`
    - Source code: `app/web/src/`
        - `components/` — Vue components
        - `composables/` — Vue composables (reusable logic)
        - `styles/` — global CSS
    - Build output: `app/web/dist/` (production only, not used locally)

## Components

### `AppHeader.vue`
Main application header displaying title and navigation.

### `VideoPlayer.vue`
HLS video player component. Uses the `useHlsPlayer` composable to manage playback. Displays the live stream and responds to stream status changes.

### `StreamStatus.vue`
Displays current stream status. Shows whether the stream is active or stopped.

### `BirdStatus.vue`
Shows bird detection status for the currently displayed segment. Uses the `useAnnotations` composable to access bird detection data.

## Composables

### `useHlsPlayer.ts`
Manages hls.js lifecycle and stream playback:
- Initializes and attaches hls.js to the video element
- Handles manifest/segment loading and error recovery
- Exposes reactive state: `currentSegment` (currently displayed segment), `isStreamActive` (stream connection status)

### `useAnnotations.ts`
Fetches bird detection annotations from the server:
- Polls `/annotations/bird.json` every 500ms to fetch latest bird detections
- Exposes reactive bird detection data keyed by segment name

## Development Workflow

**Everything runs in Docker — do not run `npm` commands directly on the host.**

### Start Full Stack (including web dev server)
```
make -C local build   # build all Docker images (includes web image with npm ci)
make -C local start   # start all services
make -C local stream  # start ffmpeg stream
```

The `web` Docker service runs `npm run dev` (Vite dev server on port 5173). nginx proxies all web requests (`/`) to the Vite dev server at `http://web:5173`, serving HLS and annotations directly from volumes.

Source files in `app/web/src/`, `app/web/public/`, `app/web/index.html`, and config files are bind-mounted into the container, so edits on the host trigger Vite HMR instantly.

`node_modules` lives inside the Docker image (installed via `RUN npm install` during `docker build`). To add or update dependencies:
1. Edit `app/web/package.json`
2. Run `make -C local build` — `npm install` runs inside the image build and resolves the new deps

Access the app at `http://localhost:8080`.

## Deployment

Deploy to Raspberry Pi with:
```
make -C infra setup_web
```
This target automatically:
1. Builds the web app using a temporary `node:20-alpine` Docker container (no local Node.js required): `npm ci && npm run build`
2. Runs the Ansible playbook `setup_web.yml`
3. Playbook copies `app/web/dist/` to `/var/www/html/` on the Raspberry Pi
4. nginx serves the SPA at `/` on port 80

## No Tests
Web package has no automated tests. Tests to be added later.
