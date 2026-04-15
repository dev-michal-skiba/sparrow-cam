# Overview
- Software: Vue 3 + Vite + TypeScript single-page application (SPA)
- Responsibility: Frontend UI that displays the live HLS video stream and detects bird activity in the current segment.

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
Main page showing the live HLS stream with bird detection annotations in real-time. Displays the video player and renders `ArchiveBirdStatus` below it to show detection details (species and confidence) for the currently displayed segment.

### `ArchiveView.vue`
Archive browse interface. Renders an `ArchiveCalendar` widget for month navigation and day selection.

### `ArchivePlaybackView.vue`
Full-page archive playback view. Reads route parameters to construct a playlist URL for a specific archived stream. Renders the `ArchivePlayer` component and tracks the current segment. Uses `useArchiveMeta` to fetch detection metadata and passes detection data to `ArchiveBirdStatus` for display below the player.

## Components

### Live Feed
#### `AppHeader.vue`
Main application header displaying title and navigation.

#### `VideoPlayer.vue`
HLS video player component. Uses the `useHlsPlayer` composable to manage playback. Displays the live stream.

#### `BirdStatus.vue`
(Deprecated — no longer used in LiveView.)

### Archive
#### `ArchiveCalendar.vue`
Calendar widget for browsing archived streams. Features month navigation (with future month restriction), day grid with stream count badges, and today highlighting. Clicking a day shows `ArchiveDayModal`. Accepts `birdsParam` prop to filter streams by selected bird types.

#### `ArchiveCalendarDay.vue`
Single day cell in the calendar. Displays the day number, a badge with stream count if available, and visual states for today and future days (disabled).

#### `ArchiveDayModal.vue`
Modal overlay showing all archived streams for a selected day. Displays streams as clickable links that navigate to `ArchivePlaybackView` using the archive-playback route.

#### `ArchivePlayer.vue`
HLS video player for archive streams. Wraps hls.js with a `playlistUrl` prop. Emits `segmentChange` event when the currently displayed segment changes (based on hls.js FRAG_CHANGED event). Reusable for both live and archive playback.

#### `ArchiveBirdStatus.vue`
Displays bird detection information for the currently displayed archive segment. Shows two labeled rows: "Birds detected in this stream:" (displays all unique species found in the entire stream) and "Birds detected in this segment:" (displays species with confidence for the current segment). Optionally accepts `streamBirds` prop to show stream-level bird summary (archive view only); segment row always displays. Accepts `currentDetections` and `metaAvailable` props from the parent view.

#### `ArchiveBirdFilter.vue`
UI component for filtering archive streams by bird type. Renders toggle buttons for each bird species. Uses the `useBirdFilter` composable to track selected birds and expose them as a query parameter.

## Composables

### `useHlsPlayer.ts`
Manages hls.js lifecycle and stream playback:
- Initializes and attaches hls.js to the video element
- Handles manifest and segment loading
- Exposes reactive state: `currentSegment` (currently displayed segment)

### `useAnnotations.ts`
Fetches bird detection annotations from the server:
- Polls `/annotations/bird.json` every 500ms to fetch the latest annotations file (format: `{version, detections}`)
- Parses the structured annotations and extracts detections for the current segment
- Exposes `currentDetections` (list of detections for the current segment) and `metaAvailable` (loading/available/unavailable state)

### `useArchive.ts`
Fetches and caches archive metadata from the archive API:
- Accepts year and month refs, and optional `birdsParam` ref for filtering by bird types
- Queries `/archive/api?from=YYYY-MM-01&to=YYYY-MM-DD&birds=...` (birds param is optional)
- Returns a `MonthArchive` (map of day numbers to stream lists) keyed by year-month-birds for memory efficiency
- Each stream in the result now includes metadata (bird species detected in that stream)
- Supports reactive month/year/birds changes with cached results

### `useArchiveMeta.ts`
Fetches bird detection metadata (`meta.json`) for an archived stream:
- Accepts a `metaUrl` (archive stream metadata endpoint) and reactive `currentSegment` ref
- Exposes `currentDetections` (computed list of detections for the current segment), `metaAvailable` (loading/available/unavailable state), and `streamBirds` (list of all unique bird species in the stream)
- Handles missing or unreachable metadata gracefully

### `useArchiveAdjacent.ts`
Fetches previous and next archived streams for navigation:
- Accepts year, month, day, stream identifiers and optional `birdsParam` ref for filtering
- Queries `/archive/api/adjacent?year=...&month=...&day=...&stream=...&birds=...` (birds param is optional)
- Exposes `previous` and `next` refs to navigate between adjacent filtered streams
- Automatically updates when year, month, day, stream, or bird filters change

### `useBirdFilter.ts`
Global reactive state for bird filter selection and bird name utilities:
- Manages a set of selected bird types
- Provides `toggleBird()` function to add/remove bird types from selection
- Exposes `selectedBirds`, `selectedBirdsArray`, and `birdsParam` (comma-separated bird slugs for API queries)
- Exports `unslugBird(slug)` utility function to convert bird name slugs (e.g., "house_sparrow") to human-readable names (e.g., "House sparrow")
- Uses shared state so selection is consistent across all views

## Types

### `archive.ts`
TypeScript interfaces for archive API responses and stream metadata:
- `StreamMeta` — Metadata for a single archived stream, contains list of detected bird species
- `ArchiveApiResponse` — Nested Record structure keyed by year → month → day → stream ID → `StreamMeta`
- `StreamInfo` — Runtime representation of a stream in the archive browse UI with name and detected birds list
- `DayArchive` — Represents a single day with day number and list of `StreamInfo` objects
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
