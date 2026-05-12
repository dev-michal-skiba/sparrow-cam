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
Full-page archive playback view. Reads route parameters to construct a playlist URL for a specific archived stream. Renders the `ArchivePlayer` component and tracks the current segment. Uses `useArchiveMeta` to fetch detection metadata and passes detection data to `ArchiveBirdStatus` for display below the player. Uses `useAnnotationsFilter` to manage annotation filter state and passes both bird and annotation filters to `useArchiveAdjacent` for adjacent stream navigation. Passes detected birds and available annotation filters to `ArchiveBirdFilter`, constraining it to only show species and filters actually applicable to the current recording. Includes a "Manual annotations" link that navigates to `ManualAnnotationsView`.

### `ManualAnnotationsView.vue`
Full-page view for manual annotation of archived streams. Allows users to step through the first frame of each HLS segment using Previous/Next buttons or arrow keys. Users draw region-of-interest bounding boxes on a canvas overlay positioned over the paused video, label each box with a bird species, and submit all annotations via the Archive API. Loads existing manual annotations from `meta.json` on mount to show prior work. Navigates back to `ArchivePlaybackView` on successful submission and warns users before leaving with unsaved changes.

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
Calendar widget for browsing archived streams. Features month navigation (with future month restriction), day grid with stream count badges, and today highlighting. Clicking a day shows `ArchiveDayModal`. Uses `useBirdFilter` and `useAnnotationsFilter` composables to pass both bird and annotation filters to `useArchive` for filtering the displayed streams.

#### `ArchiveCalendarDay.vue`
Single day cell in the calendar. Displays the day number, a badge with stream count if available, and visual states for today and future days (disabled).

#### `ArchiveDayModal.vue`
Modal overlay showing all archived streams for a selected day. Displays streams as clickable links that navigate to `ArchivePlaybackView` using the archive-playback route.

#### `ArchivePlayer.vue`
HLS video player for archive streams. Wraps hls.js with a `playlistUrl` prop. Emits `segmentChange` event when the currently displayed segment changes (based on hls.js FRAG_CHANGED event). Reusable for both live and archive playback.

#### `ArchiveBirdStatus.vue`
Displays bird detection information for the currently displayed archive segment. Shows two labeled rows: "Birds detected in this stream:" (displays all unique species found in the entire stream) and "Birds detected in this segment:" (displays species with confidence for the current segment). Optionally accepts `streamBirds` prop to show stream-level bird summary (archive view only); segment row always displays. Accepts `currentDetections` and `metaAvailable` props from the parent view.

#### `ArchiveBirdFilter.vue`
UI component for filtering archive streams by bird type and manual annotations. Renders toggle buttons for each bird species and annotation filter. Uses `useBirdFilter` and `useAnnotationsFilter` composables to track selections and expose them as query parameters. Accepts optional props: `availableBirds` (list of bird slugs to show) and `availableAnnotationFilters` (list of annotation filter labels to show). When provided, only matching filters are displayed. Watches both props and automatically deselects any currently selected filters not in the updated available lists.

#### `AnnotationCanvas.vue`
Absolutely-positioned overlay canvas positioned over the paused video in `ManualAnnotationsView`. Handles pointer events (mouse and touch) to let users draw region-of-interest bounding boxes on the frame. Displays crosshair help lines (vertical and horizontal) that follow the cursor before drawing starts, allowing users to preview what will be captured in their annotation. The help lines hide during drag and while the species-picker popover is open. When a box is drawn, the species-picker popover appears to assign a bird label. Renders existing ROI annotations as green rectangles with labels and × buttons for removal. Enforces a minimum box size (~1% of frame) to meet backend validation requirements. Emits `add` (ROIAnnotation) and `remove` (index) events to the parent view.

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
- Accepts year and month refs, optional `birdsParam` ref for filtering by bird types, and optional `annotationsParams` ref for annotation filters
- Queries `/archive/api?from=YYYY-MM-01&to=YYYY-MM-DD&birds=...&exclude_annotated=true|include_false_positives=true` (both params optional)
- Returns a `MonthArchive` (map of day numbers to stream lists) keyed by year-month-birds-annotationsParams for memory efficiency
- Each stream in the result includes metadata (bird species detected in that stream)
- Supports reactive changes to year, month, birds filter, and annotations filter with cached results

### `useArchiveMeta.ts`
Fetches bird detection metadata (`meta.json`) for an archived stream:
- Accepts a `metaUrl` (archive stream metadata endpoint) and reactive `currentSegment` ref
- Exposes `currentDetections` (computed list of detections for the current segment), `metaAvailable` (loading/available/unavailable state), `streamBirds` (list of all unique bird species in the stream), and `availableAnnotationFilters` (computed list of applicable annotation filters based on the stream's manual_annotations data)
- `availableAnnotationFilters` returns "Include false positives" if manual_annotations is an empty object; returns "Exclude annotated" if manual_annotations is null
- Handles missing or unreachable metadata gracefully

### `useArchiveAdjacent.ts`
Fetches previous and next archived streams for navigation:
- Accepts year, month, day, stream identifiers, optional `birdsParam` ref for filtering, and optional `annotationsParams` ref for annotation filters
- Queries `/archive/api/adjacent?year=...&month=...&day=...&stream=...&birds=...&exclude_annotated=true|include_false_positives=true` (both params optional)
- Exposes `previous` and `next` refs to navigate between adjacent filtered streams
- Automatically updates when year, month, day, stream, bird filters, or annotations filters change

### `useBirdFilter.ts`
Global reactive state for bird filter selection and bird name utilities:
- Manages a set of selected bird types
- Provides `toggleBird()` function to add/remove bird types from selection
- Exposes `selectedBirds`, `selectedBirdsArray`, and `birdsParam` (comma-separated bird slugs for API queries)
- Exports `BIRD_SLUGS` mapping (human-readable bird names to slugs for use by components)
- Exports `unslugBird(slug)` utility function to convert bird name slugs (e.g., "house_sparrow") to human-readable names (e.g., "House sparrow")
- Uses shared state so selection is consistent across all views

### `useAnnotationsFilter.ts`
Global reactive state for manual annotation filter selection (mutually exclusive filters):
- Manages selection of "Exclude annotated" or "Include false positives" filter
- Provides `toggleAnnotationFilter()` function to toggle a filter on/off (deselects if already selected)
- Exposes `selectedAnnotationFilter` (currently active filter, null if none selected)
- Exposes `annotationsParams` computed property (query parameter object for API, e.g., `{ exclude_annotated: 'true' }` or `{ include_false_positives: 'true' }`)
- Uses shared state so selection is consistent across all views

### `useManualAnnotations.ts`
Manages in-memory state for manual bounding box annotations keyed by segment filename:
- `load(metaUrl)`: Fetches `meta.json` and seeds annotations from the `manual_annotations` field
- `addRoi` / `removeRoi`: Mutate per-segment annotation lists in memory
- `submit({year, month, day, stream})`: PATCHes `/archive/api/meta?…` with the full annotations payload, omitting empty segments
- Exposes reactive state: `annotations`, `isDirty` (changes since last load/submit), `submitting`, `error`, `lastSubmitOk`

## Types

### `archive.ts`
TypeScript interfaces for archive API responses and stream metadata:
- `StreamMeta` — Metadata for a single archived stream, contains list of detected bird species
- `ArchiveApiResponse` — Nested Record structure keyed by year → month → day → stream ID → `StreamMeta`
- `StreamInfo` — Runtime representation of a stream in the archive browse UI with name and detected birds list
- `DayArchive` — Represents a single day with day number and list of `StreamInfo` objects
- `MonthArchive` — Map from day numbers to `DayArchive` objects

### `annotations.ts`
TypeScript interfaces and types for manual bounding box annotations:
- `BirdSlug` — Union type for supported bird species slugs (`'great_tit' | 'house_sparrow' | 'pigeon'`)
- `BoundingBox` — Normalized bounding box with `x`, `y`, `width`, `height` (all in range 0–1)
- `ROIAnnotation` — Region-of-interest annotation with a `bird_class` (BirdSlug) and a `bbox` (BoundingBox)
- `ManualAnnotationsMap` — Type alias for a map keyed by segment filename to list of ROIAnnotations

## Routing

Router supports:
- `/` → `LiveView` (live stream)
- `/archive` → `ArchiveView` (calendar browse)
- `/archive/:year/:month/:day/:stream` → `ArchivePlaybackView` (playback a specific archived stream)
- `/archive/:year/:month/:day/:stream/annotate` → `ManualAnnotationsView` (manual annotation of a stream, named `archive-annotate`)

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
