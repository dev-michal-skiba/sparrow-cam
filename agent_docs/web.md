# Overview
- Software: Vue 3 + Vite + TypeScript single-page application (SPA)
- Responsibility: Frontend UI that displays the live HLS video stream, detects bird activity in the current segment, and provides stream status information.

## Package Layout
- Package location: `app/web/`
    - Source code: `app/web/src/`
        - `components/` — Vue components
        - `composables/` — Vue composables (reusable logic)
        - `views/` — Full-page Vue views (routed)
        - `types/` — TypeScript type definitions
        - `styles/` — global CSS
    - Build output: `app/web/dist/` (production only, not used locally)

## Views

### `LiveView.vue`
Main page showing the live HLS stream with bird detection annotations in real-time.

### `ArchiveView.vue`
Archive browse interface. Renders an `ArchiveCalendar` widget for month navigation and day selection.

### `ArchivePlaybackView.vue`
Full-page archive playback view. Reads route parameters to construct a playlist URL for a specific archived stream. Renders the `ArchivePlayer` component and tracks the current segment. Uses `useArchiveMeta` to fetch detection metadata and passes detection data to `ArchiveBirdStatus` for display below the player.

## Components

### Live Feed
#### `AppHeader.vue`
Main application header displaying title and navigation.

#### `VideoPlayer.vue`
HLS video player component. Uses the `useHlsPlayer` composable to manage playback. Displays the live stream and responds to stream status changes.

#### `StreamStatus.vue`
Displays current stream status. Shows whether the stream is active or stopped.

#### `BirdStatus.vue`
Shows bird detection status for the currently displayed segment. Uses the `useAnnotations` composable to access bird detection data.

### Archive
#### `ArchiveCalendar.vue`
Calendar widget for browsing archived streams. Features month navigation (with future month restriction), day grid with stream count badges, and today highlighting. Clicking a day shows `ArchiveDayModal`.

#### `ArchiveCalendarDay.vue`
Single day cell in the calendar. Displays the day number, a badge with stream count if available, and visual states for today and future days (disabled).

#### `ArchiveDayModal.vue`
Modal overlay showing all archived streams for a selected day. Displays streams as clickable links that navigate to `ArchivePlaybackView` using the archive-playback route.

#### `ArchivePlayer.vue`
HLS video player for archive streams. Wraps hls.js with a `playlistUrl` prop. Emits `segmentChange` event when the currently displayed segment changes (based on hls.js FRAG_CHANGED event). Reusable for both live and archive playback.

#### `ArchiveBirdStatus.vue`
Displays bird detection information for the currently displayed archive segment. Shows species and confidence for each detection, or displays status messages (loading, unavailable, or no detections). Accepts `currentDetections` and `metaAvailable` props from the parent view.

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

### `useArchive.ts`
Fetches and caches archive metadata from the archive API:
- Accepts year and month refs, queries `/archive/api?from=YYYY-MM-01&to=YYYY-MM-DD`
- Returns a `MonthArchive` (map of day numbers to stream lists) keyed by year-month for memory efficiency
- Supports reactive month/year changes with cached results

### `useArchiveMeta.ts`
Fetches bird detection metadata (`meta.json`) for an archived stream:
- Accepts a `metaUrl` (archive stream metadata endpoint) and reactive `currentSegment` ref
- Exposes `currentDetections` (computed list of detections for the current segment) and `metaAvailable` (loading/available/unavailable state)
- Handles missing or unreachable metadata gracefully

## Types

### `archive.ts`
TypeScript interfaces for archive API responses:
- `ArchiveApiResponse` — Nested Record structure keyed by year → month → day → stream ID
- `DayArchive` — Represents a single day with day number and list of stream IDs
- `MonthArchive` — Map from day numbers to `DayArchive` objects

## Routing

Router supports:
- `/` → `LiveView` (live stream)
- `/archive` → `ArchiveView` (calendar browse)
- `/archive/:year/:month/:day/:stream` → `ArchivePlaybackView` (playback a specific archived stream)

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
Web package has no automated tests, formatting or linting. Just skip it
