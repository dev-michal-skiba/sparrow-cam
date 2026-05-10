<template>
  <div class="page">
    <div class="nav-bar">
      <RouterLink :to="`/archive/${year}/${month}/${day}/${stream}`" class="back-link">&#8592; Back</RouterLink>
      <div class="seg-nav">
        <button
          type="button"
          class="adj-link"
          :class="{ 'adj-link--disabled': !hasPrevSegment }"
          :disabled="!hasPrevSegment"
          @click="goPrev"
        >&#8592; Previous</button>
        <button
          type="button"
          class="adj-link"
          :class="{ 'adj-link--disabled': !hasNextSegment }"
          :disabled="!hasNextSegment"
          @click="goNext"
        >Next &#8594;</button>
        <span class="hint-trigger" tabindex="0">?
          <span class="hint-tooltip">Drag to draw a box, then pick a bird. Click × to remove. Use ←/→ keys or the buttons above to move between segments.</span>
        </span>
      </div>
    </div>
    <div class="divider" />

    <div class="player-col">
      <div class="video-shell">
        <video ref="videoRef" playsinline muted></video>
        <AnnotationCanvas
          v-if="videoReady"
          :annotations="currentAnnotations"
          @add="onAdd"
          @remove="onRemove"
        />
      </div>
    </div>

    <div class="actions-col">
      <div class="submit-row">
        <span class="seg-label">{{ segmentLabel }}</span>
        <button
          type="button"
          class="submit-btn"
          :disabled="submitting || !isDirty"
          @click="onSubmit"
        >{{ submitting ? 'Submitting…' : 'Submit' }}</button>
      </div>
      <p v-if="statusMessage" class="status" :class="{ 'status--error': !!error }">
        {{ statusMessage }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import Hls, { type Fragment } from 'hls.js'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, RouterLink, onBeforeRouteLeave } from 'vue-router'
import AnnotationCanvas from '../components/AnnotationCanvas.vue'
import { useManualAnnotations } from '../composables/useManualAnnotations'
import type { ROIAnnotation } from '../types/annotations'

const route = useRoute()
const router = useRouter()
const { year, month, day, stream } = route.params as Record<string, string>

const playlistUrl = `/archive/storage/${year}/${month}/${day}/${stream}/sparrow_cam.m3u8`
const metaUrl = `/archive/storage/${year}/${month}/${day}/${stream}/meta.json`

const videoRef = ref<HTMLVideoElement | null>(null)
const videoReady = ref(false)
const segments = ref<Array<{ filename: string; start: number }>>([])
const currentIndex = ref(0)
let hls: Hls | null = null

const {
  isDirty,
  submitting,
  error,
  lastSubmitOk,
  load,
  getForSegment,
  addRoi,
  removeRoi,
  submit,
} = useManualAnnotations()

const currentSegmentName = computed(() => segments.value[currentIndex.value]?.filename ?? '')

const currentAnnotations = computed<ROIAnnotation[]>(() =>
  currentSegmentName.value ? getForSegment(currentSegmentName.value) : [],
)

const segmentLabel = computed(() => {
  const total = segments.value.length
  if (total === 0) return '—'
  return `${currentIndex.value + 1}/${total}`
})

const hasPrevSegment = computed(() => currentIndex.value > 0)
const hasNextSegment = computed(() => currentIndex.value < segments.value.length - 1)

const statusMessage = computed(() => {
  if (error.value) return error.value
  if (lastSubmitOk.value && !isDirty.value) return 'Saved.'
  return ''
})

function seekToSegment(index: number) {
  const video = videoRef.value
  const seg = segments.value[index]
  if (!video || !seg) return
  video.pause()
  video.currentTime = seg.start + 0.001
}

function goPrev() {
  if (!hasPrevSegment.value) return
  currentIndex.value -= 1
  seekToSegment(currentIndex.value)
}

function goNext() {
  if (!hasNextSegment.value) return
  currentIndex.value += 1
  seekToSegment(currentIndex.value)
}

function onAdd(roi: ROIAnnotation) {
  if (!currentSegmentName.value) return
  addRoi(currentSegmentName.value, roi)
}

function onRemove(index: number) {
  if (!currentSegmentName.value) return
  removeRoi(currentSegmentName.value, index)
}

async function onSubmit() {
  const ok = await submit({ year, month, day, stream })
  if (ok) {
    router.push(`/archive/${year}/${month}/${day}/${stream}`)
  }
}

function onKey(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
    return
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    goPrev()
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    goNext()
  }
}

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (isDirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}

function buildSegmentList(fragments: Fragment[]) {
  segments.value = fragments
    .filter((f) => typeof f.start === 'number')
    .map((f) => {
      const url = f.url || f.relurl || ''
      const filename = url.substring(url.lastIndexOf('/') + 1) || (f.relurl ?? '')
      return { filename, start: f.start }
    })
    .filter((s) => s.filename.length > 0)
  if (segments.value.length > 0) {
    currentIndex.value = 0
  }
}

function setupHls() {
  const video = videoRef.value
  if (!video) return

  if (Hls.isSupported()) {
    hls = new Hls({ startPosition: 0 })
    hls.loadSource(playlistUrl)
    hls.attachMedia(video)
    hls.on(Hls.Events.LEVEL_LOADED, (_event, data) => {
      const fragments = data.details?.fragments ?? []
      if (fragments.length === 0) return
      buildSegmentList(fragments)
      videoReady.value = true
      seekToSegment(0)
    })
    return
  }

  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = playlistUrl
    video.addEventListener('loadedmetadata', () => {
      video.pause()
      video.currentTime = 0
      segments.value = []
      videoReady.value = true
    }, { once: true })
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('beforeunload', onBeforeUnload)
  await load(metaUrl)
  setupHls()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('beforeunload', onBeforeUnload)
  hls?.destroy()
  hls = null
})

onBeforeRouteLeave((_to, _from, next) => {
  if (isDirty.value) {
    const ok = window.confirm('Discard unsaved annotations?')
    if (!ok) {
      next(false)
      return
    }
  }
  next()
})
</script>

<style scoped>
.page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 15px;
  gap: 8px;
}

.divider {
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  margin: 0 15px;
}

.back-link {
  color: var(--primary-color);
  text-decoration: none;
  opacity: 0.7;
  font-size: 0.9rem;
  transition: opacity 0.15s;
  white-space: nowrap;
}

.back-link:hover {
  opacity: 1;
}

.seg-nav {
  display: flex;
  align-items: center;
  gap: 6px;
}

.adj-link {
  appearance: none;
  -webkit-appearance: none;
  font-family: inherit;
  font-weight: inherit;
  color: var(--primary-color);
  text-decoration: none;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 0.9rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0.7;
  user-select: none;
  transition: opacity 0.15s, background 0.15s;
}

.adj-link:not(.adj-link--disabled):hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.07);
}

.adj-link--disabled {
  opacity: 0.2;
  cursor: default;
}

.seg-label {
  font-size: 0.85rem;
  opacity: 0.6;
}

.player-col {
  width: 100%;
  display: flex;
  justify-content: center;
}

.video-shell {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  background: #020617;
  border: 1px solid rgba(15, 23, 42, 0.3);
  width: var(--player-width);
  max-width: 100%;
  aspect-ratio: 16 / 9;
}

video {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: fill;
  border: none;
  border-radius: inherit;
}

.actions-col {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.submit-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.submit-btn {
  font-family: inherit;
  font-weight: 700;
  font-size: 0.95rem;
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid var(--secondary-color);
  background: rgba(3, 182, 3, 0.18);
  color: var(--secondary-color);
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
}

.submit-btn:hover:not(:disabled) {
  background: var(--secondary-color);
  color: #022c22;
}

.submit-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.status {
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.8;
}

.status--error {
  color: #ff7b7b;
}

.hint-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.25);
  font-size: 0.8rem;
  opacity: 0.6;
  cursor: default;
  user-select: none;
}

.hint-trigger:hover,
.hint-trigger:focus-visible {
  opacity: 1;
}

.hint-tooltip {
  display: none;
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  width: 280px;
  padding: 8px 10px;
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 400;
  opacity: 0.9;
  line-height: 1.5;
  white-space: normal;
  z-index: 20;
  pointer-events: none;
}

.hint-trigger:hover .hint-tooltip,
.hint-trigger:focus-visible .hint-tooltip {
  display: block;
}

@media (orientation: landscape) and (max-height: 500px) {
  .page {
    display: grid;
    grid-template-columns: 40% 1fr;
    grid-template-areas:
      "nav     player"
      "sep     player"
      "actions player";
    align-items: start;
    gap: 0;
    background: linear-gradient(to right, rgba(15, 23, 42, 0.25) 40%, transparent 40%);
  }

  .nav-bar {
    grid-area: nav;
    padding: 6px 14px 4px;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .divider {
    grid-area: sep;
    margin: 2px 14px;
    border-top-color: rgba(255, 255, 255, 0.08);
  }

  .actions-col {
    grid-area: actions;
    padding: 4px 14px 6px;
  }

  .player-col {
    grid-area: player;
    border-left: 1px solid rgba(3, 182, 3, 0.2);
    padding-left: 14px;
    align-self: start;
  }

  .video-shell {
    width: 100%;
    max-height: 80vh;
  }
}
</style>
